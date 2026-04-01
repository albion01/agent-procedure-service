import json
import logging
import os
import tempfile
import threading
from pathlib import Path

from aps.config import settings
from aps.integrity import compute_procedure_json, verify_hmac
from aps.models import Procedure, ProceduresEnvelope

logger = logging.getLogger("aps.store")


class ProcedureStore:
    """In-memory procedure store with thread-safe atomic reloads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._procedures: dict[str, Procedure] = {}
        # API keys removed — all read endpoints are public
        self._version: int = 0
        self._generated_at: str = ""
        self._source: str = ""
        self._integrity_valid: bool = False
        self._envelope: ProceduresEnvelope | None = None

    def get(self, service_name: str) -> Procedure | None:
        """Look up a procedure by service name (case-insensitive). O(1)."""
        return self._procedures.get(service_name.lower())

    def get_scoped(self, service_name: str, scope: str | None = None) -> Procedure | None:
        """Look up a procedure with optional scope.

        If scope is provided, tries "{service_name}-{scope}" first,
        then falls back to "{service_name}".
        """
        if scope:
            scoped_key = f"{service_name}-{scope}".lower()
            scoped = self._procedures.get(scoped_key)
            if scoped is not None:
                return scoped
        return self._procedures.get(service_name.lower())

    def list_scopes(self, service_name: str) -> list[str]:
        """Return available scopes for a service.

        Finds all procedure keys matching "{service_name}-*" and returns
        the suffix portions as scope names.
        """
        prefix = f"{service_name}-".lower()
        scopes = []
        for key in self._procedures:
            if key.startswith(prefix):
                scope = key[len(prefix):]
                if scope:
                    scopes.append(scope)
        return sorted(scopes)

    def list_services(self, tag: str | None = None) -> list[str]:
        """Return list of active service names, optionally filtered by tag."""
        results = []
        for name, proc in self._procedures.items():
            if not proc.is_active:
                continue
            if tag is not None:
                if proc.tags and tag.lower() in [t.lower() for t in proc.tags]:
                    results.append(proc.service_name)
            else:
                results.append(proc.service_name)
        return sorted(results)

    def get_metadata(self) -> dict:
        """Return store metadata."""
        return {
            "version": self._version,
            "generated_at": self._generated_at,
            "source": self._source,
            "procedure_count": len(self._procedures),
            "api_key_count": 0,  # API keys removed — reads are public
            "integrity_valid": self._integrity_valid,
        }

    def reload(self, envelope: ProceduresEnvelope) -> bool:
        """Atomically replace all data from a validated envelope.

        Returns True if integrity check passed, False otherwise (data is still loaded).
        """
        # Build new dicts before acquiring the lock
        new_procedures: dict[str, Procedure] = {}
        for proc in envelope.procedures:
            key = proc.service_name.lower()
            if key in new_procedures:
                logger.warning(
                    "Duplicate service_name '%s' in envelope — last definition wins",
                    proc.service_name,
                )
            new_procedures[key] = proc

        # Verify integrity
        procedures_dicts = [p.model_dump() for p in envelope.procedures]
        procedures_json = compute_procedure_json(procedures_dicts)
        integrity_valid = False
        if settings.hmac_secret:
            integrity_valid = verify_hmac(
                procedures_json, envelope.hmac_signature, settings.hmac_secret
            )
            if not integrity_valid:
                logger.error(
                    "HMAC verification FAILED for envelope version %d", envelope.version
                )
        else:
            logger.warning("No HMAC secret configured — skipping integrity verification")

        # Atomic swap under lock
        with self._lock:
            self._procedures = new_procedures
            self._version = envelope.version
            self._generated_at = envelope.generated_at
            self._source = envelope.source
            self._integrity_valid = integrity_valid
            self._envelope = envelope

        logger.info(
            "Store reloaded: version=%d, procedures=%d, integrity=%s",
            envelope.version,
            len(new_procedures),
            "valid" if integrity_valid else "INVALID",
        )
        return integrity_valid

    def load_from_file(self, path: str) -> bool:
        """Load procedures from a JSON file on disk.

        Returns True if file was loaded successfully, False otherwise.
        """
        filepath = Path(path)
        if not filepath.exists():
            logger.warning("Procedures file not found: %s", path)
            return False

        try:
            raw = filepath.read_text(encoding="utf-8")
            data = json.loads(raw)
            envelope = ProceduresEnvelope.model_validate(data)
            self.reload(envelope)
            logger.info("Loaded procedures from file: %s", path)
            return True
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in procedures file %s: %s", path, exc)
            return False
        except Exception as exc:
            logger.error("Failed to load procedures from %s: %s", path, exc)
            return False

    def save_to_disk(self, path: str) -> bool:
        """Write the current envelope to a JSON file atomically.

        Uses write-to-temp, fsync, rename pattern for crash safety.
        Returns True on success, False on failure.
        """
        with self._lock:
            envelope = self._envelope

        if envelope is None:
            logger.warning("No envelope to save — store is empty")
            return False

        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Write to temporary file in the same directory (same filesystem for atomic rename)
            fd, tmp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=".procedures_",
                dir=str(filepath.parent),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(envelope.model_dump(), f, indent=2, sort_keys=True)
                    f.flush()
                    os.fsync(f.fileno())
                # Atomic rename
                os.replace(tmp_path, str(filepath))
                logger.info("Saved procedures to disk: %s", path)
                return True
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:
            logger.error("Failed to save procedures to %s: %s", path, exc)
            return False


# Singleton instance
store = ProcedureStore()
