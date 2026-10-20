from django import template


register = template.Library()


@register.filter
def status_label(status: str) -> str:
    return {
        "PAID": "Completado",
        "PENDING": "Pendiente",
        "FAILED": "Fallido",
        "EXPIRED": "Expirado",
    }.get(status, status)


@register.filter
def event_explanation(event_type: str) -> str:
    return {
        "payment_request.created": "La solicitud se creó y está lista para procesarse.",
        "payment_request.status_changed": "El resultado de la pasarela actualizó el estado del pago.",
        "payment_request.expired": "El pago expiró antes de poder procesarse.",
        "payment.gateway_communication_failed": "La pasarela no respondió; el pago sigue pendiente.",
    }.get(event_type, "Se registró un evento técnico del pago.")


@register.filter
def money_eur(value: object) -> str:
    """Presenta importes persistidos con el formato monetario de España."""
    english_number = format(value, ",.2f")
    spanish_number = english_number.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{spanish_number} €"


@register.filter
def get_item(mapping: dict[str, object], key: str) -> object:
    return mapping.get(key, 0)
