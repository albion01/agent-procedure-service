from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APS_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 9090

    procedures_file: str = "data/procedures.json"

    # HMAC shared secret for config integrity verification
    hmac_secret: str = ""

    # Management API key hash (SHA-256) for config reload endpoint
    management_key_hash: str = ""

    # Rate limiting
    per_ip_rate_limit: int = 30       # requests/minute per IP
    global_rate_limit: int = 300      # requests/minute total
    unauth_rate_limit: int = 10       # requests/minute for unauthenticated endpoints
    ban_threshold: int = 5            # violations before temp ban
    ban_duration_seconds: int = 300   # 5 minute ban

    # Request guards
    max_request_size_bytes: int = 1_048_576  # 1MB
    request_timeout_seconds: int = 10

    # Resolve log callback — POST resolves to Platform for the Resolve Log tab
    platform_log_url: str = ""  # e.g. http://YOUR_PLATFORM:8000/api/v1/aps/log/

    # Debug
    enable_docs: bool = False  # Swagger/OpenAPI disabled in production


settings = Settings()
