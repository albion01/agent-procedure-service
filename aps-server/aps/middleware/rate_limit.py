import asyncio
import logging
import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from aps.config import settings

logger = logging.getLogger("aps.middleware.rate_limit")

# Unauthenticated paths that get the stricter rate limit
UNAUTH_PATHS = {"/auth-hint", "/health"}

# Maximum tracked IPs to prevent memory exhaustion under DDoS
MAX_TRACKED_IPS = 10_000


class RateLimitState:
    """Shared rate limiting state. All access is from the async event loop so
    we use simple dicts rather than threading locks."""

    def __init__(self) -> None:
        # Per-IP sliding window: IP -> deque of request timestamps
        self.per_ip: dict[str, deque[float]] = {}
        # Global sliding window
        self.global_window: deque[float] = deque()
        # Ban list: IP -> ban expiry timestamp
        self.bans: dict[str, float] = {}
        # Violation counters: IP -> count of rate limit violations
        self.violations: dict[str, int] = {}
        # Metrics counters
        self.total_rejections: int = 0
        self.total_bans: int = 0

    def cleanup(self) -> None:
        """Remove stale entries older than 60 seconds and expired bans."""
        now = time.monotonic()
        cutoff = now - 60.0

        # Clean per-IP windows
        stale_ips = []
        for ip, window in self.per_ip.items():
            while window and window[0] < cutoff:
                window.popleft()
            if not window:
                stale_ips.append(ip)
        for ip in stale_ips:
            del self.per_ip[ip]

        # Clean global window
        while self.global_window and self.global_window[0] < cutoff:
            self.global_window.popleft()

        # Clean expired bans
        expired = [ip for ip, expiry in self.bans.items() if expiry <= now]
        for ip in expired:
            del self.bans[ip]
            self.violations.pop(ip, None)
            logger.info("Ban expired for IP %s", ip)

        # Clean violation counters for IPs no longer tracked
        stale_violations = [ip for ip in self.violations if ip not in self.per_ip and ip not in self.bans]
        for ip in stale_violations:
            del self.violations[ip]


_state = RateLimitState()
_cleanup_task: asyncio.Task | None = None


async def _periodic_cleanup() -> None:
    """Background task that runs cleanup every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        _state.cleanup()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware implementing per-IP and global rate limiting."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        global _cleanup_task

        # Start background cleanup task on first request
        if _cleanup_task is None or _cleanup_task.done():
            _cleanup_task = asyncio.create_task(_periodic_cleanup())

        now = time.monotonic()
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Check if IP is banned
        if client_ip in _state.bans:
            if _state.bans[client_ip] > now:
                remaining = int(_state.bans[client_ip] - now)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. You are temporarily banned."},
                    headers={"Retry-After": str(remaining)},
                )
            else:
                # Ban expired
                del _state.bans[client_ip]
                _state.violations.pop(client_ip, None)

        # Check global rate limit
        window_start = now - 60.0
        while _state.global_window and _state.global_window[0] < window_start:
            _state.global_window.popleft()

        if len(_state.global_window) >= settings.global_rate_limit:
            _state.total_rejections += 1
            return JSONResponse(
                status_code=503,
                content={"detail": "Service temporarily overloaded. Try again later."},
                headers={"Retry-After": "10"},
            )

        # DDoS protection: reject new IPs if tracking dict is full
        if client_ip not in _state.per_ip and len(_state.per_ip) >= MAX_TRACKED_IPS:
            _state.total_rejections += 1
            return JSONResponse(
                status_code=503,
                content={"detail": "Service temporarily overloaded. Try again later."},
                headers={"Retry-After": "30"},
            )

        # Per-IP rate limit check
        if client_ip not in _state.per_ip:
            _state.per_ip[client_ip] = deque()

        ip_window = _state.per_ip[client_ip]
        while ip_window and ip_window[0] < window_start:
            ip_window.popleft()

        # Determine the applicable rate limit
        if path in UNAUTH_PATHS:
            limit = settings.unauth_rate_limit
        else:
            limit = settings.per_ip_rate_limit

        if len(ip_window) >= limit:
            # Rate limit exceeded — record violation
            _state.violations[client_ip] = _state.violations.get(client_ip, 0) + 1
            _state.total_rejections += 1

            if _state.violations[client_ip] >= settings.ban_threshold:
                # Ban the IP
                _state.bans[client_ip] = now + settings.ban_duration_seconds
                _state.total_bans += 1
                logger.warning(
                    "IP %s banned for %d seconds after %d violations",
                    client_ip,
                    settings.ban_duration_seconds,
                    _state.violations[client_ip],
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. You are temporarily banned."},
                    headers={"Retry-After": str(settings.ban_duration_seconds)},
                )

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded."},
                headers={"Retry-After": "10"},
            )

        # Record this request
        ip_window.append(now)
        _state.global_window.append(now)

        response = await call_next(request)
        return response


def get_rate_limit_stats() -> dict:
    """Return current rate limiting statistics for the health endpoint."""
    return {
        "tracked_ips": len(_state.per_ip),
        "active_bans": len(_state.bans),
        "total_rejections": _state.total_rejections,
        "total_bans": _state.total_bans,
        "global_window_size": len(_state.global_window),
    }
