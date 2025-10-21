from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application runtime settings loaded from environment/.env."""

    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(default="sqlite:///./data.db", alias="DATABASE_URL")
    admin_host: str = Field(default="127.0.0.1", alias="ADMIN_HOST")
    admin_port: int = Field(default=8080, alias="ADMIN_PORT")
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )
