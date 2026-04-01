import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest

from aps.middleware.rate_limit import get_rate_limit_stats
from aps.store import store

router = APIRouter()

# Dedicated registry (avoids default process/platform collectors that add noise)
registry = CollectorRegistry()

# Counters
aps_requests_total = Counter(
    "aps_requests_total",
    "Total APS requests by endpoint and status",
    ["endpoint", "status"],
    registry=registry,
)

aps_rate_limit_rejections = Counter(
    "aps_rate_limit_rejections_total",
    "Total rate limit rejections",
    registry=registry,
)

aps_ip_bans = Counter(
    "aps_ip_bans_total",
    "Total IP bans issued",
    registry=registry,
)

# Gauges
aps_procedures_loaded = Gauge(
    "aps_procedures_loaded",
    "Number of procedures currently loaded",
    registry=registry,
)

aps_config_version = Gauge(
    "aps_config_version",
    "Current config version number",
    registry=registry,
)

aps_integrity_valid = Gauge(
    "aps_integrity_valid",
    "Whether the current config passed HMAC integrity verification (1=valid, 0=invalid)",
    registry=registry,
)

aps_uptime_seconds = Gauge(
    "aps_uptime_seconds",
    "Seconds since APS server started",
    registry=registry,
)

_start_time: float = time.time()


def set_metrics_start_time(t: float) -> None:
    """Allow main.py to set the authoritative start time."""
    global _start_time
    _start_time = t


def _refresh_gauges() -> None:
    """Update gauge values from current store and rate limit state."""
    metadata = store.get_metadata()
    aps_procedures_loaded.set(metadata["procedure_count"])
    aps_config_version.set(metadata["version"])
    aps_integrity_valid.set(1 if metadata["integrity_valid"] else 0)
    aps_uptime_seconds.set(round(time.time() - _start_time, 2))

    # Sync rate limit stats into counters
    rl_stats = get_rate_limit_stats()
    # Counters are monotonic — we set them to current totals via _value
    aps_rate_limit_rejections._value.set(rl_stats["total_rejections"])
    aps_ip_bans._value.set(rl_stats["total_bans"])


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus-compatible metrics endpoint."""
    _refresh_gauges()
    return generate_latest(registry).decode("utf-8")
