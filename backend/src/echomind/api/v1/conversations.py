"""Conversation and paginated message read endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from echomind.api.dependencies import get_db_session, set_private_response_headers
from echomind.schemas.conversations import ConversationDetail, ConversationPage
from echomind.schemas.messages import MessagePage
from echomind.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationPage)
def read_conversations(
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    source_file_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConversationPage:
    set_private_response_headers(response)
    return conversation_service.list_conversations(
        session,
        source_file_id=source_file_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
def read_conversation(
    conversation_id: str,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ConversationDetail:
    set_private_response_headers(response)
    return conversation_service.get_conversation(session, conversation_id)


@router.get("/{conversation_id}/messages", response_model=MessagePage)
def read_messages(
    conversation_id: str,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    include_excluded: bool = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MessagePage:
    set_private_response_headers(response)
    return conversation_service.list_messages(
        session,
        conversation_id=conversation_id,
        include_excluded=include_excluded,
        limit=limit,
        offset=offset,
    )
