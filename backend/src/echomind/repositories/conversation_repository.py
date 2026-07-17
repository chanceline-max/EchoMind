"""Conversation and message queries with stable pagination."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from echomind.models import Conversation, Message, Participant, conversation_participants


@dataclass(frozen=True)
class ConversationCounts:
    participant_count: int
    message_count: int
    excluded_message_count: int


def list_conversations(
    session: Session,
    *,
    source_file_id: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Conversation], int]:
    total_query = select(func.count()).select_from(Conversation)
    item_query = select(Conversation)
    if source_file_id is not None:
        total_query = total_query.where(Conversation.source_file_id == source_file_id)
        item_query = item_query.where(Conversation.source_file_id == source_file_id)
    total = session.scalar(total_query) or 0
    items = list(
        session.scalars(
            item_query.order_by(
                Conversation.started_at.desc(),
                Conversation.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def get_conversation(session: Session, conversation_id: str) -> Conversation | None:
    return session.get(Conversation, conversation_id)


def conversation_counts(session: Session, conversation_id: str) -> ConversationCounts:
    participant_count = (
        session.scalar(
            select(func.count())
            .select_from(conversation_participants)
            .where(conversation_participants.c.conversation_id == conversation_id)
        )
        or 0
    )
    message_count = (
        session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        or 0
    )
    excluded_count = (
        session.scalar(
            select(func.count())
            .select_from(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.excluded_from_analysis.is_(True),
            )
        )
        or 0
    )
    return ConversationCounts(participant_count, message_count, excluded_count)


def conversation_participant_rows(
    session: Session,
    conversation_id: str,
) -> list[Participant]:
    return list(
        session.scalars(
            select(Participant)
            .join(
                conversation_participants,
                conversation_participants.c.participant_id == Participant.id,
            )
            .where(conversation_participants.c.conversation_id == conversation_id)
            .order_by(Participant.created_at.asc(), Participant.id.asc())
        )
    )


def list_messages(
    session: Session,
    *,
    conversation_id: str,
    include_excluded: bool,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Message, str]], int]:
    filters = [Message.conversation_id == conversation_id]
    if not include_excluded:
        filters.append(Message.excluded_from_analysis.is_(False))
    total = session.scalar(select(func.count()).select_from(Message).where(*filters)) or 0
    result = session.execute(
        select(Message, Participant.canonical_name)
        .join(Participant, Participant.id == Message.sender_id)
        .where(*filters)
        .order_by(Message.source_order.asc(), Message.id.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = [(message, sender_name) for message, sender_name in result]
    return rows, total


def get_message_with_sender(session: Session, message_id: str) -> tuple[Message, str] | None:
    row = session.execute(
        select(Message, Participant.canonical_name)
        .join(Participant, Participant.id == Message.sender_id)
        .where(Message.id == message_id)
    ).one_or_none()
    return None if row is None else (row[0], row[1])
