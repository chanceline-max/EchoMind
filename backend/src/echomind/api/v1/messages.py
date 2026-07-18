"""Non-destructive message analysis-exclusion endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from echomind.api.dependencies import (
    get_db_session,
    require_allowed_origin,
    set_private_response_headers,
)
from echomind.api.errors import ApiError
from echomind.repositories import insight_review_repository
from echomind.schemas.insight_review import MessageLocation
from echomind.schemas.messages import AnalysisExclusionRequest, MessageSummary
from echomind.services.message_service import set_analysis_exclusion

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{message_id}/location", response_model=MessageLocation)
def read_message_location(
    message_id: str,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> MessageLocation:
    location = insight_review_repository.message_location(session, message_id)
    if location is None:
        raise ApiError(
            "resource_not_found",
            status_code=404,
            message="The requested message does not exist.",
        )
    conversation_id, zero_based_index, suggested_offset = location
    set_private_response_headers(response)
    return MessageLocation(
        message_id=message_id,
        conversation_id=conversation_id,
        zero_based_index=zero_based_index,
        suggested_offset=suggested_offset,
    )


@router.patch(
    "/{message_id}/analysis-exclusion",
    response_model=MessageSummary,
    dependencies=[Depends(require_allowed_origin)],
)
def update_analysis_exclusion(
    message_id: str,
    payload: AnalysisExclusionRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> MessageSummary:
    result = set_analysis_exclusion(
        session,
        message_id=message_id,
        excluded=payload.excluded,
    )
    set_private_response_headers(response)
    return result
