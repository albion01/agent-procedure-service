import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from aps.config import settings
from aps.endpoints import auth_hint, config_reload, health, metrics, resolve, services
from aps.endpoints.health import set_start_time
from aps.endpoints.metrics import set_metrics_start_time
from aps.middleware.rate_limit import RateLimitMiddleware
from aps.middleware.request_guard import RequestGuardMiddleware
from aps.store import store

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("aps")

START_TIME = time.time()
set_start_time(START_TIME)
set_metrics_start_time(START_TIME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load procedures on startup."""
    loaded = store.load_from_file(settings.procedures_file)
    if loaded:
        meta = store.get_metadata()
        logger.info(
            "Loaded %d procedures (version %d) from %s",
            meta["procedure_count"],
            meta["version"],
            settings.procedures_file,
        )
    else:
        logger.warning(
            "No procedures loaded from %s — serving empty until config push",
            settings.procedures_file,
        )
    yield


app = FastAPI(
    title="Agent Procedure Service",
    version="1.0.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
    lifespan=lifespan,
)

# Middleware — outermost first (rate limiting before request guard)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestGuardMiddleware)

# Routes
app.include_router(auth_hint.router)
app.include_router(health.router)
app.include_router(resolve.router)
app.include_router(services.router)
app.include_router(config_reload.router)
app.include_router(metrics.router)
