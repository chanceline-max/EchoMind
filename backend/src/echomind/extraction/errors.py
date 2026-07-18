"""Safe stage-seven extraction errors that never carry message content."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID


class ExtractionErrorCode(StrEnum):
    INVALID_EXTRACTION_REQUEST = "invalid_extraction_request"
    CONVERSATION_NOT_FOUND = "conversation_not_found"
    CONVERSATION_ARCHIVED = "conversation_archived"
    PROFILE_OWNER_NOT_IDENTIFIED = "profile_owner_not_identified"
    MULTIPLE_PROFILE_OWNERS = "multiple_profile_owners"
    NO_ANALYZABLE_MESSAGES = "no_analyzable_messages"
    CONTEXT_WINDOW_CONFIGURATION_INVALID = "context_window_configuration_invalid"
    CONTEXT_WINDOW_TOO_LARGE = "context_window_too_large"
    PROVIDER_ERROR = "provider_error"
    CANDIDATE_BATCH_INVALID = "candidate_batch_invalid"
    CANDIDATE_EVIDENCE_MISSING = "candidate_evidence_missing"
    CANDIDATE_EVIDENCE_OUTSIDE_WINDOW = "candidate_evidence_outside_window"
    CANDIDATE_SEMANTIC_RULE_FAILED = "candidate_semantic_rule_failed"
    EVIDENCE_BINDING_FAILED = "evidence_binding_failed"
    PERSISTENCE_FAILED = "persistence_failed"
    EXTRACTION_STOPPED = "extraction_stopped"


class ExtractionError(Exception):
    """Controlled exception with a deliberately small public field set."""

    def __init__(
        self,
        error_code: ExtractionErrorCode | str,
        *,
        message: str,
        request_id: UUID | str,
        window_id: str | None = None,
        conversation_id: str | None = None,
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = ExtractionErrorCode(error_code)
        self.message = message
        self.request_id = str(request_id)
        self.window_id = window_id
        self.conversation_id = conversation_id
        self.recoverable = recoverable
        self.details = details or {}

    def __repr__(self) -> str:
        return (
            "ExtractionError("
            f"error_code={self.error_code.value!r}, request_id={self.request_id!r}, "
            f"window_id={self.window_id!r}, recoverable={self.recoverable!r})"
        )
