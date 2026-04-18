from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from env vars prefixed with `LINKHOP_`.

    Fields that would otherwise produce awkwardly long env var names use an
    explicit `validation_alias` to pick a shorter operator-friendly name,
    while still allowing the Python attribute name as a fallback.
    """

    model_config = SettingsConfigDict(
        env_prefix="LINKHOP_",
        case_sensitive=False,
        populate_by_name=True,
    )

    database_url: str = "postgresql+asyncpg://linkhop:linkhop@localhost:5432/linkhop"
    redis_url: str = "redis://localhost:6379/0"

    rate_anonymous_per_minute: int = Field(
        default=20,
        validation_alias=AliasChoices(
            "LINKHOP_RATE_ANONYMOUS", "LINKHOP_RATE_ANONYMOUS_PER_MINUTE"
        ),
    )
    rate_with_key_per_minute: int = Field(
        default=300,
        validation_alias=AliasChoices(
            "LINKHOP_RATE_WITH_KEY", "LINKHOP_RATE_WITH_KEY_PER_MINUTE"
        ),
    )
    cache_ttl_seconds: int = Field(
        default=604800,
        validation_alias=AliasChoices("LINKHOP_CACHE_TTL", "LINKHOP_CACHE_TTL_SECONDS"),
    )

    enable_spotify: bool = True
    enable_deezer: bool = True
    enable_tidal: bool = True
    enable_youtube_music: bool = True

    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    tidal_client_id: str = ""
    tidal_client_secret: str = ""

    ytm_cookie_file: str = ""

    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"]
    )

    log_level: str = "INFO"

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v
