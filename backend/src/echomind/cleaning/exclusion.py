"""Non-destructive, configuration-driven analysis exclusion."""

from typing import ClassVar

from echomind.cleaning.base import CleaningState, append_operation
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.schemas import CleaningOperation, ExclusionReason


class ExclusionCleaner:
    cleaner_name: ClassVar[str] = "exclusion"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = True

    def is_enabled(self, options: CleaningOptions) -> bool:
        return any(
            (
                options.exclude_system_messages,
                options.exclude_recalled_messages,
                options.exclude_duplicates,
                bool(options.excluded_source_message_ids),
            )
        )

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        changed = 0
        for conversation in state.conversations:
            for message in conversation.cleaned_messages:
                reasons: list[ExclusionReason] = []
                if options.exclude_system_messages and message.is_system_message:
                    reasons.append(ExclusionReason.SYSTEM_MESSAGE)
                if options.exclude_recalled_messages and message.is_recalled_message:
                    reasons.append(ExclusionReason.RECALLED_MESSAGE)
                if (
                    options.exclude_duplicates
                    and message.duplicate_of_source_message_id is not None
                ):
                    reasons.append(ExclusionReason.EXACT_DUPLICATE)
                if message.source_message_id in options.excluded_source_message_ids:
                    reasons.append(ExclusionReason.USER_EXCLUDED)
                if not reasons:
                    continue
                message.exclusion_reasons = reasons
                message.excluded_from_analysis = True
                append_operation(
                    message.cleaning_operations,
                    CleaningOperation(
                        cleaner_name=self.cleaner_name,
                        cleaner_version=self.cleaner_version,
                        operation_type="exclude_from_analysis",
                        changed_fields=["excluded_from_analysis", "exclusion_reasons"],
                        details={"rule": "configured_policy", "reason_count": len(reasons)},
                    ),
                )
                changed += 1
        return changed
