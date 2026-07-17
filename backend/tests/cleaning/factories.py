"""Synthetic factories for database-independent cleaning tests."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from echomind.parsers.schemas import (
    CanonicalConversation,
    CanonicalMessage,
    CanonicalParticipant,
    MessageType,
    ParsedChatFile,
    ParseStatistics,
    ParseWarning,
)

BASE_TIME = datetime(2026, 7, 17, 2, 0, tzinfo=UTC)


def participant(identifier: str = "person-a") -> CanonicalParticipant:
    return CanonicalParticipant(
        source_participant_id=identifier,
        display_name=f"Synthetic {identifier}",
        is_profile_owner=identifier == "person-a",
    )


def message(
    identifier: str = "message-1",
    *,
    sender: str = "person-a",
    content: str = "Synthetic message",
    message_type: MessageType = MessageType.TEXT,
    seconds: int = 0,
    source_order: int = 0,
    reply: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CanonicalMessage:
    return CanonicalMessage(
        source_message_id=identifier,
        sender_source_id=sender,
        timestamp=BASE_TIME + timedelta(seconds=seconds),
        message_type=message_type,
        raw_content=content,
        normalized_content=content,
        reply_to_source_message_id=reply,
        source_order=source_order,
        source_location=f"record:{source_order}",
        metadata_json=metadata or {},
    )


def conversation(
    messages: Iterable[CanonicalMessage] | None = None,
    *,
    identifier: str = "conversation-1",
    participants: Iterable[CanonicalParticipant] | None = None,
) -> CanonicalConversation:
    return CanonicalConversation(
        source_conversation_id=identifier,
        platform="generic",
        title="Synthetic conversation",
        started_at=BASE_TIME,
        ended_at=BASE_TIME + timedelta(hours=1),
        participants=list(participants or [participant("person-a"), participant("person-b")]),
        messages=list(messages or [message()]),
        metadata_json={"fixture": True},
    )


def parsed_chat(
    conversations: Iterable[CanonicalConversation] | None = None,
    *,
    warnings: Iterable[ParseWarning] | None = None,
) -> ParsedChatFile:
    items = list(conversations or [conversation()])
    warning_items = list(warnings or [])
    message_count = sum(len(item.messages) for item in items)
    return ParsedChatFile(
        source_filename="synthetic-chat.json",
        file_hash="a" * 64,
        parser_name="synthetic-parser",
        parser_version="1.0",
        conversations=items,
        warnings=warning_items,
        statistics=ParseStatistics(
            conversation_count=len(items),
            participant_count=sum(len(item.participants) for item in items),
            message_count=message_count,
            accepted_record_count=message_count,
            skipped_record_count=0,
            warning_count=len(warning_items),
        ),
    )
