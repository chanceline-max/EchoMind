"""Stage-nine Insight review, Evidence detail, and revision endpoints."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from echomind.api.dependencies import (
    get_db_session,
    require_allowed_origin,
    set_private_response_headers,
)
from echomind.api.errors import ApiError, ErrorResponse
from echomind.models.enums import EvidenceState, InsightStatus, InsightType
from echomind.schemas.insight_review import (
    BatchConfirmRequest,
    BatchConfirmResponse,
    InsightDetail,
    InsightEditRequest,
    InsightPage,
    InsightRevisionPage,
    RejectInsightRequest,
    RestoreInsightRequest,
    ReviewActionRequest,
    ReviewMutationResponse,
    SupersedeInsightRequest,
)
from echomind.services import insight_review_service

router = APIRouter(prefix="/insights", tags=["insights"])
SortOption = Literal[
    "created_at_desc",
    "updated_at_desc",
    "confidence_desc",
    "confidence_asc",
]
WRITE_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("", response_model=InsightPage)
def read_insights(
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    status: InsightStatus | None = None,
    insight_type: InsightType | None = None,
    category: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    evidence_state: EvidenceState | None = None,
    min_confidence: Annotated[float | None, Query(ge=0, le=1)] = None,
    max_confidence: Annotated[float | None, Query(ge=0, le=1)] = None,
    conversation_id: str | None = None,
    source_file_id: str | None = None,
    has_contradicting_evidence: bool | None = None,
    review_bucket: Literal["batch_eligible", "manual"] | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: SortOption = "updated_at_desc",
) -> InsightPage:
    if min_confidence is not None and max_confidence is not None:
        if min_confidence > max_confidence:
            raise ApiError(
                "invalid_request",
                status_code=422,
                message="The confidence range is not valid.",
            )
    result = insight_review_service.list_insights(
        session,
        status=status,
        insight_type=insight_type,
        category=category,
        evidence_state=evidence_state,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        conversation_id=conversation_id,
        source_file_id=source_file_id,
        has_contradicting_evidence=has_contradicting_evidence,
        review_bucket=review_bucket,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    set_private_response_headers(response)
    return result


@router.post(
    "/batch-confirm",
    response_model=BatchConfirmResponse,
    responses=WRITE_RESPONSES,
    dependencies=[Depends(require_allowed_origin)],
)
def batch_confirm_insights(
    payload: BatchConfirmRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> BatchConfirmResponse:
    result = insight_review_service.batch_confirm_insights(session, payload)
    set_private_response_headers(response)
    return result


@router.get("/{insight_id}/revisions", response_model=InsightRevisionPage)
def read_insight_revisions(
    insight_id: str,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InsightRevisionPage:
    result = insight_review_service.get_revisions(
        session,
        insight_id,
        limit=limit,
        offset=offset,
    )
    set_private_response_headers(response)
    return result


@router.get("/{insight_id}", response_model=InsightDetail)
def read_insight(
    insight_id: str,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> InsightDetail:
    result = insight_review_service.get_insight_detail(session, insight_id)
    set_private_response_headers(response)
    return result


@router.patch(
    "/{insight_id}",
    response_model=ReviewMutationResponse,
    responses=WRITE_RESPONSES,
    dependencies=[Depends(require_allowed_origin)],
)
def update_insight(
    insight_id: str,
    payload: InsightEditRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ReviewMutationResponse:
    result = insight_review_service.edit_insight(session, insight_id, payload)
    set_private_response_headers(response)
    return result


@router.post(
    "/{insight_id}/confirm",
    response_model=ReviewMutationResponse,
    responses=WRITE_RESPONSES,
    dependencies=[Depends(require_allowed_origin)],
)
def confirm_insight(
    insight_id: str,
    payload: ReviewActionRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ReviewMutationResponse:
    result = insight_review_service.confirm_insight(session, insight_id, payload)
    set_private_response_headers(response)
    return result


@router.post(
    "/{insight_id}/reject",
    response_model=ReviewMutationResponse,
    responses=WRITE_RESPONSES,
    dependencies=[Depends(require_allowed_origin)],
)
def reject_insight(
    insight_id: str,
    payload: RejectInsightRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ReviewMutationResponse:
    result = insight_review_service.reject_insight(session, insight_id, payload)
    set_private_response_headers(response)
    return result


@router.post(
    "/{insight_id}/restore",
    response_model=ReviewMutationResponse,
    responses=WRITE_RESPONSES,
    dependencies=[Depends(require_allowed_origin)],
)
def restore_insight(
    insight_id: str,
    payload: RestoreInsightRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ReviewMutationResponse:
    result = insight_review_service.restore_insight(session, insight_id, payload)
    set_private_response_headers(response)
    return result


@router.post(
    "/{insight_id}/supersede",
    response_model=ReviewMutationResponse,
    responses=WRITE_RESPONSES,
    dependencies=[Depends(require_allowed_origin)],
)
def supersede_insight(
    insight_id: str,
    payload: SupersedeInsightRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ReviewMutationResponse:
    result = insight_review_service.supersede_insight(session, insight_id, payload)
    set_private_response_headers(response)
    return result
