from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal

from django.test import TestCase

from payments.gateways.mock import MockPaymentGateway, MockPaymentOutcome
from payments.observability import JsonFormatter, reset_request_id, set_request_id
from payments.services.payments import (
    CreatePaymentRequestCommand,
    IdempotencyConflictError,
    InvalidPaymentTransitionError,
    create_payment_request,
    process_payment_request,
)


class JsonLoggingTests(TestCase):
    def test_json_formatter_includes_safe_correlation_context_only(self) -> None:
        context_token = set_request_id("correlation-test-1001")
        try:
            record = logging.LogRecord(
                name="payments.services.payments",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="payment_approved",
                args=(),
                exc_info=None,
            )
            record.event = "payment_approved"
            record.payment_uuid = "f61d9cda-1e78-4a3a-bdee-259514b29e93"
            record.payment_status = "PAID"
            record.idempotency_key = "must-not-appear-in-logs"
            record.password = "must-not-appear-in-logs"

            rendered = json.loads(JsonFormatter().format(record))
        finally:
            reset_request_id(context_token)

        self.assertEqual(rendered["request_id"], "correlation-test-1001")
        self.assertEqual(rendered["event"], "payment_approved")
        self.assertNotIn("idempotency_key", rendered)
        self.assertNotIn("password", rendered)

    def test_middleware_generates_request_id_header(self) -> None:
        response = self.client.get("/pay/not-a-real-token/")

        self.assertEqual(response.status_code, 404)
        uuid.UUID(response["X-Request-ID"])


class PaymentServiceLoggingTests(TestCase):
    def command(self, **overrides: object) -> CreatePaymentRequestCommand:
        values: dict[str, object] = {
            "amount": Decimal("25.00"),
            "concept": "Concepto que no debe entrar en logs",
            "reference": "OBS-1001",
            "idempotency_key": "observability-key-1001",
        }
        values.update(overrides)
        return CreatePaymentRequestCommand(**values)

    def create_payment(self, **overrides: object):
        return create_payment_request(self.command(**overrides)).payment

    def test_creation_log_does_not_contain_sensitive_payload(self) -> None:
        context_token = set_request_id("correlation-create-1001")
        try:
            with self.assertLogs("payments.services.payments", level="INFO") as logs:
                payment = self.create_payment()
        finally:
            reset_request_id(context_token)

        record = logs.records[0]
        self.assertEqual(record.event, "payment_request_created")
        self.assertEqual(record.payment_uuid, str(payment.uuid))
        self.assertNotIn("observability-key-1001", "\n".join(logs.output))
        self.assertNotIn("Concepto que no debe entrar en logs", "\n".join(logs.output))

    def test_approved_payment_is_logged_at_info(self) -> None:
        payment = self.create_payment()

        with self.assertLogs("payments.services.payments", level="INFO") as logs:
            process_payment_request(
                payment.pk,
                MockPaymentGateway(MockPaymentOutcome.APPROVED),
            )

        self.assertEqual(logs.records[0].levelno, logging.INFO)
        self.assertEqual(logs.records[0].event, "payment_approved")

    def test_rejected_payment_is_logged_at_warning(self) -> None:
        payment = self.create_payment()

        with self.assertLogs("payments.services.payments", level="WARNING") as logs:
            process_payment_request(
                payment.pk,
                MockPaymentGateway(MockPaymentOutcome.DECLINED),
            )

        self.assertEqual(logs.records[0].levelno, logging.WARNING)
        self.assertEqual(logs.records[0].event, "payment_rejected")

    def test_gateway_communication_error_is_logged_at_error(self) -> None:
        payment = self.create_payment()

        with self.assertLogs("payments.services.payments", level="ERROR") as logs:
            process_payment_request(
                payment.pk,
                MockPaymentGateway(MockPaymentOutcome.COMMUNICATION_ERROR),
            )

        self.assertEqual(logs.records[0].levelno, logging.ERROR)
        self.assertEqual(logs.records[0].event, "payment_gateway_communication_error")

    def test_idempotency_conflict_is_logged_at_warning(self) -> None:
        self.create_payment()

        with self.assertLogs("payments.services.payments", level="WARNING") as logs:
            with self.assertRaises(IdempotencyConflictError):
                self.create_payment(amount=Decimal("26.00"))

        self.assertEqual(logs.records[0].event, "payment_idempotency_conflict")

    def test_invalid_transition_is_logged_without_duplicate_audit_event(self) -> None:
        payment = self.create_payment()
        process_payment_request(
            payment.pk,
            MockPaymentGateway(MockPaymentOutcome.APPROVED),
        )
        self.assertEqual(payment.events.count(), 2)

        with self.assertLogs("payments.services.payments", level="WARNING") as logs:
            with self.assertRaises(InvalidPaymentTransitionError):
                process_payment_request(
                    payment.pk,
                    MockPaymentGateway(MockPaymentOutcome.APPROVED),
                )

        self.assertEqual(logs.records[0].event, "payment_invalid_transition")
        self.assertEqual(payment.events.count(), 2)
