"""Safe confidence errors with a closed public field set."""

from enum import StrEnum
from typing import Any


class ConfidenceErrorCode(StrEnum):
    INVALID_CONFIDENCE_REQUEST = "invalid_confidence_request"
    UNSUPPORTED_CONFIDENCE_VERSION = "unsupported_confidence_version"
    INSIGHT_NOT_FOUND = "insight_not_found"
    INSIGHT_STATUS_SKIPPED = "insight_status_skipped"
    CONFIDENCE_DATA_INCONSISTENT = "confidence_data_inconsistent"
    PROFILE_OWNER_INCONSISTENT = "profile_owner_inconsistent"
    EVIDENCE_TIMESTAMP_INVALID = "evidence_timestamp_invalid"
    EVIDENCE_AFTER_AS_OF = "evidence_after_as_of"
    EVIDENCE_SCORE_INVALID = "evidence_score_invalid"
    MINIMUM_RULE_FAILED = "minimum_rule_failed"
    CONTRADICTION_ROLES_INCOMPLETE = "contradiction_roles_incomplete"
    PERSISTENCE_FAILED = "persistence_failed"
    CONFIDENCE_STOPPED = "confidence_stopped"


class ConfidenceError(Exception):
    def __init__(
        self,
        error_code: ConfidenceErrorCode | str,
        *,
        message: str,
        request_id: str,
        insight_id: str | None = None,
        recoverable: bool = False,
        details: dict[str, str | int | float | bool] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = ConfidenceErrorCode(error_code)
        self.message = message
        self.request_id = request_id
        self.insight_id = insight_id
        self.recoverable = recoverable
        self.details = details or {}

    def as_safe_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "request_id": self.request_id,
            "insight_id": self.insight_id,
            "recoverable": self.recoverable,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return (
            "ConfidenceError("
            f"error_code={self.error_code.value!r}, request_id={self.request_id!r}, "
            f"insight_id={self.insight_id!r}, recoverable={self.recoverable!r})"
        )
