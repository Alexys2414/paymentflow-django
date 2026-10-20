from django import template


register = template.Library()


@register.filter
def status_label(status: str) -> str:
    return {
        "PAID": "Completed",
        "PENDING": "Pending",
        "FAILED": "Failed",
        "EXPIRED": "Expired",
    }.get(status, status)


@register.filter
def event_explanation(event_type: str) -> str:
    return {
        "payment_request.created": "The request was created and is ready to process.",
        "payment_request.status_changed": "The gateway result updated the payment state.",
        "payment_request.expired": "The payment expired before it could be processed.",
        "payment.gateway_communication_failed": "The gateway did not respond; payment remains pending.",
    }.get(event_type, "A technical payment event was recorded.")


@register.filter
def get_item(mapping: dict[str, object], key: str) -> object:
    return mapping.get(key, 0)
