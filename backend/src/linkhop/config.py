from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LINKHOP_", case_sensitive=False)

    database_url: str = Field(default="postgresql+asyncpg://linkhop:linkhop@localhost:5432/linkhop")
    redis_url: str = Field(default="redis://localhost:6379/0")

    rate_anonymous_per_minute: int = Field(default=20, alias="LINKHOP_RATE_ANONYMOUS")
    rate_with_key_per_minute: int = Field(default=300, alias="LINKHOP_RATE_WITH_KEY")

    cache_ttl_seconds: int = Field(default=604800, alias="LINKHOP_CACHE_TTL")

    enable_spotify: bool = True
    enable_deezer: bool = True
    enable_tidal: bool = True
    enable_youtube_music: bool = True

    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    tidal_client_id: str = ""
    tidal_client_secret: str = ""

    ytm_cookie_file: str = ""

    cors_allow_origins: str = "*"

    log_level: str = "INFO"
