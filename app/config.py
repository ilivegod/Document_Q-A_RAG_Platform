from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import Self


class Settings(BaseSettings):
    database_url: str
    google_api_key: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_expiration_minutes: int
    jwt_refresh_expiration_days: int = 7
    redis_url: str
    cors_origins: str = "http://localhost:3000"

    # Email / Resend
    resend_api_key: str
    email_from: str = "onboarding@resend.dev"
    frontend_url: str = "http://localhost:3000"
    password_reset_ttl_minutes: int = 30
    email_verification_ttl_hours: int = 24

    # Sentry. All optional — if sentry_dsn is empty, Sentry init is skipped.
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 1.0

    # Cloudflare R2 object storage.
    # All optional — if r2_bucket_name is empty, storage falls back to local
    # disk (dev mode). In production all four must be set.
    r2_bucket_name: str = ""
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""

    # Stripe (optional — billing disabled when empty)
    stripe_secret_key: str = ""
    stripe_price_id_pro: str = ""
    stripe_webhook_secret: str = ""

    # Closed beta: manual admin approval before login; all agent tools unlocked
    closed_beta_enabled: bool = True
    admin_email: str = ""
    admin_approval_ttl_days: int = 7
    api_public_url: str = "http://localhost:8000"

    # MCP web research (DuckDuckGo + Wikipedia stdio servers)
    mcp_web_enabled: bool = False
    mcp_ddg_command: str = "python"
    mcp_ddg_args: str = "-m,duckduckgo_mcp.server"
    mcp_wiki_command: str = "wiki-mcp"
    mcp_wiki_args: str = ""
    mcp_tool_timeout_seconds: int = 45
    web_research_max_results: int = 5
    web_research_limit: str = "10/day"

    @property
    def mcp_ddg_args_list(self) -> list[str]:
        return [a.strip() for a in self.mcp_ddg_args.split(",") if a.strip()]

    @property
    def mcp_wiki_args_list(self) -> list[str]:
        return [a.strip() for a in self.mcp_wiki_args.split(",") if a.strip()]

    @property
    def is_production(self) -> bool:
        return self.sentry_environment == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS env var into a list."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @field_validator("google_api_key")
    @classmethod
    def google_api_key_format(cls, v: str) -> str:
        """Warn when the key is not a Google AI Studio API key (AIza...)."""
        if v in ("test-key", "your_google_api_key_here"):
            return v
        if not v.startswith("AIza"):
            import logging

            logging.getLogger(__name__).warning(
                "GOOGLE_API_KEY does not look like a Google AI Studio key "
                "(expected AIza...). Get one at https://aistudio.google.com/apikey"
            )
        return v

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters long. "
                "Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return v

    @model_validator(mode="after")
    def production_checks(self) -> Self:
        """Reject dangerous misconfigurations when running in production.

        Uses sentry_environment == "production" as the production signal —
        it's the one variable you must set when deploying, so it's a
        reliable sentinel.
        """
        if not self.is_production:
            return self

        # 1. Reject wildcard CORS in production.
        if "*" in self.cors_origins_list:
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' in production. "
                "Set it to your actual frontend domain, e.g. "
                "https://docqa.yourdomain.com"
            )

        # 2. Reject localhost in CORS in production.
        if any("localhost" in o or "127.0.0.1" in o for o in self.cors_origins_list):
            raise ValueError(
                "CORS_ORIGINS contains localhost in production. "
                "Set it to your actual frontend domain."
            )

        # 3. Reject obviously weak or placeholder JWT secrets in production.
        _weak_patterns = (
            "secret", "changeme", "your_jwt",
            "example", "placeholder", "dev", "test",
        )
        if any(p in self.jwt_secret.lower() for p in _weak_patterns):
            raise ValueError(
                "JWT_SECRET looks like a placeholder. "
                "Generate a strong secret with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )

        # 4. Warn if traces sample rate is 1.0 in production — will exhaust
        #    Sentry's free tier quota quickly.
        if self.sentry_dsn and self.sentry_traces_sample_rate >= 1.0:
            import logging
            logging.getLogger(__name__).warning(
                "SENTRY_TRACES_SAMPLE_RATE is 1.0 in production. "
                "Consider lowering to 0.1 to avoid exhausting the free tier."
            )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
    )


settings = Settings()