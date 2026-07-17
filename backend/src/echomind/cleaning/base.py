"""Cleaner protocol, mutable per-run state, and safe trace helpers."""

from dataclasses import dataclass, field
from typing import ClassVar, Protocol

from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.schemas import (
    CleanedConversation,
    CleaningOperation,
    CleaningWarning,
)
from echomind.parsers.schemas import ParseWarning


class Cleaner(Protocol):
    cleaner_name: ClassVar[str]
    cleaner_version: ClassVar[str]
    enabled_by_default: ClassVar[bool]

    def is_enabled(self, options: CleaningOptions) -> bool: ...

    def apply(self, state: "CleaningState", options: CleaningOptions) -> int: ...


@dataclass
class CleaningState:
    source_filename: str
    file_hash: str
    parser_name: str
    parser_version: str
    input_message_count: int
    conversations: list[CleanedConversation]
    parser_warnings: list[ParseWarning]
    cleaning_warnings: list[CleaningWarning] = field(default_factory=list)
    per_cleaner_counts: dict[str, int] = field(default_factory=dict)


def append_operation(
    operations: list[CleaningOperation],
    operation: CleaningOperation,
) -> None:
    """Append one trace once; a repeated application cannot grow the list."""

    if operation not in operations:
        operations.append(operation)
