"""Middleware HTTP de correlación para trazabilidad local."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from payments.observability import reset_request_id, set_request_id


class RequestIDMiddleware:
    """Genera una correlación por petición y la devuelve al cliente."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = str(uuid.uuid4())
        request.request_id = request_id
        context_token = set_request_id(request_id)
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(context_token)
