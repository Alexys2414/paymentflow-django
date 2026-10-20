from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from payments.gateways.base import GatewayCommunicationError, GatewayResult
from payments.gateways.mock import MockPaymentGateway, MockPaymentOutcome
from payments.models import PaymentRequest


class MockPaymentGatewayTests(SimpleTestCase):
    def setUp(self) -> None:
        self.payment = PaymentRequest(
            amount=Decimal("10.00"),
            concept="Prueba",
            reference="GATEWAY-1",
        )

    def test_returns_approved_outcome(self) -> None:
        gateway = MockPaymentGateway(MockPaymentOutcome.APPROVED)

        self.assertEqual(gateway.charge(self.payment), GatewayResult.APPROVED)

    def test_returns_declined_outcome(self) -> None:
        gateway = MockPaymentGateway(MockPaymentOutcome.DECLINED)

        self.assertEqual(gateway.charge(self.payment), GatewayResult.DECLINED)

    def test_raises_for_communication_error(self) -> None:
        gateway = MockPaymentGateway(MockPaymentOutcome.COMMUNICATION_ERROR)

        with self.assertRaises(GatewayCommunicationError):
            gateway.charge(self.payment)
