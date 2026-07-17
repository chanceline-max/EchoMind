"""Environment-backed application settings."""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
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
    llm_provider: str = Field(default="mock", validation_alias="LLM_PROVIDER")
    llm_remote_enabled: bool = Field(
        default=False,
        validation_alias="LLM_REMOTE_ENABLED",
    )
    llm_openai_compatible_endpoint: str | None = Field(
        default=None,
        validation_alias="LLM_OPENAI_COMPATIBLE_ENDPOINT",
    )
    llm_openai_compatible_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="LLM_OPENAI_COMPATIBLE_API_KEY",
    )
    llm_openai_compatible_model: str | None = Field(
        default=None,
        validation_alias="LLM_OPENAI_COMPATIBLE_MODEL",
    )
    llm_request_timeout_seconds: float = Field(
        default=30,
        gt=0,
        le=300,
        validation_alias="LLM_REQUEST_TIMEOUT_SECONDS",
    )
    llm_connect_timeout_seconds: float = Field(
        default=5,
        gt=0,
        le=60,
        validation_alias="LLM_CONNECT_TIMEOUT_SECONDS",
    )
    llm_read_timeout_seconds: float = Field(
        default=30,
        gt=0,
        le=300,
        validation_alias="LLM_READ_TIMEOUT_SECONDS",
    )
    llm_max_retries: int = Field(default=2, ge=0, le=5, validation_alias="LLM_MAX_RETRIES")
    llm_verify_tls: bool = Field(default=True, validation_alias="LLM_VERIFY_TLS")
    llm_allow_insecure_local_http: bool = Field(
        default=False,
        validation_alias="LLM_ALLOW_INSECURE_LOCAL_HTTP",
    )
    llm_max_input_characters: int = Field(
        default=100_000,
        ge=1,
        le=10_000_000,
        validation_alias="LLM_MAX_INPUT_CHARACTERS",
    )
    llm_max_messages: int = Field(
        default=100,
        ge=1,
        le=10_000,
        validation_alias="LLM_MAX_MESSAGES",
    )
    llm_max_message_characters: int = Field(
        default=20_000,
        ge=1,
        le=1_000_000,
        validation_alias="LLM_MAX_MESSAGE_CHARACTERS",
    )
    llm_max_schema_characters: int = Field(
        default=50_000,
        ge=1,
        le=1_000_000,
        validation_alias="LLM_MAX_SCHEMA_CHARACTERS",
    )
    llm_max_output_tokens: int = Field(
        default=4_096,
        ge=1,
        le=100_000,
        validation_alias="LLM_MAX_OUTPUT_TOKENS",
    )
    llm_max_response_bytes: int = Field(
        default=1_048_576,
        ge=1_024,
        le=16_777_216,
        validation_alias="LLM_MAX_RESPONSE_BYTES",
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

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        if value not in {"mock", "openai_compatible", "local"}:
            raise ValueError("LLM_PROVIDER must name a built-in provider")
        return value

    @field_validator(
        "llm_openai_compatible_endpoint",
        "llm_openai_compatible_model",
        mode="before",
    )
    @classmethod
    def empty_llm_strings_are_unset(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("llm_openai_compatible_api_key", mode="before")
    @classmethod
    def empty_llm_key_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_llm_security_settings(self) -> "Settings":
        endpoint = self.llm_openai_compatible_endpoint
        if endpoint is not None:
            if not endpoint or len(endpoint) > 2_048:
                raise ValueError("LLM endpoint length is invalid")
            parsed = urlsplit(endpoint)
            if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
                raise ValueError("LLM endpoint must be an absolute HTTP(S) URL")
            if parsed.username is not None or parsed.password is not None or parsed.fragment:
                raise ValueError("LLM endpoint contains forbidden URL components")
            if parsed.scheme == "http" and (
                not self.llm_allow_insecure_local_http
                or parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError("HTTP LLM endpoints require explicit localhost permission")
            if not self.llm_verify_tls and parsed.hostname.casefold() not in {
                "localhost",
                "127.0.0.1",
                "::1",
            }:
                raise ValueError("TLS verification can only be disabled for localhost")
        if self.llm_max_message_characters > self.llm_max_input_characters:
            raise ValueError("LLM_MAX_MESSAGE_CHARACTERS must not exceed input budget")
        return self


@lru_cache
def get_settings() -> Settings:
    """Load and cache process-wide settings without logging their values."""
    return Settings()
