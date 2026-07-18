"""Database snapshot selection without exposing ORM objects to providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from echomind.extraction.errors import ExtractionError, ExtractionErrorCode
from echomind.extraction.options import ExtractionRequest
from echomind.models import Conversation, Message, Participant, conversation_participants


@dataclass
class ContextMessage:
    database_message_id: str
    conversation_id: str
    sender_id: str
    is_profile_owner: bool
    timestamp: datetime
    message_type: str
    normalized_content: str
    reply_to_message_id: str | None
    source_order: int


@dataclass(frozen=True)
class ConversationContext:
    conversation_id: str
    messages: list[ContextMessage]


@dataclass(frozen=True)
class ContextSelection:
    conversations: list[ConversationContext]
    selected_message_count: int
    excluded_message_count: int


def _error(
    request: ExtractionRequest,
    code: ExtractionErrorCode,
    message: str,
    conversation_id: str,
) -> ExtractionError:
    return ExtractionError(
        code,
        message=message,
        request_id=request.request_id,
        conversation_id=conversation_id,
    )


def select_context(session: Session, request: ExtractionRequest) -> ContextSelection:
    """Snapshot only explicitly selected, current, analyzable messages."""
    selected: list[ConversationContext] = []
    excluded_count = 0
    for requested_id in request.conversation_ids:
        conversation_id = str(requested_id)
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise _error(
                request,
                ExtractionErrorCode.CONVERSATION_NOT_FOUND,
                "The requested conversation does not exist.",
                conversation_id,
            )
        if conversation.archived_at is not None:
            raise _error(
                request,
                ExtractionErrorCode.CONVERSATION_ARCHIVED,
                "The requested conversation is archived.",
                conversation_id,
            )
        participants = list(
            session.scalars(
                select(Participant)
                .join(
                    conversation_participants,
                    conversation_participants.c.participant_id == Participant.id,
                )
                .where(conversation_participants.c.conversation_id == conversation_id)
                .order_by(Participant.id.asc())
            )
        )
        owners = [item for item in participants if item.is_profile_owner]
        if not owners:
            raise _error(
                request,
                ExtractionErrorCode.PROFILE_OWNER_NOT_IDENTIFIED,
                "The conversation has no identified profile owner.",
                conversation_id,
            )
        if len(owners) > 1:
            raise _error(
                request,
                ExtractionErrorCode.MULTIPLE_PROFILE_OWNERS,
                "The conversation has multiple profile owners.",
                conversation_id,
            )
        owner_id = owners[0].id
        filters = [Message.conversation_id == conversation_id]
        if request.start_at is not None:
            filters.append(Message.timestamp >= request.start_at)
        if request.end_at is not None:
            filters.append(Message.timestamp <= request.end_at)
        rows = list(
            session.scalars(
                select(Message)
                .where(*filters)
                .order_by(Message.source_order.asc(), Message.id.asc())
            )
        )
        messages: list[ContextMessage] = []
        for row in rows:
            if (
                row.excluded_from_analysis
                or row.archived_at is not None
                or row.is_deleted
                or row.timestamp is None
            ):
                excluded_count += 1
                continue
            messages.append(
                ContextMessage(
                    database_message_id=row.id,
                    conversation_id=conversation_id,
                    sender_id=row.sender_id,
                    is_profile_owner=row.sender_id == owner_id,
                    timestamp=row.timestamp,
                    message_type=row.message_type.value,
                    normalized_content=row.normalized_content,
                    reply_to_message_id=row.reply_to_message_id,
                    source_order=row.source_order,
                )
            )
        if not messages:
            raise _error(
                request,
                ExtractionErrorCode.NO_ANALYZABLE_MESSAGES,
                "The requested conversation range has no analyzable messages.",
                conversation_id,
            )
        selected.append(ConversationContext(conversation_id=conversation_id, messages=messages))
    selected_count = sum(len(item.messages) for item in selected)
    if selected_count == 0:
        raise ExtractionError(
            ExtractionErrorCode.NO_ANALYZABLE_MESSAGES,
            message="The requested range has no analyzable messages.",
            request_id=request.request_id,
        )
    return ContextSelection(
        conversations=selected,
        selected_message_count=selected_count,
        excluded_message_count=excluded_count,
    )
