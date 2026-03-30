from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    google_api_key: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_expiration_minutes: int
    redis_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
    )


settings = Settings()
