"""Message query and analysis-exclusion schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MessageSummary(ApiSchema):
    id: str
    conversation_id: str
    source_message_id: str
    sender_id: str
    sender_display_name: str
    timestamp: datetime | None
    message_type: str
    raw_content: str
    normalized_content: str
    reply_to_message_id: str | None
    source_order: int
    is_system_message: bool
    is_recalled_message: bool
    duplicate_of_message_id: str | None
    excluded_from_analysis: bool
    exclusion_reasons: list[str]


class MessagePage(ApiSchema):
    items: list[MessageSummary]
    total: int
    limit: int
    offset: int


class AnalysisExclusionRequest(ApiSchema):
    excluded: bool
