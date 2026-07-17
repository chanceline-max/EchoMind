"""Read-only conversation and message application services."""

from sqlalchemy.orm import Session

from echomind.api.errors import ApiError
from echomind.models import Conversation, Message
from echomind.repositories import conversation_repository
from echomind.schemas.conversations import (
    ConversationDetail,
    ConversationPage,
    ConversationSummary,
    ParticipantSummary,
)
from echomind.schemas.messages import MessagePage, MessageSummary


def _summary(session: Session, conversation: Conversation) -> ConversationSummary:
    counts = conversation_repository.conversation_counts(session, conversation.id)
    return ConversationSummary(
        id=conversation.id,
        source_file_id=conversation.source_file_id,
        platform=conversation.platform,
        title=conversation.title,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        participant_count=counts.participant_count,
        message_count=counts.message_count,
        excluded_message_count=counts.excluded_message_count,
    )


def list_conversations(
    session: Session,
    *,
    source_file_id: str | None,
    limit: int,
    offset: int,
) -> ConversationPage:
    items, total = conversation_repository.list_conversations(
        session,
        source_file_id=source_file_id,
        limit=limit,
        offset=offset,
    )
    return ConversationPage(
        items=[_summary(session, item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_conversation(session: Session, conversation_id: str) -> ConversationDetail:
    conversation = conversation_repository.get_conversation(session, conversation_id)
    if conversation is None:
        raise ApiError(
            "resource_not_found",
            status_code=404,
            message="The requested conversation does not exist.",
        )
    summary = _summary(session, conversation)
    participants = conversation_repository.conversation_participant_rows(
        session,
        conversation_id,
    )
    return ConversationDetail(
        **summary.model_dump(),
        source_conversation_id=conversation.source_conversation_id,
        participants=[
            ParticipantSummary(
                id=item.id,
                display_name=item.canonical_name,
                aliases=list(item.aliases),
                is_profile_owner=item.is_profile_owner,
            )
            for item in participants
        ],
    )


def list_messages(
    session: Session,
    *,
    conversation_id: str,
    include_excluded: bool,
    limit: int,
    offset: int,
) -> MessagePage:
    if conversation_repository.get_conversation(session, conversation_id) is None:
        raise ApiError(
            "resource_not_found",
            status_code=404,
            message="The requested conversation does not exist.",
        )
    rows, total = conversation_repository.list_messages(
        session,
        conversation_id=conversation_id,
        include_excluded=include_excluded,
        limit=limit,
        offset=offset,
    )
    return MessagePage(
        items=[message_summary(message, display_name) for message, display_name in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def message_summary(message: Message, display_name: str) -> MessageSummary:
    return MessageSummary(
        id=message.id,
        conversation_id=message.conversation_id,
        source_message_id=message.source_message_id,
        sender_id=message.sender_id,
        sender_display_name=display_name,
        timestamp=message.timestamp,
        message_type=message.message_type.value,
        raw_content=message.raw_content,
        normalized_content=message.normalized_content,
        reply_to_message_id=message.reply_to_message_id,
        source_order=message.source_order,
        is_system_message=message.is_system_message,
        is_recalled_message=message.is_recalled_message,
        duplicate_of_message_id=message.duplicate_of_message_id,
        excluded_from_analysis=message.excluded_from_analysis,
        exclusion_reasons=list(message.exclusion_reasons_json),
    )
