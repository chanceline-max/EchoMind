"""Conservative line-ending and whitespace normalization."""

import re
from typing import ClassVar

from echomind.cleaning.base import CleaningState, append_operation
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.schemas import CleaningOperation


class WhitespaceCleaner:
    cleaner_name: ClassVar[str] = "whitespace"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = True

    def is_enabled(self, options: CleaningOptions) -> bool:
        return options.normalize_line_endings or options.normalize_whitespace

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        changed = 0
        for conversation in state.conversations:
            for message in conversation.cleaned_messages:
                original = message.normalized_content
                normalized = original
                line_endings = 0
                trailing_lines = 0
                trimmed = 0
                collapsed_runs = 0

                if options.normalize_line_endings:
                    line_endings = normalized.count("\r\n") + len(
                        re.findall(r"\r(?!\n)", normalized)
                    )
                    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

                if options.normalize_whitespace:
                    trailing_lines = len(re.findall(r"[ \t]+(?=\n|$)", normalized))
                    normalized = re.sub(r"[ \t]+(?=\n|$)", "", normalized)
                    stripped = normalized.strip(" \t\n")
                    trimmed = len(normalized) - len(stripped)
                    normalized = stripped
                    maximum_newlines = options.max_consecutive_blank_lines + 1
                    pattern = rf"\n{{{maximum_newlines + 1},}}"
                    collapsed_runs = len(re.findall(pattern, normalized))
                    normalized = re.sub(pattern, "\n" * maximum_newlines, normalized)

                if normalized == original:
                    continue
                message.normalized_content = normalized
                append_operation(
                    message.cleaning_operations,
                    CleaningOperation(
                        cleaner_name=self.cleaner_name,
                        cleaner_version=self.cleaner_version,
                        operation_type="normalize_whitespace",
                        changed_fields=["normalized_content"],
                        details={
                            "line_ending_replacements": line_endings,
                            "trailing_whitespace_lines": trailing_lines,
                            "trimmed_boundary_characters": trimmed,
                            "collapsed_blank_line_runs": collapsed_runs,
                        },
                    ),
                )
                changed += 1
        return changed
