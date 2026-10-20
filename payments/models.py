"""Modelos de persistencia para solicitudes de pago y su auditoría."""

from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


def generate_public_token() -> str:
    """Genera un token opaco adecuado para exponer en un enlace público."""
    return secrets.token_urlsafe(32)


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pendiente"
    PAID = "PAID", "Pagado"
    FAILED = "FAILED", "Fallido"
    EXPIRED = "EXPIRED", "Expirado"


class PaymentRequest(models.Model):
    """Solicitud de pago, sin ningún dato de tarjeta ni información bancaria."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    public_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_public_token,
        editable=False,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="EUR", editable=False)
    concept = models.CharField(max_length=255)
    reference = models.CharField(max_length=100)
    status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True, unique=True)
    payload_hash = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_request_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(currency="EUR"),
                name="payment_request_currency_is_eur",
            ),
            models.CheckConstraint(
                condition=Q(status__in=PaymentStatus.values),
                name="payment_request_status_is_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(idempotency_key__isnull=True, payload_hash__isnull=True)
                    | Q(idempotency_key__isnull=False, payload_hash__isnull=False)
                ),
                name="payment_request_idempotency_pair",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reference} ({self.amount} {self.currency})"


class PaymentEvent(models.Model):
    """Registro de auditoría de una solicitud de pago.

    ``metadata`` se reservará para datos técnicos no sensibles y será saneado
    por el servicio de auditoría de la fase 4.
    """

    payment_request = models.ForeignKey(
        PaymentRequest,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=64)
    previous_status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        null=True,
        blank=True,
    )
    new_status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.event_type} para {self.payment_request_id}"
