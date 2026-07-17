"""Fixed, deterministic stage-four cleaning pipeline."""

from copy import deepcopy
from typing import Final

from echomind.cleaning.analysis_units import (
    AnalysisUnitCleaner,
    derive_analysis_unit_id,
)
from echomind.cleaning.attachments import AttachmentPlaceholderCleaner
from echomind.cleaning.base import Cleaner, CleaningState
from echomind.cleaning.classification import (
    RecalledMessageClassifier,
    SystemMessageClassifier,
)
from echomind.cleaning.duplicates import ExactDuplicateCleaner
from echomind.cleaning.errors import CleaningError, CleaningErrorCode
from echomind.cleaning.exclusion import ExclusionCleaner
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.redaction import RedactionCleaner
from echomind.cleaning.schemas import (
    CleanedChatFile,
    CleanedConversation,
    CleanedMessage,
    CleaningStatistics,
)
from echomind.cleaning.urls import UrlReplacementCleaner
from echomind.cleaning.whitespace import WhitespaceCleaner
from echomind.parsers.schemas import ParsedChatFile

CLEANING_PIPELINE_VERSION: Final = "1.0"
CLEANER_ORDER: Final = (
    "whitespace",
    "attachment_placeholders",
    "system_classification",
    "recalled_classification",
    "exact_duplicates",
    "url_replacement",
    "redaction",
    "exclusion",
    "analysis_units",
)
DEFAULT_CLEANERS: tuple[Cleaner, ...] = (
    WhitespaceCleaner(),
    AttachmentPlaceholderCleaner(),
    SystemMessageClassifier(),
    RecalledMessageClassifier(),
    ExactDuplicateCleaner(),
    UrlReplacementCleaner(),
    RedactionCleaner(),
    ExclusionCleaner(),
    AnalysisUnitCleaner(),
)


def _initialize_state(source: ParsedChatFile) -> CleaningState:
    conversations: list[CleanedConversation] = []
    for conversation in source.conversations:
        messages = [
            CleanedMessage(
                source_message_id=message.source_message_id,
                sender_source_id=message.sender_source_id,
                timestamp=message.timestamp,
                message_type=message.message_type,
                raw_content=message.raw_content,
                normalized_content=message.raw_content,
                reply_to_source_message_id=message.reply_to_source_message_id,
                source_order=message.source_order,
                source_location=message.source_location,
                metadata_json=deepcopy(message.metadata_json),
            )
            for message in conversation.messages
        ]
        conversations.append(
            CleanedConversation(
                source_conversation_id=conversation.source_conversation_id,
                platform=conversation.platform,
                title=conversation.title,
                started_at=conversation.started_at,
                ended_at=conversation.ended_at,
                time_range_derived=conversation.time_range_derived,
                participants=[item.model_copy(deep=True) for item in conversation.participants],
                cleaned_messages=messages,
                analysis_units=[],
                metadata_json=deepcopy(conversation.metadata_json),
            )
        )
    return CleaningState(
        source_filename=source.source_filename,
        file_hash=source.file_hash,
        parser_name=source.parser_name,
        parser_version=source.parser_version,
        input_message_count=sum(len(item.messages) for item in source.conversations),
        conversations=conversations,
        parser_warnings=[item.model_copy(deep=True) for item in source.warnings],
    )


def _operation_count(message: CleanedMessage, cleaner_name: str) -> int:
    return sum(item.cleaner_name == cleaner_name for item in message.cleaning_operations)


def _replacement_total(message: CleanedMessage, cleaner_name: str) -> int:
    total = 0
    for item in message.cleaning_operations:
        value = item.details.get("replacement_count", 0)
        if item.cleaner_name == cleaner_name and isinstance(value, int):
            total += value
    return total


def _statistics(
    conversations: list[CleanedConversation],
    input_message_count: int,
    warning_count: int,
    per_cleaner_counts: dict[str, int],
) -> CleaningStatistics:
    messages = [message for item in conversations for message in item.cleaned_messages]
    return CleaningStatistics(
        conversation_count=len(conversations),
        input_message_count=input_message_count,
        output_message_count=len(messages),
        normalized_message_count=sum(
            item.normalized_content != item.raw_content for item in messages
        ),
        system_message_count=sum(item.is_system_message for item in messages),
        recalled_message_count=sum(item.is_recalled_message for item in messages),
        duplicate_message_count=sum(
            item.duplicate_of_source_message_id is not None for item in messages
        ),
        excluded_message_count=sum(item.excluded_from_analysis for item in messages),
        redacted_message_count=sum(_operation_count(item, "redaction") > 0 for item in messages),
        redaction_count=sum(_replacement_total(item, "redaction") for item in messages),
        url_replacement_count=sum(_replacement_total(item, "url_replacement") for item in messages),
        attachment_placeholder_count=sum(
            _operation_count(item, "attachment_placeholders") for item in messages
        ),
        analysis_unit_count=sum(len(item.analysis_units) for item in conversations),
        warning_count=warning_count,
        per_cleaner_counts=dict(per_cleaner_counts),
    )


def _recomputed_cleaner_counts(
    conversations: list[CleanedConversation],
) -> dict[str, int]:
    counts = {name: 0 for name in CLEANER_ORDER}
    for conversation in conversations:
        for message in conversation.cleaned_messages:
            for operation in message.cleaning_operations:
                counts.setdefault(operation.cleaner_name, 0)
                counts[operation.cleaner_name] += 1
    counts["analysis_units"] = sum(len(item.analysis_units) for item in conversations)
    return counts


def validate_cleaned_chat(result: CleanedChatFile) -> CleanedChatFile:
    """Recompute every derived reference and statistic without changing output."""

    # Revalidate nested schemas after cleaner mutations.
    CleanedChatFile.model_validate(result.model_dump())
    for conversation in result.conversations:
        positions = {
            message.source_message_id: index
            for index, message in enumerate(conversation.cleaned_messages)
        }
        if len(positions) != len(conversation.cleaned_messages):
            raise ValueError("cleaned messages must retain unique source identifiers")
        for index, message in enumerate(conversation.cleaned_messages):
            duplicate = message.duplicate_of_source_message_id
            if duplicate is not None and (
                duplicate not in positions or positions[duplicate] >= index
            ):
                raise ValueError("duplicate reference must point to an earlier message")
        unit_message_ids: set[str] = set()
        last_unit_position = -1
        messages_by_id = {
            message.source_message_id: message for message in conversation.cleaned_messages
        }
        for unit in conversation.analysis_units:
            if unit.conversation_source_id != conversation.source_conversation_id:
                raise ValueError("analysis unit references the wrong conversation")
            if any(identifier not in positions for identifier in unit.message_source_ids):
                raise ValueError("analysis unit references an unknown message")
            unit_positions = [positions[identifier] for identifier in unit.message_source_ids]
            if (
                unit_positions != sorted(unit_positions)
                or unit_positions[0] <= last_unit_position
                or unit_message_ids.intersection(unit.message_source_ids)
            ):
                raise ValueError("analysis unit message references are not stable and unique")
            source_messages = [messages_by_id[identifier] for identifier in unit.message_source_ids]
            expected_fields = (
                derive_analysis_unit_id(
                    conversation.source_conversation_id,
                    unit.message_source_ids,
                ),
                source_messages[0].sender_source_id,
                source_messages[0].timestamp,
                source_messages[-1].timestamp,
                "\n".join(item.normalized_content for item in source_messages),
                len(source_messages),
                source_messages[0].source_order,
                source_messages[-1].source_order,
            )
            actual_fields = (
                unit.analysis_unit_id,
                unit.sender_source_id,
                unit.started_at,
                unit.ended_at,
                unit.combined_content,
                unit.message_count,
                unit.source_order_start,
                unit.source_order_end,
            )
            if actual_fields != expected_fields or any(
                item.message_type.value != "text"
                or item.excluded_from_analysis
                or item.is_system_message
                or item.is_recalled_message
                or item.sender_source_id != unit.sender_source_id
                for item in source_messages
            ):
                raise ValueError("analysis unit fields do not match source messages")
            if any(
                later.source_order != earlier.source_order + 1
                for earlier, later in zip(
                    source_messages,
                    source_messages[1:],
                    strict=False,
                )
            ):
                raise ValueError("analysis unit fields do not match source messages")
            unit_message_ids.update(unit.message_source_ids)
            last_unit_position = unit_positions[-1]

    expected = _statistics(
        result.conversations,
        result.statistics.input_message_count,
        len(result.cleaning_warnings),
        _recomputed_cleaner_counts(result.conversations),
    )
    if result.statistics != expected:
        raise ValueError("cleaning statistics do not match final output")
    if result.statistics.input_message_count != result.statistics.output_message_count:
        raise ValueError("cleaning cannot remove messages")
    return result


def _validate_against_parser_source(
    source: ParsedChatFile,
    result: CleanedChatFile,
) -> None:
    if len(source.conversations) != len(result.conversations):
        raise ValueError("cleaning cannot add or remove conversations")
    for original_conversation, cleaned_conversation in zip(
        source.conversations,
        result.conversations,
        strict=True,
    ):
        original_identity = (
            original_conversation.source_conversation_id,
            original_conversation.platform,
            original_conversation.title,
            original_conversation.started_at,
            original_conversation.ended_at,
            original_conversation.time_range_derived,
            original_conversation.participants,
            original_conversation.metadata_json,
        )
        cleaned_identity = (
            cleaned_conversation.source_conversation_id,
            cleaned_conversation.platform,
            cleaned_conversation.title,
            cleaned_conversation.started_at,
            cleaned_conversation.ended_at,
            cleaned_conversation.time_range_derived,
            cleaned_conversation.participants,
            cleaned_conversation.metadata_json,
        )
        if original_identity != cleaned_identity or len(original_conversation.messages) != len(
            cleaned_conversation.cleaned_messages
        ):
            raise ValueError("cleaning changed canonical conversation data")
        for original, cleaned in zip(
            original_conversation.messages,
            cleaned_conversation.cleaned_messages,
            strict=True,
        ):
            canonical_fields = (
                original.source_message_id,
                original.sender_source_id,
                original.timestamp,
                original.message_type,
                original.raw_content,
                original.reply_to_source_message_id,
                original.source_order,
                original.source_location,
                original.metadata_json,
            )
            cleaned_fields = (
                cleaned.source_message_id,
                cleaned.sender_source_id,
                cleaned.timestamp,
                cleaned.message_type,
                cleaned.raw_content,
                cleaned.reply_to_source_message_id,
                cleaned.source_order,
                cleaned.source_location,
                cleaned.metadata_json,
            )
            if canonical_fields != cleaned_fields:
                raise ValueError("cleaning changed canonical message data")


class CleaningPipeline:
    """Repository-internal fixed cleaner sequence; no dynamic plugin loading."""

    def __init__(self) -> None:
        self.cleaners = DEFAULT_CLEANERS

    def run(
        self,
        source: ParsedChatFile,
        options: CleaningOptions | None = None,
    ) -> CleanedChatFile:
        if not isinstance(source, ParsedChatFile):
            raise TypeError("CleaningPipeline only accepts ParsedChatFile")
        configured = options or CleaningOptions()
        state = _initialize_state(source)
        all_counts = {name: 0 for name in CLEANER_ORDER}
        for cleaner in self.cleaners:
            if not cleaner.is_enabled(configured):
                all_counts.setdefault(cleaner.cleaner_name, 0)
                continue
            try:
                all_counts[cleaner.cleaner_name] = cleaner.apply(state, configured)
            except CleaningError:
                raise
            except Exception as error:
                raise CleaningError(
                    CleaningErrorCode.INTERNAL_CLEANER_ERROR,
                    safe_filename=source.source_filename,
                    cleaner_name=cleaner.cleaner_name,
                    message="A cleaner failed before a result could be produced.",
                    recoverable=False,
                    details={"exception_type": type(error).__name__},
                ) from None
        state.per_cleaner_counts = all_counts
        statistics = _statistics(
            state.conversations,
            state.input_message_count,
            len(state.cleaning_warnings),
            all_counts,
        )
        result = CleanedChatFile(
            source_filename=state.source_filename,
            file_hash=state.file_hash,
            parser_name=state.parser_name,
            parser_version=state.parser_version,
            cleaning_pipeline_version=CLEANING_PIPELINE_VERSION,
            conversations=state.conversations,
            parser_warnings=state.parser_warnings,
            cleaning_warnings=state.cleaning_warnings,
            statistics=statistics,
        )
        try:
            _validate_against_parser_source(source, result)
            return validate_cleaned_chat(result)
        except ValueError:
            raise CleaningError(
                CleaningErrorCode.INVALID_CLEANED_RESULT,
                safe_filename=source.source_filename,
                cleaner_name=None,
                message="The cleaning result failed final consistency validation.",
                recoverable=False,
                details={"reason": "validation_failed"},
            ) from None


def clean_chat(
    source: ParsedChatFile,
    options: CleaningOptions | None = None,
) -> CleanedChatFile:
    return CleaningPipeline().run(source, options)
