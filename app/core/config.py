from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CommercePulse"
    app_env: str = "development"
    database_url: str = "sqlite:///./commercepulse.db"
    redis_url: str | None = None
    mongodb_url: str | None = None
    elasticsearch_url: str | None = None
    kafka_bootstrap_servers: str | None = None
    jwt_secret: str = "development-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_discovery_url: str = "https://accounts.google.com/.well-known/openid-configuration"
    oidc_redirect_uri: str = "http://localhost:8000/api/v1/auth/oidc/callback"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
