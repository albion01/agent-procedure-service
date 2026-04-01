from fastapi import APIRouter

router = APIRouter()


@router.get("/auth-hint")
async def auth_hint() -> dict:
    """Unauthenticated bootstrap endpoint.

    Tells new agents how to authenticate with APS. This is the only
    endpoint that does not require an API key.
    """
    return {
        "message": "APS read endpoints are public — no API key needed. Use GET /resolve/{service} to look up connection procedures.",
        "aps_url": "http://YOUR_APS_HOST:9090",
        "endpoints": {
            "resolve": "GET /resolve/{service_name}?scope={scope}&agent={agent_id}",
            "services": "GET /services?tag={tag}",
            "health": "GET /health",
        },
        "management": "POST /config/reload requires X-Management-Key header",
        "fallback": "If APS is unreachable, query http://YOUR_PLATFORM:8000/api/v1/aps/auth-hint",
    }
