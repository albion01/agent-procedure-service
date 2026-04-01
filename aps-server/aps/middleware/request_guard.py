import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from aps.config import settings

logger = logging.getLogger("aps.middleware.request_guard")


class RequestGuardMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces request size limits on POST requests."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        if request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    length = int(content_length)
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length header."},
                    )

                if length > settings.max_request_size_bytes:
                    client_ip = request.client.host if request.client else "unknown"
                    logger.warning(
                        "Rejected oversized POST from %s: %d bytes (limit: %d)",
                        client_ip,
                        length,
                        settings.max_request_size_bytes,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Payload too large. Maximum size is {settings.max_request_size_bytes} bytes."
                        },
                    )

        response = await call_next(request)
        return response
