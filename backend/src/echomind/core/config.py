"""Environment-backed application settings."""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="EchoMind API", validation_alias="APP_NAME")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    database_url: str = Field(
        default="sqlite:///./data/echomind.db",
        validation_alias="DATABASE_URL",
    )
    frontend_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        validation_alias="FRONTEND_ORIGINS",
    )
    import_max_file_bytes: int = Field(
        default=26_214_400,
        ge=1,
        validation_alias="IMPORT_MAX_FILE_BYTES",
    )
    import_max_conversations: int = Field(
        default=500,
        ge=1,
        validation_alias="IMPORT_MAX_CONVERSATIONS",
    )
    import_max_participants: int = Field(
        default=10_000,
        ge=1,
        validation_alias="IMPORT_MAX_PARTICIPANTS",
    )
    import_max_messages: int = Field(
        default=50_000,
        ge=1,
        validation_alias="IMPORT_MAX_MESSAGES",
    )
    import_max_message_characters: int = Field(
        default=100_000,
        ge=1,
        validation_alias="IMPORT_MAX_MESSAGE_CHARACTERS",
    )
    import_chunk_size_bytes: int = Field(
        default=65_536,
        ge=1,
        le=1_048_576,
        validation_alias="IMPORT_CHUNK_SIZE_BYTES",
    )
    import_max_metadata_bytes: int = Field(
        default=65_536,
        ge=1,
        validation_alias="IMPORT_MAX_METADATA_BYTES",
    )
    import_temp_root: str | None = Field(
        default=None,
        validation_alias="IMPORT_TEMP_ROOT",
    )

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = value.rstrip("/")
        if not normalized.startswith("/") or normalized == "":
            raise ValueError("API_V1_PREFIX must be a non-root absolute URL path")
        return normalized

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("DATABASE_URL must not be empty")
        return value

    @field_validator("frontend_origins")
    @classmethod
    def validate_frontend_origins(cls, origins: list[str]) -> list[str]:
        if not origins:
            raise ValueError("FRONTEND_ORIGINS must contain at least one exact origin")

        normalized_origins: list[str] = []
        for origin in origins:
            if "*" in origin:
                raise ValueError("FRONTEND_ORIGINS must not contain wildcards")

            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise ValueError("FRONTEND_ORIGINS entries must be exact HTTP(S) origins")

            normalized_origins.append(f"{parsed.scheme}://{parsed.netloc}")

        return list(dict.fromkeys(normalized_origins))


@lru_cache
def get_settings() -> Settings:
    """Load and cache process-wide settings without logging their values."""
    return Settings()
