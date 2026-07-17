"""Stage-five import request options and response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from echomind.cleaning.options import RedactionCategory


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportCleaningOptions(ApiSchema):
    redact_sensitive_data: bool | None = None
    redaction_categories: set[RedactionCategory] | None = None
    exclude_system_messages: bool | None = None
    exclude_recalled_messages: bool | None = None
    exclude_duplicates: bool | None = None
    replace_urls: bool | None = None
    build_analysis_units: bool | None = None


class SafeWarning(ApiSchema):
    error_code: str
    message: str
    location: str | None = None


class ImportLinks(ApiSchema):
    self: str
    conversations: str


class ImportDetail(ApiSchema):
    source_file_id: str
    filename: str
    file_hash: str
    file_type: str
    byte_size: int
    parser_name: str
    parser_version: str
    cleaning_pipeline_version: str
    imported_at: datetime
    conversation_count: int
    participant_count: int
    message_count: int
    excluded_message_count: int
    analysis_unit_count: int
    parser_warning_count: int
    cleaning_warning_count: int
    warnings: list[SafeWarning] = Field(default_factory=list)
    links: ImportLinks


class ImportSummary(ApiSchema):
    source_file_id: str
    filename: str
    file_hash: str
    file_type: str
    imported_at: datetime
    parser_name: str
    parser_version: str
    cleaning_pipeline_version: str
    conversation_count: int
    participant_count: int
    message_count: int
    excluded_message_count: int
    warning_count: int


class ImportPage(ApiSchema):
    items: list[ImportSummary]
    total: int
    limit: int
    offset: int


def safe_metadata_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
