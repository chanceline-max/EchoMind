"""HTTP(S)-only URL placeholder replacement without network access."""

import re
from typing import ClassVar

from echomind.cleaning.base import CleaningState, append_operation
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.schemas import CleaningOperation

URL_PATTERN = re.compile(r"https?://[A-Za-z0-9][^\s<>\"']*")
TRAILING_PUNCTUATION = ".,!?;:，。！？；：)]}"


class UrlReplacementCleaner:
    cleaner_name: ClassVar[str] = "url_replacement"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = True

    def is_enabled(self, options: CleaningOptions) -> bool:
        return options.replace_urls

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        changed = 0
        for conversation in state.conversations:
            for message in conversation.cleaned_messages:
                count = 0

                def replace(match: re.Match[str]) -> str:
                    nonlocal count
                    value = match.group(0)
                    suffix_length = len(value) - len(value.rstrip(TRAILING_PUNCTUATION))
                    suffix = value[-suffix_length:] if suffix_length else ""
                    count += 1
                    return f"{options.url_placeholder}{suffix}"

                normalized = URL_PATTERN.sub(replace, message.normalized_content)
                if count == 0:
                    continue
                message.normalized_content = normalized
                append_operation(
                    message.cleaning_operations,
                    CleaningOperation(
                        cleaner_name=self.cleaner_name,
                        cleaner_version=self.cleaner_version,
                        operation_type="replace_urls",
                        changed_fields=["normalized_content"],
                        details={"replacement_count": count},
                    ),
                )
                changed += 1
        return changed
