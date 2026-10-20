"""Contrato mínimo para las pasarelas de pago."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from payments.models import PaymentRequest


class GatewayResult(StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"


class GatewayCommunicationError(Exception):
    """La pasarela no pudo responder; el pago debe seguir pendiente."""


class PaymentGateway(Protocol):
    """Interfaz para cobrar una solicitud sin manejar datos de tarjeta."""

    def charge(self, payment: PaymentRequest) -> GatewayResult:
        """Intenta cobrar la solicitud y devuelve el resultado del proveedor."""
