# Generated manually for the initial PaymentFlow domain model.

import django.core.validators
import django.db.models.deletion
import payments.models
import uuid
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PaymentRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                (
                    "public_token",
                    models.CharField(
                        default=payments.models.generate_public_token,
                        editable=False,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                ("currency", models.CharField(default="EUR", editable=False, max_length=3)),
                ("concept", models.CharField(max_length=255)),
                ("reference", models.CharField(max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pendiente"),
                            ("PAID", "Pagado"),
                            ("FAILED", "Fallido"),
                            ("EXPIRED", "Expirado"),
                        ],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "idempotency_key",
                    models.CharField(blank=True, max_length=255, null=True, unique=True),
                ),
                ("payload_hash", models.CharField(blank=True, max_length=64, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("event_type", models.CharField(max_length=64)),
                (
                    "previous_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("PENDING", "Pendiente"),
                            ("PAID", "Pagado"),
                            ("FAILED", "Fallido"),
                            ("EXPIRED", "Expirado"),
                        ],
                        max_length=10,
                        null=True,
                    ),
                ),
                (
                    "new_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("PENDING", "Pendiente"),
                            ("PAID", "Pagado"),
                            ("FAILED", "Fallido"),
                            ("EXPIRED", "Expirado"),
                        ],
                        max_length=10,
                        null=True,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "payment_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="payments.paymentrequest",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="paymentrequest",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)),
                name="payment_request_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentrequest",
            constraint=models.CheckConstraint(
                condition=models.Q(("currency", "EUR")),
                name="payment_request_currency_is_eur",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentrequest",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["PENDING", "PAID", "FAILED", "EXPIRED"])),
                name="payment_request_status_is_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentrequest",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("idempotency_key__isnull", True), ("payload_hash__isnull", True))
                    | models.Q(("idempotency_key__isnull", False), ("payload_hash__isnull", False))
                ),
                name="payment_request_idempotency_pair",
            ),
        ),
    ]
