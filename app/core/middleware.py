"""Shared middleware for the FastAPI application."""

import asyncio
import contextvars
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to hold the current request ID, accessible from logging filters.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a correlation request ID into every request/response cycle.

    * Reads ``X-Request-ID`` from the incoming request (reuses caller-supplied IDs).
    * Falls back to a generated UUID4 if the header is absent.
    * Stores the ID in a ``contextvars.ContextVar`` so logging filters can include it.
    * Adds ``X-Request-ID`` to every response header.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request timeout."""

    def __init__(self, app: FastAPI, timeout_seconds: int = 300) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        """Process request with timeout tracking."""
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "error": "Request timeout",
                    "detail": f"Request exceeded {self.timeout_seconds} seconds",
                },
            )


class RequestIDLogFilter(logging.Filter):
    """Logging filter that injects request_id from the ContextVar into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")  # type: ignore[attr-defined]
        return True
