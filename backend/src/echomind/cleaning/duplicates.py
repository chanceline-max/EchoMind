"""Exact, conversation-local duplicate message marking."""

from typing import ClassVar

from echomind.cleaning.base import CleaningState, append_operation
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.schemas import CleaningOperation


class ExactDuplicateCleaner:
    cleaner_name: ClassVar[str] = "exact_duplicates"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = True

    def is_enabled(self, options: CleaningOptions) -> bool:
        return options.detect_exact_duplicates

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        changed = 0
        for conversation in state.conversations:
            first_by_key: dict[tuple[object, ...], str] = {}
            for message in conversation.cleaned_messages:
                key = (
                    message.sender_source_id,
                    message.message_type,
                    message.normalized_content,
                    message.timestamp,
                    message.reply_to_source_message_id,
                )
                first_id = first_by_key.get(key)
                if first_id is None:
                    first_by_key[key] = message.source_message_id
                    continue
                message.duplicate_of_source_message_id = first_id
                append_operation(
                    message.cleaning_operations,
                    CleaningOperation(
                        cleaner_name=self.cleaner_name,
                        cleaner_version=self.cleaner_version,
                        operation_type="mark_exact_duplicate",
                        changed_fields=["duplicate_of_source_message_id"],
                        details={"rule": "exact_match"},
                    ),
                )
                changed += 1
        return changed
