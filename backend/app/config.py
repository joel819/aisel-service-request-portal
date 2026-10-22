from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True)

    database_url: str
    jwt_secret: str = Field(min_length=16)
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_price_in: float | None = None
    llm_price_cached: float | None = None
    llm_price_out: float | None = None
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 2

    @field_validator("jwt_secret")
    @classmethod
    def reject_placeholder_secret(cls, value: str) -> str:
        if value.lower().startswith("change-me"):
            raise ValueError("JWT_SECRET is still the .env.example placeholder; generate a real one")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
