from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from payments.gateways.mock import MockPaymentGateway, MockPaymentOutcome
from payments.models import PaymentRequest, PaymentStatus
from payments.services.payments import CreatePaymentRequestCommand, PaymentService


class DashboardTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="dashboard-staff",
            password="test-password",
            is_staff=True,
        )
        self.regular_user = user_model.objects.create_user(
            username="dashboard-user",
            password="test-password",
        )

    def create_payment(self, **overrides: object) -> PaymentRequest:
        values: dict[str, object] = {
            "amount": Decimal("25.00"),
            "concept": "Dashboard payment",
            "reference": "DASH-1001",
            "idempotency_key": "dashboard-test-1001",
        }
        values.update(overrides)
        return PaymentService.create(CreatePaymentRequestCommand(**values)).payment

    def test_dashboard_requires_authenticated_staff_member(self) -> None:
        response = self.client.get(reverse("dashboard:overview"))

        self.assertRedirects(
            response,
            "/api-auth/login/?next=/dashboard/",
            fetch_redirect_response=False,
        )
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 403)

    def test_overview_uses_real_payment_metrics(self) -> None:
        paid = self.create_payment()
        PaymentService.process(paid.pk, MockPaymentGateway(MockPaymentOutcome.APPROVED))
        self.client.force_login(self.staff)

        response = self.client.get(reverse("dashboard:overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "€25,00")
        self.assertContains(response, "Approved payments")

    def test_payments_filter_by_status_and_search(self) -> None:
        paid = self.create_payment(reference="DASH-PAID", idempotency_key="dashboard-test-paid")
        pending = self.create_payment(reference="DASH-PENDING", idempotency_key="dashboard-test-pending")
        PaymentService.process(paid.pk, MockPaymentGateway(MockPaymentOutcome.APPROVED))
        self.client.force_login(self.staff)

        response = self.client.get(reverse("dashboard:payments"), {"status": "PAID"})
        self.assertContains(response, "DASH-PAID")
        self.assertNotContains(response, "DASH-PENDING")

        response = self.client.get(reverse("dashboard:payments"), {"q": "PENDING"})
        self.assertContains(response, pending.reference)

    def test_staff_can_create_payment_with_service_and_idempotency_key(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("dashboard:payment-create"),
            {
                "amount": "10.50",
                "currency": "EUR",
                "concept": "Created from dashboard",
                "reference": "DASH-CREATE",
                "idempotency_key": "dashboard-create-1001",
            },
        )

        payment = PaymentRequest.objects.get(reference="DASH-CREATE")
        self.assertRedirects(
            response,
            reverse("dashboard:payment-detail", kwargs={"payment_uuid": payment.uuid}),
        )
        self.assertEqual(payment.events.count(), 1)

    def test_detail_shows_audit_timeline_and_processes_with_service(self) -> None:
        payment = self.create_payment()
        self.client.force_login(self.staff)

        detail_response = self.client.get(
            reverse("dashboard:payment-detail", kwargs={"payment_uuid": payment.uuid})
        )
        process_response = self.client.post(
            reverse("dashboard:payment-process", kwargs={"payment_uuid": payment.uuid}),
            {"outcome": "approved"},
        )

        payment.refresh_from_db()
        self.assertContains(detail_response, "Audit timeline")
        self.assertRedirects(
            process_response,
            reverse("dashboard:payment-detail", kwargs={"payment_uuid": payment.uuid}),
        )
        self.assertEqual(payment.status, PaymentStatus.PAID)
