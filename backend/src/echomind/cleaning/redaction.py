"""Opt-in deterministic redaction for a deliberately small rule set."""

import re
from typing import ClassVar

from echomind.cleaning.base import CleaningState, append_operation
from echomind.cleaning.options import CleaningOptions, RedactionCategory
from echomind.cleaning.schemas import CleaningOperation

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+(?![\w.-])"
)
PHONE_PATTERN = re.compile(r"(?<![\w+])\+[1-9](?:[ -]?\d){7,14}(?![\w\d])")
OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IPV4_PATTERN = re.compile(rf"(?<![\d.]){OCTET}(?:\.{OCTET}){{3}}(?![\d.])")


class RedactionCleaner:
    cleaner_name: ClassVar[str] = "redaction"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = False

    def is_enabled(self, options: CleaningOptions) -> bool:
        return options.redact_sensitive_data

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        changed = 0
        configured_rules: list[tuple[str, re.Pattern[str], str]] = []
        if RedactionCategory.EMAIL in options.redaction_categories:
            configured_rules.append(("email", EMAIL_PATTERN, "[EMAIL]"))
        if RedactionCategory.PHONE_LIKE in options.redaction_categories:
            configured_rules.append(("phone_like", PHONE_PATTERN, "[PHONE]"))
        if RedactionCategory.IPV4 in options.redaction_categories:
            configured_rules.append(("ipv4", IPV4_PATTERN, "[IP]"))
        if RedactionCategory.CUSTOM in options.redaction_categories:
            configured_rules.extend(
                ("custom", re.compile(item.pattern), item.placeholder)
                for item in options.custom_redaction_patterns
            )

        for conversation in state.conversations:
            for message in conversation.cleaned_messages:
                normalized = message.normalized_content
                categories: list[str] = []
                replacement_count = 0
                for category, pattern, placeholder in configured_rules:
                    category_count = 0

                    def replace(_: re.Match[str], replacement: str = placeholder) -> str:
                        nonlocal category_count
                        category_count += 1
                        return replacement

                    normalized = pattern.sub(replace, normalized)
                    if category_count:
                        replacement_count += category_count
                        if category not in categories:
                            categories.append(category)
                if replacement_count == 0:
                    continue
                message.normalized_content = normalized
                append_operation(
                    message.cleaning_operations,
                    CleaningOperation(
                        cleaner_name=self.cleaner_name,
                        cleaner_version=self.cleaner_version,
                        operation_type="redact_sensitive_data",
                        changed_fields=["normalized_content"],
                        details={
                            "replacement_count": replacement_count,
                            "categories": categories,
                        },
                    ),
                )
                changed += 1
        return changed
