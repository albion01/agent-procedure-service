import json
import logging
import threading
import urllib.request

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse

from aps.config import settings
from aps.integrity import compute_hmac
from aps.store import store

logger = logging.getLogger("aps.endpoints.resolve")


def _log_resolve_to_platform(service: str, scope: str | None, agent: str | None, resolved_name: str):
    """Fire-and-forget POST to Platform resolve log."""
    if not settings.platform_log_url:
        return
    try:
        data = json.dumps({
            "service": service, "scope": scope, "agent": agent,
            "resolved_name": resolved_name, "result": "ok",
        }).encode()
        req = urllib.request.Request(
            settings.platform_log_url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # fire and forget

router = APIRouter()


@router.get("/resolve/{service_name}")
async def resolve(
    service_name: str,
    background_tasks: BackgroundTasks,
    agent: str | None = Query(None, description="Agent ID requesting the procedure"),
    scope: str | None = Query(None, description="Scope to select a scoped procedure variant (e.g. 'certs' looks up '{service}-certs' first)"),
) -> dict:
    """Resolve a service name to its connection procedure.

    Returns the full procedure definition including URL, auth method,
    vault path, and step-by-step connection instructions.

    Public endpoint — no authentication required.

    If scope is provided, looks up "{service_name}-{scope}" first,
    falling back to "{service_name}" if no scoped record exists.
    """
    procedure = store.get_scoped(service_name, scope)

    if procedure is None or not procedure.is_active:
        raise HTTPException(
            status_code=404,
            detail=f"No active procedure found for service '{service_name}'"
            + (f" with scope '{scope}'" if scope else "") + ".",
        )

    # Check agent-level restrictions on the procedure
    if agent and procedure.allowed_agents is not None:
        if agent.lower() not in [a.lower() for a in procedure.allowed_agents]:
            logger.warning(
                "Agent '%s' denied access to service '%s' (allowed: %s)",
                agent,
                service_name,
                procedure.allowed_agents,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Agent '{agent}' is not authorized for service '{service_name}'.",
            )

    result = procedure.model_dump()

    # Log resolve to Platform (background, non-blocking)
    background_tasks.add_task(
        _log_resolve_to_platform, service_name, scope, agent, procedure.service_name
    )

    # Compute per-response integrity header
    headers = {}
    if settings.hmac_secret:
        response_json = json.dumps(result, sort_keys=True, separators=(",", ":"))
        integrity = compute_hmac(response_json, settings.hmac_secret)
        headers["X-APS-Integrity"] = integrity

    return JSONResponse(content=result, headers=headers)
