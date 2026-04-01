import time

from fastapi import APIRouter

from aps.middleware.rate_limit import get_rate_limit_stats
from aps.store import store

router = APIRouter()

# Set at import time; main.py sets START_TIME before routes are loaded,
# but we also capture here as a fallback.
_start_time = time.time()


def set_start_time(t: float) -> None:
    """Allow main.py to set the authoritative start time."""
    global _start_time
    _start_time = t


@router.get("/health")
async def health() -> dict:
    """Health check endpoint returning store metadata, uptime, and rate limit stats.

    Unauthenticated — intended for monitoring systems.
    """
    metadata = store.get_metadata()
    uptime_seconds = round(time.time() - _start_time, 2)

    return {
        "status": "healthy",
        "uptime_seconds": uptime_seconds,
        "store": metadata,
        "rate_limiting": get_rate_limit_stats(),
    }
