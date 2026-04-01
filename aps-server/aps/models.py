from pydantic import BaseModel


class Procedure(BaseModel):
    service_name: str
    display_name: str
    url: str
    service_type: str = "api"
    auth_method: str
    vault_secret_path: str | None = None
    auth_details: dict | None = None
    procedure_steps: list[str]
    restrictions: list[str] | None = None
    change_record_required: bool = False
    change_record_notes: str | None = None
    allowed_agents: list[str] | None = None
    tags: list[str] | None = None
    is_active: bool = True
    notes: str | None = None


class ProceduresEnvelope(BaseModel):
    version: int
    generated_at: str
    source: str
    hmac_signature: str  # HMAC-SHA256 hex digest
    procedures: list[Procedure]
