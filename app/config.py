from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    database_url: str
    google_api_key: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_expiration_minutes: int
    jwt_refresh_expiration_days: int = 7
    redis_url: str

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters long. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
    )


settings = Settings()