"""Serializers HTTP para el dominio de pagos."""

from __future__ import annotations

import re
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from payments.gateways.mock import MockPaymentOutcome
from payments.models import PaymentEvent, PaymentRequest


IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,254}$")


class PaymentCreateSerializer(serializers.Serializer):
    """Valida únicamente los datos editables al crear una solicitud."""

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    currency = serializers.ChoiceField(choices=["EUR"], required=False, default="EUR")
    concept = serializers.CharField(max_length=255, trim_whitespace=True)
    reference = serializers.CharField(max_length=100, trim_whitespace=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        key = self.context.get("idempotency_key")
        if not isinstance(key, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
            raise serializers.ValidationError(
                {
                    "idempotency_key": (
                        "El encabezado Idempotency-Key debe tener entre 8 y 255 caracteres "
                        "alfanuméricos o . _ : -."
                    )
                }
            )

        expires_at = attrs.get("expires_at")
        if expires_at is not None and expires_at <= timezone.now():
            raise serializers.ValidationError(
                {"expires_at": "La fecha de expiración debe estar en el futuro."}
            )
        return attrs


class PaymentAdminSerializer(serializers.ModelSerializer):
    """Representación de gestión: nunca incluye token, hashes ni claves."""

    class Meta:
        model = PaymentRequest
        fields = [
            "uuid",
            "amount",
            "currency",
            "concept",
            "reference",
            "status",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PaymentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentEvent
        fields = ["event_type", "previous_status", "new_status", "metadata", "created_at"]
        read_only_fields = fields


class PaymentProcessSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=[outcome.value for outcome in MockPaymentOutcome]
    )


class PublicPaymentSerializer(serializers.ModelSerializer):
    """Representación deliberadamente mínima para un enlace no autenticado."""

    class Meta:
        model = PaymentRequest
        fields = ["concept", "amount", "currency", "status"]
        read_only_fields = fields
