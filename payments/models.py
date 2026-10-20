"""Modelos de persistencia para solicitudes de pago y su auditoría."""

from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


def generate_public_token() -> str:
    """Genera un token opaco adecuado para exponer en un enlace público."""
    return secrets.token_urlsafe(32)


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", _("Pendiente")
    PAID = "PAID", _("Pagado")
    FAILED = "FAILED", _("Fallido")
    EXPIRED = "EXPIRED", _("Expirado")


class PaymentRequest(models.Model):
    """Solicitud de pago, sin ningún dato de tarjeta ni información bancaria."""

    uuid = models.UUIDField("UUID", default=uuid.uuid4, unique=True, editable=False)
    public_token = models.CharField(
        "Token público",
        max_length=64,
        unique=True,
        default=generate_public_token,
        editable=False,
    )
    amount = models.DecimalField(
        _("Importe"),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(_("Moneda"), max_length=3, default="EUR", editable=False)
    concept = models.CharField(_("Concepto"), max_length=255)
    reference = models.CharField(_("Referencia"), max_length=100)
    status = models.CharField(
        _("Estado"),
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    expires_at = models.DateTimeField(_("Fecha de expiración"), null=True, blank=True)
    idempotency_key = models.CharField(
        _("Clave de idempotencia"), max_length=255, null=True, blank=True, unique=True
    )
    payload_hash = models.CharField(_("Huella del contenido"), max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Fecha de actualización"), auto_now=True)

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
        verbose_name = _("solicitud de pago")
        verbose_name_plural = _("solicitudes de pago")

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
        verbose_name=_("Solicitud de pago"),
    )
    event_type = models.CharField(_("Tipo de evento"), max_length=64)
    previous_status = models.CharField(
        _("Estado anterior"),
        max_length=10,
        choices=PaymentStatus.choices,
        null=True,
        blank=True,
    )
    new_status = models.CharField(
        _("Estado nuevo"),
        max_length=10,
        choices=PaymentStatus.choices,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(_("Metadatos"), default=dict, blank=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("evento de pago")
        verbose_name_plural = _("eventos de pago")

    def __str__(self) -> str:
        return f"{self.event_type} para {self.payment_request_id}"
