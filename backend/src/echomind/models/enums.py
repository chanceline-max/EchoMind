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
    SYSTEM = "system"
    RECALLED = "recalled"
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
