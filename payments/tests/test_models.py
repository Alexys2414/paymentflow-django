from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from payments.models import PaymentEvent, PaymentRequest, PaymentStatus


class PaymentRequestModelTests(TestCase):
    def create_payment_request(self, **overrides: object) -> PaymentRequest:
        values: dict[str, object] = {
            "amount": Decimal("19.99"),
            "concept": "Suscripción de demostración",
            "reference": "ORDER-1001",
        }
        values.update(overrides)
        return PaymentRequest.objects.create(**values)

    def test_creates_a_pending_eur_payment_with_public_identifiers(self) -> None:
        payment = self.create_payment_request()

        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(payment.currency, "EUR")
        self.assertIsNotNone(payment.uuid)
        self.assertGreaterEqual(len(payment.public_token), 43)
        self.assertNotEqual(str(payment.pk), str(payment.uuid))

    def test_database_rejects_non_positive_amount(self) -> None:
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                self.create_payment_request(amount=Decimal("0.00"))

    def test_database_rejects_non_eur_currency(self) -> None:
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                self.create_payment_request(currency="USD")

    def test_idempotency_key_and_payload_hash_must_appear_together(self) -> None:
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                self.create_payment_request(idempotency_key="create-1001")

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                self.create_payment_request(payload_hash="a" * 64)

    def test_idempotency_key_is_unique(self) -> None:
        self.create_payment_request(
            idempotency_key="create-1001",
            payload_hash="a" * 64,
        )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                self.create_payment_request(
                    reference="ORDER-1002",
                    idempotency_key="create-1001",
                    payload_hash="b" * 64,
                )


class PaymentEventModelTests(TestCase):
    def test_event_belongs_to_a_payment_request(self) -> None:
        payment = PaymentRequest.objects.create(
            amount=Decimal("20.00"),
            concept="Pedido de prueba",
            reference="ORDER-2001",
        )

        event = PaymentEvent.objects.create(
            payment_request=payment,
            event_type="payment_request.created",
            new_status=PaymentStatus.PENDING,
            metadata={"source": "test"},
        )

        self.assertEqual(payment.events.get(), event)
        self.assertEqual(event.metadata, {"source": "test"})
