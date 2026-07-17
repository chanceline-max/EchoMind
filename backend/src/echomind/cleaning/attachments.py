"""Deterministic placeholders for empty non-text messages."""

from typing import ClassVar

from echomind.cleaning.base import CleaningState, append_operation
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.schemas import CleaningOperation
from echomind.parsers.schemas import MessageType

ATTACHMENT_PLACEHOLDERS: dict[MessageType, str] = {
    MessageType.IMAGE: "[IMAGE]",
    MessageType.FILE: "[FILE]",
    MessageType.AUDIO: "[AUDIO]",
    MessageType.VIDEO: "[VIDEO]",
    MessageType.OTHER: "[ATTACHMENT]",
}


class AttachmentPlaceholderCleaner:
    cleaner_name: ClassVar[str] = "attachment_placeholders"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = True

    def is_enabled(self, options: CleaningOptions) -> bool:
        return options.add_attachment_placeholders

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        changed = 0
        for conversation in state.conversations:
            for message in conversation.cleaned_messages:
                placeholder = ATTACHMENT_PLACEHOLDERS.get(message.message_type)
                if placeholder is None or message.normalized_content.strip():
                    continue
                message.normalized_content = placeholder
                append_operation(
                    message.cleaning_operations,
                    CleaningOperation(
                        cleaner_name=self.cleaner_name,
                        cleaner_version=self.cleaner_version,
                        operation_type="add_attachment_placeholder",
                        changed_fields=["normalized_content"],
                        details={"placeholder": placeholder},
                    ),
                )
                changed += 1
        return changed
