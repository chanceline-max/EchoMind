"""Stable lowercase values stored by the stage-two models."""

from enum import Enum, StrEnum


def enum_values(enum_class: type[Enum]) -> list[str]:
    """Persist public enum values rather than Python member names."""

    return [str(member.value) for member in enum_class]


class FileType(StrEnum):
    JSON = "json"
    CSV = "csv"
    TEXT = "text"
    WEFLOW = "weflow"
    UNKNOWN = "unknown"


class SourceFileStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class MessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    SYSTEM = "system"
    RECALLED = "recalled"
    OTHER = "other"
    UNKNOWN = "unknown"


class EvidenceStance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class InsightType(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    PATTERN = "pattern"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    CONTRADICTION = "contradiction"
    CHANGE = "change"


class InsightStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class EvidenceState(StrEnum):
    VALID = "valid"
    PARTIAL = "partial"
    INVALID = "invalid"


class InsightRevisionAction(StrEnum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    RESTORED_TO_PROPOSED = "restored_to_proposed"
    RESTORED_TO_CONFIRMED = "restored_to_confirmed"
    EDITED = "edited"
    SUPERSEDED = "superseded"
    EVIDENCE_INVALIDATED = "evidence_invalidated"
    EVIDENCE_REVALIDATED = "evidence_revalidated"


class RevisionActorType(StrEnum):
    LOCAL_USER = "local_user"
    SYSTEM = "system"


class EvidenceInvalidationReason(StrEnum):
    SOURCE_MESSAGE_EXCLUDED = "source_message_excluded"
    SOURCE_MESSAGE_ARCHIVED = "source_message_archived"
    USER_MARKED_INVALID = "user_marked_invalid"
    SOURCE_MISSING = "source_missing"
    OTHER_SYSTEM_REASON = "other_system_reason"
