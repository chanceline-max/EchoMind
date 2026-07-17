"""Non-destructive message analysis-exclusion endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from echomind.api.dependencies import (
    get_db_session,
    require_allowed_origin,
    set_private_response_headers,
)
from echomind.schemas.messages import AnalysisExclusionRequest, MessageSummary
from echomind.services.message_service import set_analysis_exclusion

router = APIRouter(prefix="/messages", tags=["messages"])


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
