"""Formularios de presentación para el dashboard interno."""

from __future__ import annotations

from decimal import Decimal

from django import forms

from payments.serializers import IDEMPOTENCY_KEY_PATTERN


class PaymentRequestForm(forms.Form):
    amount = forms.DecimalField(
        label="Importe",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(
            attrs={
                "class": "field-input",
                "step": "0.01",
                "min": "0.01",
                "inputmode": "decimal",
                "placeholder": "0.00",
            }
        ),
    )
    currency = forms.ChoiceField(
        label="Moneda",
        choices=[("EUR", "EUR")],
        initial="EUR",
        disabled=True,
        widget=forms.Select(attrs={"class": "field-input"}),
    )
    concept = forms.CharField(
        label="Concepto",
        max_length=255,
        widget=forms.TextInput(
            attrs={"class": "field-input", "placeholder": "e.g. Annual platform subscription"}
        ),
    )
    reference = forms.CharField(
        label="Referencia",
        max_length=100,
        widget=forms.TextInput(
            attrs={"class": "field-input", "placeholder": "e.g. INV-2026-001"}
        ),
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput())

    def clean_idempotency_key(self) -> str:
        key = self.cleaned_data["idempotency_key"]
        if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
            raise forms.ValidationError("No se ha podido validar la solicitud. Recarga la página.")
        return key
