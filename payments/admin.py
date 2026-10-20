"""Configuración de lectura del dominio de pagos en Django Admin."""

from django.contrib import admin

from payments.models import PaymentEvent, PaymentRequest


class PaymentEventInline(admin.TabularInline):
    model = PaymentEvent
    extra = 0
    can_delete = False
    readonly_fields = (
        "event_type",
        "previous_status",
        "new_status",
        "metadata",
        "created_at",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "concept", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("reference", "concept", "uuid")
    readonly_fields = (
        "uuid",
        "public_token",
        "amount",
        "currency",
        "concept",
        "reference",
        "status",
        "expires_at",
        "idempotency_key",
        "payload_hash",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields
    inlines = (PaymentEventInline,)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "payment_request", "previous_status", "new_status", "created_at")
    list_filter = ("event_type", "previous_status", "new_status", "created_at")
    search_fields = ("payment_request__reference", "payment_request__uuid")
    readonly_fields = (
        "payment_request",
        "event_type",
        "previous_status",
        "new_status",
        "metadata",
        "created_at",
    )
    fields = readonly_fields

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
