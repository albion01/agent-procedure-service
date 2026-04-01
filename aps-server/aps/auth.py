import hashlib
import hmac
import logging

from fastapi import Header, HTTPException, Request

from aps.config import settings

logger = logging.getLogger("aps.auth")


def _hash_key(raw_key: str) -> str:
    """Compute SHA-256 hex digest of a raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def require_management_key(
    request: Request,
    x_management_key: str | None = Header(None),
) -> bool:
    """FastAPI dependency: validate management API key for config operations.

    Compares SHA-256 hash of the provided key against settings.management_key_hash.
    """
    if x_management_key is None:
        logger.warning(
            "Missing X-Management-Key header from %s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=401,
            detail="Missing X-Management-Key header.",
        )

    if not settings.management_key_hash:
        logger.error("Management key hash not configured — rejecting all management requests")
        raise HTTPException(
            status_code=503,
            detail="Management endpoint not configured.",
        )

    provided_hash = _hash_key(x_management_key)
    if not hmac.compare_digest(provided_hash, settings.management_key_hash):
        logger.warning(
            "Invalid management key from %s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid management key.",
        )

    return True
