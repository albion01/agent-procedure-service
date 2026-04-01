import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from aps.auth import require_management_key
from aps.config import settings
from aps.integrity import compute_procedure_json, verify_hmac
from aps.models import ProceduresEnvelope
from aps.store import store

logger = logging.getLogger("aps.endpoints.config_reload")

router = APIRouter()


@router.post("/config/reload")
async def config_reload(
    envelope: ProceduresEnvelope,
    _key: bool = Depends(require_management_key),
) -> dict:
    """Accept a new procedures configuration from the CISO Platform.

    Validates the HMAC signature, atomically swaps the in-memory store,
    and persists the new config to disk.
    """
    # Step 1: Verify HMAC signature
    if not settings.hmac_secret:
        logger.error("HMAC secret not configured — cannot verify config integrity")
        raise HTTPException(
            status_code=503,
            detail="HMAC secret not configured. Cannot accept unsigned configurations.",
        )

    procedures_dicts = [p.model_dump() for p in envelope.procedures]
    procedures_json = compute_procedure_json(procedures_dicts)

    if not verify_hmac(procedures_json, envelope.hmac_signature, settings.hmac_secret):
        logger.error(
            "HMAC verification failed for config reload (version=%d, source=%s)",
            envelope.version,
            envelope.source,
        )
        raise HTTPException(
            status_code=400,
            detail="HMAC signature verification failed. Config rejected.",
        )

    # Step 2: Validate all procedures (Pydantic already validated the envelope,
    # but check for empty or duplicate service names)
    seen_names: set[str] = set()
    for proc in envelope.procedures:
        if not proc.service_name.strip():
            raise HTTPException(
                status_code=400,
                detail="Procedure with empty service_name found.",
            )
        lower_name = proc.service_name.lower()
        if lower_name in seen_names:
            logger.warning("Duplicate service_name '%s' in reload payload", proc.service_name)
        seen_names.add(lower_name)

    # Step 3: Atomically swap the store
    integrity_valid = store.reload(envelope)

    # Step 4: Persist to disk (atomic write)
    saved = store.save_to_disk(settings.procedures_file)
    if not saved:
        logger.error("Failed to persist config to disk after reload")

    metadata = store.get_metadata()

    logger.info(
        "Config reload complete: version=%d, procedures=%d, saved_to_disk=%s",
        envelope.version,
        len(envelope.procedures),
        saved,
    )

    return {
        "status": "reloaded",
        "version": metadata["version"],
        "procedure_count": metadata["procedure_count"],
        "api_key_count": metadata["api_key_count"],
        "integrity_valid": integrity_valid,
        "saved_to_disk": saved,
    }
