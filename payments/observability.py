"""Utilidades pequeñas para correlación de peticiones y logs estructurados."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> Token[str | None]:
    """Asocia una correlación a la ejecución actual."""
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Limpia la correlación al finalizar una petición."""
    _request_id.reset(token)


def get_request_id() -> str | None:
    """Devuelve la correlación activa, si existe."""
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Formatter JSON limitado deliberadamente a contexto técnico seguro."""

    safe_extra_fields = ("event", "payment_uuid", "payment_status")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        for field in self.safe_extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, default=str)
