"""Synchronous chat-file import and SourceFile query endpoints."""

import json
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from echomind.api.dependencies import (
    get_db_session,
    require_allowed_origin,
    set_private_response_headers,
)
from echomind.api.errors import ApiError, ErrorResponse
from echomind.cleaning import CleaningOptions
from echomind.core.config import Settings
from echomind.parsers import ErrorMode
from echomind.repositories import import_repository
from echomind.schemas.imports import (
    ImportCleaningOptions,
    ImportDetail,
    ImportPage,
    ImportSummary,
)
from echomind.services.import_service import build_import_detail, import_upload

router = APIRouter(prefix="/imports", tags=["imports"])


def _cleaning_options(value: str | None) -> CleaningOptions:
    if value is None or not value.strip():
        return CleaningOptions()
    try:
        payload = json.loads(value)
        safe = ImportCleaningOptions.model_validate(payload)
        return CleaningOptions(**safe.model_dump(exclude_none=True))
    except (json.JSONDecodeError, TypeError, ValidationError, ValueError):
        raise ApiError(
            "invalid_import_options",
            status_code=422,
            message="The cleaning options are not valid.",
        ) from None


def _content_length(request: Request) -> int | None:
    value = request.headers.get("content-length")
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


@router.post(
    "",
    response_model=ImportDetail,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_allowed_origin)],
)
async def create_import(
    request: Request,
    response: Response,
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_db_session)],
    parser_name: Annotated[str | None, Form()] = None,
    error_mode: Annotated[ErrorMode, Form()] = ErrorMode.STRICT,
    default_timezone: Annotated[str | None, Form()] = None,
    cleaning_options_json: Annotated[str | None, Form()] = None,
) -> ImportDetail:
    settings = cast(Settings, request.app.state.settings)
    parser = parser_name.strip() if parser_name and parser_name.strip() else None
    timezone = default_timezone.strip() if default_timezone and default_timezone.strip() else None
    try:
        result = await import_upload(
            session,
            upload=file,
            parser_name=parser,
            error_mode=error_mode,
            default_timezone=timezone,
            cleaning_options=_cleaning_options(cleaning_options_json),
            settings=settings,
            content_length=_content_length(request),
        )
    except ValidationError:
        raise ApiError(
            "invalid_import_options",
            status_code=422,
            message="The parser options are not valid.",
        ) from None
    set_private_response_headers(response)
    return result


@router.get("", response_model=ImportPage)
def read_imports(
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ImportPage:
    items, total = import_repository.list_sources(session, limit=limit, offset=offset)
    set_private_response_headers(response)
    summaries: list[ImportSummary] = []
    for source in items:
        detail = build_import_detail(source)
        summaries.append(
            ImportSummary(
                source_file_id=detail.source_file_id,
                filename=detail.filename,
                file_hash=detail.file_hash,
                file_type=detail.file_type,
                imported_at=detail.imported_at,
                parser_name=detail.parser_name,
                parser_version=detail.parser_version,
                cleaning_pipeline_version=detail.cleaning_pipeline_version,
                conversation_count=detail.conversation_count,
                participant_count=detail.participant_count,
                message_count=detail.message_count,
                excluded_message_count=detail.excluded_message_count,
                warning_count=detail.parser_warning_count + detail.cleaning_warning_count,
            )
        )
    return ImportPage(items=summaries, total=total, limit=limit, offset=offset)


@router.get("/{source_file_id}", response_model=ImportDetail)
def read_import(
    source_file_id: str,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ImportDetail:
    source = import_repository.get_source(session, source_file_id)
    if source is None:
        raise ApiError(
            "resource_not_found",
            status_code=404,
            message="The requested import does not exist.",
        )
    set_private_response_headers(response)
    return build_import_detail(source)
