"""Carga datos ficticios e idempotentes para demostrar PaymentFlow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from payments.gateways.mock import MockPaymentGateway, MockPaymentOutcome
from payments.models import PaymentStatus
from payments.services.payments import (
    CreatePaymentRequestCommand,
    IdempotencyConflictError,
    PaymentService,
)


@dataclass(frozen=True)
class DemoPayment:
    reference: str
    concept: str
    amount: Decimal
    idempotency_key: str
    outcome: MockPaymentOutcome | None = None
    expired: bool = False


DEMO_PAYMENTS = (
    DemoPayment(
        reference="DEMO-APPROVED-001",
        concept="Demostración: pago aprobado",
        amount=Decimal("19.90"),
        idempotency_key="seed-demo-approved-001",
        outcome=MockPaymentOutcome.APPROVED,
    ),
    DemoPayment(
        reference="DEMO-DECLINED-001",
        concept="Demostración: pago rechazado",
        amount=Decimal("24.50"),
        idempotency_key="seed-demo-declined-001",
        outcome=MockPaymentOutcome.DECLINED,
    ),
    DemoPayment(
        reference="DEMO-PENDING-001",
        concept="Demostración: pago pendiente",
        amount=Decimal("12.00"),
        idempotency_key="seed-demo-pending-001",
    ),
    DemoPayment(
        reference="DEMO-EXPIRED-001",
        concept="Demostración: pago expirado",
        amount=Decimal("8.75"),
        idempotency_key="seed-demo-expired-001",
        expired=True,
    ),
    DemoPayment(
        reference="DEMO-COMMUNICATION-001",
        concept="Demostración: error de comunicación",
        amount=Decimal("31.20"),
        idempotency_key="seed-demo-communication-001",
        outcome=MockPaymentOutcome.COMMUNICATION_ERROR,
    ),
)


class Command(BaseCommand):
    help = "Crea solicitudes de pago ficticias e idempotentes para demostración."

    def handle(self, *args, **options) -> None:
        for demo_payment in DEMO_PAYMENTS:
            self._seed_payment(demo_payment)

        self.stdout.write(self.style.SUCCESS("Datos de demostración disponibles."))

    def _seed_payment(self, demo_payment: DemoPayment) -> None:
        expires_at = (
            datetime(2025, 1, 1, tzinfo=datetime_timezone.utc)
            if demo_payment.expired
            else None
        )
        command = CreatePaymentRequestCommand(
            amount=demo_payment.amount,
            concept=demo_payment.concept,
            reference=demo_payment.reference,
            idempotency_key=demo_payment.idempotency_key,
            expires_at=expires_at,
        )
        try:
            result = PaymentService.create(command)
        except IdempotencyConflictError as error:
            raise CommandError(
                f"La clave de demo para {demo_payment.reference} tiene datos incompatibles."
            ) from error

        payment = result.payment
        if demo_payment.expired and payment.status == PaymentStatus.PENDING:
            payment = PaymentService.process(
                payment.pk,
                MockPaymentGateway(MockPaymentOutcome.APPROVED),
            ).payment
        elif demo_payment.outcome is not None and payment.status == PaymentStatus.PENDING:
            if (
                demo_payment.outcome == MockPaymentOutcome.COMMUNICATION_ERROR
                and payment.events.filter(
                    event_type="payment.gateway_communication_failed"
                ).exists()
            ):
                pass
            else:
                payment = PaymentService.process(
                    payment.pk,
                    MockPaymentGateway(demo_payment.outcome),
                ).payment

        action = "creada" if result.created else "ya existente"
        self.stdout.write(f"{demo_payment.reference}: {payment.status} ({action})")
