from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from payments.gateways.mock import MockPaymentGateway, MockPaymentOutcome
from payments.models import PaymentStatus
from payments.services.payments import (
    CreatePaymentRequestCommand,
    IdempotencyConflictError,
    InvalidPaymentTransitionError,
    create_payment_request,
    process_payment_request,
    transition_payment_request,
)


class PaymentCreationServiceTests(TestCase):
    def command(self, **overrides: object) -> CreatePaymentRequestCommand:
        values: dict[str, object] = {
            "amount": Decimal("25.00"),
            "concept": "Pedido de prueba",
            "reference": "SERVICE-1001",
            "idempotency_key": "create-service-1001",
        }
        values.update(overrides)
        return CreatePaymentRequestCommand(**values)

    def test_creates_a_payment_and_audit_event(self) -> None:
        result = create_payment_request(self.command())

        self.assertTrue(result.created)
        self.assertEqual(result.payment.status, PaymentStatus.PENDING)
        self.assertEqual(result.payment.events.count(), 1)

    def test_returns_existing_payment_for_matching_idempotency_key(self) -> None:
        first = create_payment_request(self.command())
        second = create_payment_request(self.command())

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.payment.pk, second.payment.pk)
        self.assertEqual(second.payment.events.count(), 1)

    def test_rejects_reused_key_with_different_payload(self) -> None:
        create_payment_request(self.command())

        with self.assertRaises(IdempotencyConflictError):
            create_payment_request(self.command(amount=Decimal("26.00")))


class PaymentProcessingServiceTests(TestCase):
    def create_payment(self, **overrides: object):
        command = CreatePaymentRequestCommand(
            amount=Decimal("25.00"),
            concept="Pedido de prueba",
            reference="SERVICE-2001",
            idempotency_key="create-service-2001",
            **overrides,
        )
        return create_payment_request(command).payment

    def test_approved_payment_becomes_paid(self) -> None:
        payment = self.create_payment()

        result = process_payment_request(
            payment.pk,
            MockPaymentGateway(MockPaymentOutcome.APPROVED),
        )

        self.assertTrue(result.gateway_available)
        self.assertEqual(result.payment.status, PaymentStatus.PAID)
        self.assertEqual(result.payment.events.count(), 2)

    def test_declined_payment_becomes_failed(self) -> None:
        payment = self.create_payment()

        result = process_payment_request(
            payment.pk,
            MockPaymentGateway(MockPaymentOutcome.DECLINED),
        )

        self.assertEqual(result.payment.status, PaymentStatus.FAILED)

    def test_communication_error_keeps_payment_pending(self) -> None:
        payment = self.create_payment()

        result = process_payment_request(
            payment.pk,
            MockPaymentGateway(MockPaymentOutcome.COMMUNICATION_ERROR),
        )

        self.assertFalse(result.gateway_available)
        self.assertEqual(result.payment.status, PaymentStatus.PENDING)
        self.assertEqual(result.payment.events.count(), 2)

    def test_expired_payment_is_not_sent_to_gateway(self) -> None:
        payment = self.create_payment(expires_at=timezone.now() - timedelta(seconds=1))

        result = process_payment_request(
            payment.pk,
            MockPaymentGateway(MockPaymentOutcome.APPROVED),
        )

        self.assertEqual(result.payment.status, PaymentStatus.EXPIRED)

    def test_terminal_state_cannot_transition_again(self) -> None:
        payment = self.create_payment()
        transition_payment_request(payment.pk, PaymentStatus.PAID)

        with self.assertRaises(InvalidPaymentTransitionError):
            transition_payment_request(payment.pk, PaymentStatus.FAILED)
