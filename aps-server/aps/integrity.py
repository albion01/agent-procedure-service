import hashlib
import hmac
import json


def compute_hmac(procedures_json: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature over procedures JSON string."""
    return hmac.new(
        secret.encode("utf-8"),
        procedures_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_hmac(procedures_json: str, signature: str, secret: str) -> bool:
    """Timing-safe HMAC verification."""
    expected = compute_hmac(procedures_json, secret)
    return hmac.compare_digest(expected, signature)


def compute_procedure_json(procedures: list[dict]) -> str:
    """Serialize procedures list to canonical JSON for HMAC computation.

    Uses sorted keys and no extra whitespace to ensure deterministic output.
    """
    return json.dumps(procedures, sort_keys=True, separators=(",", ":"))
