"""Pasarela de pago simulada para desarrollo y pruebas."""

from __future__ import annotations

from enum import StrEnum

from payments.gateways.base import GatewayCommunicationError, GatewayResult
from payments.models import PaymentRequest


class MockPaymentOutcome(StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"
    COMMUNICATION_ERROR = "communication_error"


class MockPaymentGateway:
    """Devuelve un resultado configurado, sin realizar llamadas de red."""

    def __init__(self, outcome: MockPaymentOutcome) -> None:
        self.outcome = outcome

    def charge(self, payment: PaymentRequest) -> GatewayResult:
        """Simula el resultado de un intento de cobro."""
        if self.outcome == MockPaymentOutcome.COMMUNICATION_ERROR:
            raise GatewayCommunicationError("La pasarela simulada no está disponible.")

        if self.outcome == MockPaymentOutcome.APPROVED:
            return GatewayResult.APPROVED

        return GatewayResult.DECLINED
