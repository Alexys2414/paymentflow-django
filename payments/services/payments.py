"""Servicios transaccionales para crear y procesar solicitudes de pago."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from payments.gateways.base import (
    GatewayCommunicationError,
    GatewayResult,
    PaymentGateway,
)
from payments.models import PaymentEvent, PaymentRequest, PaymentStatus


logger = logging.getLogger(__name__)


class IdempotencyConflictError(Exception):
    """Una clave de idempotencia se reutilizó con otra solicitud."""


class InvalidPaymentTransitionError(Exception):
    """Una solicitud no puede cambiar al estado solicitado."""


@dataclass(frozen=True)
class CreatePaymentRequestCommand:
    amount: Decimal
    concept: str
    reference: str
    idempotency_key: str
    expires_at: datetime | None = None


@dataclass(frozen=True)
class PaymentCreationResult:
    payment: PaymentRequest
    created: bool


@dataclass(frozen=True)
class PaymentProcessingResult:
    payment: PaymentRequest
    gateway_available: bool


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PaymentStatus.PENDING: {PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.EXPIRED},
    PaymentStatus.PAID: set(),
    PaymentStatus.FAILED: set(),
    PaymentStatus.EXPIRED: set(),
}


def create_payment_request(command: CreatePaymentRequestCommand) -> PaymentCreationResult:
    """Crea una solicitud o devuelve la existente para la misma operación.

    El hash representa los datos que identifican la operación. Una misma clave
    solo puede reutilizarse si el payload es idéntico.
    """
    if not command.idempotency_key.strip():
        raise ValueError("La clave de idempotencia no puede estar vacía.")

    payload_hash = _request_payload_hash(command)

    with transaction.atomic():
        try:
            # El savepoint permite recuperar con seguridad un conflicto de la
            # restricción UNIQUE sin marcar la transacción exterior como rota.
            with transaction.atomic():
                payment = PaymentRequest.objects.create(
                    amount=command.amount,
                    concept=command.concept,
                    reference=command.reference,
                    expires_at=command.expires_at,
                    idempotency_key=command.idempotency_key,
                    payload_hash=payload_hash,
                )
        except IntegrityError as error:
            try:
                payment = PaymentRequest.objects.select_for_update().get(
                    idempotency_key=command.idempotency_key,
                )
            except PaymentRequest.DoesNotExist:
                # El conflicto no pertenecía a la clave de idempotencia (por
                # ejemplo, una restricción de dominio). Conservamos su error.
                raise error
            if payment.payload_hash != payload_hash:
                _log_payment(
                    logging.WARNING,
                    "payment_idempotency_conflict",
                    payment,
                )
                raise IdempotencyConflictError(
                    "La clave de idempotencia ya se usó con otro payload."
                )
            _log_payment(logging.INFO, "payment_idempotency_replayed", payment)
            return PaymentCreationResult(payment=payment, created=False)

        PaymentEvent.objects.create(
            payment_request=payment,
            event_type="payment_request.created",
            new_status=PaymentStatus.PENDING,
            metadata={"source": "service"},
        )
        _log_payment(logging.INFO, "payment_request_created", payment)
        return PaymentCreationResult(payment=payment, created=True)


def process_payment_request(
    payment_id: int,
    gateway: PaymentGateway,
) -> PaymentProcessingResult:
    """Procesa una solicitud pendiente usando la pasarela indicada.

    En este MVP la pasarela simulada no hace I/O, por lo que el bloqueo de fila
    cubre la decisión y evita dobles cobros concurrentes. Para una pasarela real
    haría falta un estado intermedio o una tabla de intentos/outbox.
    """
    with transaction.atomic():
        payment = PaymentRequest.objects.select_for_update().get(pk=payment_id)

        if payment.status != PaymentStatus.PENDING:
            _log_payment(logging.WARNING, "payment_invalid_transition", payment)
            raise InvalidPaymentTransitionError(
                f"No se puede procesar un pago en estado {payment.status}."
            )

        if payment.expires_at is not None and payment.expires_at <= timezone.now():
            _transition_locked(payment, PaymentStatus.EXPIRED, "payment_request.expired")
            return PaymentProcessingResult(payment=payment, gateway_available=True)

        try:
            gateway_result = gateway.charge(payment)
        except GatewayCommunicationError:
            PaymentEvent.objects.create(
                payment_request=payment,
                event_type="payment.gateway_communication_failed",
                previous_status=payment.status,
                new_status=payment.status,
                metadata={"gateway": gateway.__class__.__name__},
            )
            _log_payment(logging.ERROR, "payment_gateway_communication_error", payment)
            return PaymentProcessingResult(payment=payment, gateway_available=False)

        target_status = (
            PaymentStatus.PAID
            if gateway_result == GatewayResult.APPROVED
            else PaymentStatus.FAILED
        )
        _transition_locked(payment, target_status, "payment_request.status_changed")
        return PaymentProcessingResult(payment=payment, gateway_available=True)


def transition_payment_request(payment_id: int, target_status: PaymentStatus) -> PaymentRequest:
    """Cambia el estado de una solicitud aplicando el grafo permitido."""
    with transaction.atomic():
        payment = PaymentRequest.objects.select_for_update().get(pk=payment_id)
        _transition_locked(payment, target_status, "payment_request.status_changed")
        return payment


def _transition_locked(
    payment: PaymentRequest,
    target_status: PaymentStatus,
    event_type: str,
) -> None:
    if target_status not in ALLOWED_TRANSITIONS[payment.status]:
        _log_payment(logging.WARNING, "payment_invalid_transition", payment)
        raise InvalidPaymentTransitionError(
            f"Transición no permitida: {payment.status} -> {target_status}."
        )

    previous_status = payment.status
    payment.status = target_status
    payment.save(update_fields=["status", "updated_at"])
    PaymentEvent.objects.create(
        payment_request=payment,
        event_type=event_type,
        previous_status=previous_status,
        new_status=target_status,
        metadata={"source": "service"},
    )
    log_level = logging.WARNING if target_status == PaymentStatus.FAILED else logging.INFO
    event_name = (
        "payment_approved"
        if target_status == PaymentStatus.PAID
        else "payment_rejected"
        if target_status == PaymentStatus.FAILED
        else "payment_expired"
    )
    _log_payment(log_level, event_name, payment)


def _request_payload_hash(command: CreatePaymentRequestCommand) -> str:
    """Calcula una huella estable del payload idempotente."""
    payload = {
        "amount": format(command.amount, "f"),
        "concept": command.concept,
        "currency": "EUR",
        "expires_at": command.expires_at.isoformat() if command.expires_at else None,
        "reference": command.reference,
    }
    serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


class PaymentService:
    """Fachada de los casos de uso consumidos por adaptadores HTTP o CLI."""

    create = staticmethod(create_payment_request)
    process = staticmethod(process_payment_request)
    transition = staticmethod(transition_payment_request)


def _log_payment(level: int, event: str, payment: PaymentRequest) -> None:
    """Registra solo identificadores técnicos y estado, nunca el payload."""
    logger.log(
        level,
        event,
        extra={
            "event": event,
            "payment_uuid": str(payment.uuid),
            "payment_status": payment.status,
        },
    )
