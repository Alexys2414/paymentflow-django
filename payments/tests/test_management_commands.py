from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from payments.models import PaymentRequest, PaymentStatus


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_creates_each_scenario_without_duplicates_on_replay(self) -> None:
        first_output = StringIO()
        call_command("seed_demo", stdout=first_output)

        payments = {
            payment.reference: payment
            for payment in PaymentRequest.objects.filter(reference__startswith="DEMO-")
        }
        self.assertEqual(len(payments), 5)
        self.assertEqual(payments["DEMO-APPROVED-001"].status, PaymentStatus.PAID)
        self.assertEqual(payments["DEMO-DECLINED-001"].status, PaymentStatus.FAILED)
        self.assertEqual(payments["DEMO-PENDING-001"].status, PaymentStatus.PENDING)
        self.assertEqual(payments["DEMO-EXPIRED-001"].status, PaymentStatus.EXPIRED)
        self.assertEqual(
            payments["DEMO-COMMUNICATION-001"].status,
            PaymentStatus.PENDING,
        )
        event_counts = {reference: payment.events.count() for reference, payment in payments.items()}

        second_output = StringIO()
        call_command("seed_demo", stdout=second_output)

        self.assertEqual(
            PaymentRequest.objects.filter(reference__startswith="DEMO-").count(),
            5,
        )
        for reference, expected_count in event_counts.items():
            self.assertEqual(payments[reference].events.count(), expected_count)
        self.assertIn("Datos de demostración disponibles.", first_output.getvalue())
        self.assertIn("Datos de demostración disponibles.", second_output.getvalue())
