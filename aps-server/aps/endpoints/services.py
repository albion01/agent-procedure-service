import logging

from fastapi import APIRouter, Query

from aps.store import store

logger = logging.getLogger("aps.endpoints.services")

router = APIRouter()


@router.get("/services")
async def list_services(
    tag: str | None = Query(None, description="Filter services by tag"),
) -> dict:
    """List all available service names, optionally filtered by tag.

    Public endpoint — no authentication required.
    Returns services with their available scopes.
    """
    all_services = store.list_services(tag=tag)

    # Build response with scopes per service
    services_with_scopes = []
    for svc in all_services:
        scopes = store.list_scopes(svc)
        entry: dict = {"name": svc}
        if scopes:
            entry["scopes"] = scopes
        services_with_scopes.append(entry)

    return {"services": services_with_scopes}
