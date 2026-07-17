"""Derived groups of adjacent analyzable text messages."""

import hashlib
from typing import ClassVar

from echomind.cleaning.base import CleaningState
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.schemas import AnalysisUnit, CleanedMessage
from echomind.parsers.schemas import MessageType

PIPELINE_ID_NAMESPACE = "echomind-cleaning-1.0"


def derive_analysis_unit_id(conversation_id: str, message_ids: list[str]) -> str:
    payload = "\x1f".join((PIPELINE_ID_NAMESPACE, conversation_id, *message_ids))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"analysis-unit-{digest}"


def _build_unit(conversation_id: str, messages: list[CleanedMessage]) -> AnalysisUnit:
    identifiers = [item.source_message_id for item in messages]
    return AnalysisUnit(
        analysis_unit_id=derive_analysis_unit_id(conversation_id, identifiers),
        conversation_source_id=conversation_id,
        sender_source_id=messages[0].sender_source_id,
        message_source_ids=identifiers,
        started_at=messages[0].timestamp,
        ended_at=messages[-1].timestamp,
        combined_content="\n".join(item.normalized_content for item in messages),
        message_count=len(messages),
        source_order_start=messages[0].source_order,
        source_order_end=messages[-1].source_order,
        metadata_json={},
    )


def _can_append(
    current: list[CleanedMessage],
    candidate: CleanedMessage,
    options: CleaningOptions,
) -> bool:
    previous = current[-1]
    if candidate.reply_to_source_message_id is not None:
        return False
    if candidate.sender_source_id != previous.sender_source_id:
        return False
    if candidate.source_order != previous.source_order + 1:
        return False
    gap = (candidate.timestamp - previous.timestamp).total_seconds()
    if gap < 0 or gap > options.analysis_unit_max_gap_seconds:
        return False
    if len(current) >= options.analysis_unit_max_messages:
        return False
    combined_length = sum(len(item.normalized_content) for item in current)
    combined_length += len(current) + len(candidate.normalized_content)
    return combined_length <= options.analysis_unit_max_characters


class AnalysisUnitCleaner:
    cleaner_name: ClassVar[str] = "analysis_units"
    cleaner_version: ClassVar[str] = "1.0"
    enabled_by_default: ClassVar[bool] = True

    def is_enabled(self, options: CleaningOptions) -> bool:
        return options.build_analysis_units

    def apply(self, state: CleaningState, options: CleaningOptions) -> int:
        unit_count = 0
        for conversation in state.conversations:
            units: list[AnalysisUnit] = []
            current: list[CleanedMessage] = []

            for message in conversation.cleaned_messages:
                eligible = (
                    message.message_type is MessageType.TEXT
                    and not message.excluded_from_analysis
                    and not message.is_system_message
                    and not message.is_recalled_message
                )
                if not eligible:
                    if current:
                        units.append(_build_unit(conversation.source_conversation_id, current))
                        current = []
                    continue
                if current and not _can_append(current, message, options):
                    units.append(_build_unit(conversation.source_conversation_id, current))
                    current = []
                current.append(message)
            if current:
                units.append(_build_unit(conversation.source_conversation_id, current))
            conversation.analysis_units = units
            unit_count += len(units)
        return unit_count
