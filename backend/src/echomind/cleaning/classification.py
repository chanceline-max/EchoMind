"""Strict, deterministic system and recalled-message classifiers."""

import re
from typing import ClassVar

from echomind.cleaning.base import CleaningState, append_operation
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.schemas import CleaningOperation
from echomind.parsers.schemas import MessageType

SYSTEM_EXACT_TEXTS = frozenset({"[SYSTEM]"})
ENGLISH_RECALLED = re.compile(r"(?:You|[A-Za-z][A-Za-z0-9 ._'-]{0,79}) recalled a message")
CHINESE_RECALLED = re.compile(r"(?:[\w\u3400-\u9fff·]{1,40})?撤回了一条消息")


class SystemMessageClassifier:
    cleaner_name: ClassVar[str] = "system_classification"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = True

    def is_enabled(self, options: CleaningOptions) -> bool:
        return options.classify_system_messages

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        changed = 0
        for conversation in state.conversations:
            for message in conversation.cleaned_messages:
                rule: str | None = None
                if message.message_type is MessageType.SYSTEM:
                    rule = "message_type"
                elif message.metadata_json.get("is_system_message") is True:
                    rule = "metadata:is_system_message"
                elif message.metadata_json.get("system_message") is True:
                    rule = "metadata:system_message"
                elif message.normalized_content in SYSTEM_EXACT_TEXTS:
                    rule = "exact_text:[SYSTEM]"
                if rule is None or message.is_system_message:
                    continue
                message.is_system_message = True
                append_operation(
                    message.cleaning_operations,
                    CleaningOperation(
                        cleaner_name=self.cleaner_name,
                        cleaner_version=self.cleaner_version,
                        operation_type="classify_system_message",
                        changed_fields=["is_system_message"],
                        details={"rule": rule},
                    ),
                )
                changed += 1
        return changed


class RecalledMessageClassifier:
    cleaner_name: ClassVar[str] = "recalled_classification"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = True

    def is_enabled(self, options: CleaningOptions) -> bool:
        return options.classify_recalled_messages

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        changed = 0
        for conversation in state.conversations:
            for message in conversation.cleaned_messages:
                content = message.normalized_content
                rule: str | None = None
                if ENGLISH_RECALLED.fullmatch(content):
                    rule = "english_recalled_placeholder"
                elif CHINESE_RECALLED.fullmatch(content):
                    rule = "chinese_recalled_placeholder"
                if rule is None or message.is_recalled_message:
                    continue
                message.is_recalled_message = True
                append_operation(
                    message.cleaning_operations,
                    CleaningOperation(
                        cleaner_name=self.cleaner_name,
                        cleaner_version=self.cleaner_version,
                        operation_type="classify_recalled_message",
                        changed_fields=["is_recalled_message"],
                        details={"rule": rule},
                    ),
                )
                changed += 1
        return changed
