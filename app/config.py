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