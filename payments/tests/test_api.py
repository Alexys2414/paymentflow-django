from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from payments.models import PaymentRequest, PaymentStatus


class PaymentAPITests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="payment-admin",
            password="test-password",
            is_staff=True,
        )
        self.regular_user = user_model.objects.create_user(
            username="regular-user",
            password="test-password",
        )
        self.client = APIClient()

    def authenticate_as_staff(self) -> None:
        self.client.force_authenticate(self.staff_user)

    def payload(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "amount": "25.00",
            "currency": "EUR",
            "concept": "Pedido de prueba API",
            "reference": "API-1001",
        }
        values.update(overrides)
        return values

    def create_payment(
        self,
        *,
        idempotency_key: str = "api-create-1001",
        **overrides: object,
    ) -> PaymentRequest:
        self.authenticate_as_staff()
        response = self.client.post(
            reverse("payment-list"),
            self.payload(**overrides),
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return PaymentRequest.objects.get(uuid=response.data["uuid"])

    def test_unauthenticated_administrative_endpoint_is_rejected(self) -> None:
        response = self.client.get(reverse("payment-list"))

        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_non_staff_user_cannot_read_payments(self) -> None:
        self.client.force_authenticate(self.regular_user)

        response = self.client.get(reverse("payment-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_payment_from_api(self) -> None:
        self.authenticate_as_staff()

        response = self.client.post(
            reverse("payment-list"),
            self.payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-create-1001",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], PaymentStatus.PENDING)
        self.assertIn("uuid", response.data)
        self.assertNotIn("idempotency_key", response.data)
        self.assertNotIn("public_token", response.data)

    def test_invalid_payload_returns_400(self) -> None:
        self.authenticate_as_staff()

        response = self.client.post(
            reverse("payment-list"),
            self.payload(amount="0.00"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)

    def test_missing_idempotency_key_returns_400(self) -> None:
        self.authenticate_as_staff()

        response = self.client.post(
            reverse("payment-list"),
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("idempotency_key", response.data)

    def test_invalid_idempotency_key_format_returns_400(self) -> None:
        self.authenticate_as_staff()

        response = self.client.post(
            reverse("payment-list"),
            self.payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY="short",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("idempotency_key", response.data)

    def test_list_and_detail_are_paginated_and_available_to_staff(self) -> None:
        payment = self.create_payment()

        list_response = self.client.get(reverse("payment-list"))
        detail_response = self.client.get(
            reverse("payment-detail", kwargs={"payment_uuid": payment.uuid})
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["uuid"], str(payment.uuid))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["reference"], payment.reference)

    def test_matching_idempotency_key_returns_existing_payment(self) -> None:
        self.authenticate_as_staff()
        key = "api-repeat-1001"
        first = self.client.post(
            reverse("payment-list"),
            self.payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        second = self.client.post(
            reverse("payment-list"),
            self.payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["uuid"], second.data["uuid"])

    def test_incompatible_idempotency_reuse_returns_409(self) -> None:
        self.authenticate_as_staff()
        key = "api-conflict-1001"
        self.client.post(
            reverse("payment-list"),
            self.payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        response = self.client.post(
            reverse("payment-list"),
            self.payload(amount="26.00"),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_approved_payment_is_processed(self) -> None:
        payment = self.create_payment()

        response = self.client.post(
            reverse("payment-process", kwargs={"payment_uuid": payment.uuid}),
            {"outcome": "approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], PaymentStatus.PAID)

    def test_declined_payment_is_processed(self) -> None:
        payment = self.create_payment(idempotency_key="api-declined-1001")

        response = self.client.post(
            reverse("payment-process", kwargs={"payment_uuid": payment.uuid}),
            {"outcome": "declined"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], PaymentStatus.FAILED)

    def test_communication_error_returns_503_and_keeps_payment_pending(self) -> None:
        payment = self.create_payment(idempotency_key="api-error-1001")

        response = self.client.post(
            reverse("payment-process", kwargs={"payment_uuid": payment.uuid}),
            {"outcome": "communication_error"},
            format="json",
        )

        payment.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_events_are_available_to_staff(self) -> None:
        payment = self.create_payment()

        response = self.client.get(
            reverse("payment-events", kwargs={"payment_uuid": payment.uuid})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["event_type"], "payment_request.created")

    def test_public_payment_response_is_minimal(self) -> None:
        payment = self.create_payment()
        self.client.force_authenticate(user=None)

        response = self.client.get(
            reverse("public-payment", kwargs={"token": payment.public_token})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertSetEqual(
            set(response.data),
            {"concept", "amount", "currency", "status"},
        )
        self.assertEqual(response.data["amount"], "25.00")

    def test_invalid_public_token_returns_404(self) -> None:
        response = self.client.get(reverse("public-payment", kwargs={"token": "missing-token"}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
