"""Generate, inspect, and explicitly export immutable EchoProfile snapshots."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from echomind.api.dependencies import (
    get_db_session,
    require_allowed_origin,
    set_private_response_headers,
)
from echomind.api.errors import ApiError
from echomind.core.config import Settings
from echomind.models import ProfileSnapshot
from echomind.profiling.errors import ProfileError
from echomind.profiling.json_renderer import render_json
from echomind.profiling.options import EvidenceMode
from echomind.profiling.persistence import safe_generated_date
from echomind.profiling.schemas import StalenessResult
from echomind.profiling.service import detect_staleness, generate_profile, read_document
from echomind.profiling.synthesis import ProfileProviderFactory
from echomind.providers.errors import ProviderError
from echomind.repositories import profile_repository
from echomind.schemas.profiles import (
    ProfileDetail,
    ProfileGenerationRequest,
    ProfileGenerationResponse,
    ProfileLinks,
    ProfilePage,
    ProfileSummary,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _raise_api(error: ProfileError) -> None:
    raise ApiError(
        error.error_code,
        status_code=error.status_code,
        message=error.message,
        recoverable=error.recoverable,
        details=error.details,
    ) from error


def _links(profile_id: str) -> ProfileLinks:
    base = f"/api/v1/profiles/{profile_id}"
    return ProfileLinks(self=base, markdown=f"{base}/markdown", json_url=f"{base}/json")


def _evidence_mode(options: dict[str, object]) -> EvidenceMode:
    value = options.get("evidence_mode", "references")
    return "excerpts" if value == "excerpts" else "references"


def _snapshot_or_404(session: Session, profile_id: str) -> ProfileSnapshot:
    snapshot = profile_repository.get_snapshot(session, profile_id)
    if snapshot is None:
        raise ApiError(
            "profile_snapshot_not_found",
            status_code=404,
            message="The Profile snapshot was not found.",
        )
    return snapshot


def _safe_staleness(session: Session, snapshot: ProfileSnapshot) -> StalenessResult:
    try:
        return detect_staleness(session, snapshot)
    except ProfileError:
        return StalenessResult(
            current_source_status="source_unavailable",
            stale_reason_codes=["source_missing"],
        )


@router.post(
    "", response_model=ProfileGenerationResponse, dependencies=[Depends(require_allowed_origin)]
)
def create_profile(
    payload: ProfileGenerationRequest,
    request: Request,
    response: Response,
) -> ProfileGenerationResponse:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    settings = cast(Settings, request.app.state.settings)
    provider = None
    if payload.include_personality_synthesis:
        if settings.llm_provider == "openai_compatible" and not payload.remote_consent:
            raise ApiError(
                "remote_consent_required",
                status_code=422,
                message="Remote personality synthesis requires explicit consent.",
            )
        provider_factory = cast(
            ProfileProviderFactory,
            request.app.state.profile_provider_factory,
        )
        provider = provider_factory(settings)
    try:
        snapshot, created = generate_profile(
            factory,
            payload,
            settings=settings,
            provider=provider,
        )
    except ProfileError as error:
        _raise_api(error)
    except ProviderError as error:
        raise ApiError(
            error.error_code.value,
            status_code=503,
            message=error.message,
            recoverable=error.recoverable,
        ) from error
    response.status_code = 201 if created else 200
    set_private_response_headers(response)
    return ProfileGenerationResponse(
        profile_snapshot_id=snapshot.id,
        profile_version=snapshot.profile_version,
        schema_version=snapshot.schema_version,
        generated_at=snapshot.generated_at,
        source_fingerprint=snapshot.source_fingerprint or "",
        generation_fingerprint=snapshot.generation_fingerprint or "",
        document_hash=snapshot.document_hash or "",
        insight_count=snapshot.insight_count or 0,
        evidence_count=snapshot.evidence_count or 0,
        source_status="current",
        created=created,
        reused=not created,
        links=_links(snapshot.id),
    )


@router.get("", response_model=ProfilePage)
def read_profiles(
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    profile_version: str | None = None,
) -> ProfilePage:
    snapshots, total = profile_repository.list_snapshots(
        session, limit=limit, offset=offset, profile_version=profile_version
    )
    items: list[ProfileSummary] = []
    for snapshot in snapshots:
        stale = _safe_staleness(session, snapshot)
        options = snapshot.generation_options_json or {}
        items.append(
            ProfileSummary(
                id=snapshot.id,
                generated_at=snapshot.generated_at,
                profile_version=snapshot.profile_version,
                schema_version=snapshot.schema_version,
                insight_count=snapshot.insight_count or 0,
                evidence_count=snapshot.evidence_count or 0,
                evidence_mode=_evidence_mode(options),
                document_hash=snapshot.document_hash or "",
                current_source_status=stale.current_source_status,
                stale_reason_codes=stale.stale_reason_codes,
            )
        )
    set_private_response_headers(response)
    return ProfilePage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{profile_id}", response_model=ProfileDetail)
def read_profile(
    profile_id: str,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ProfileDetail:
    snapshot = _snapshot_or_404(session, profile_id)
    try:
        document = read_document(snapshot)
        stale = _safe_staleness(session, snapshot)
    except ProfileError as error:
        _raise_api(error)
    options = snapshot.generation_options_json or {}
    set_private_response_headers(response)
    return ProfileDetail(
        id=snapshot.id,
        generated_at=snapshot.generated_at,
        profile_version=snapshot.profile_version,
        schema_version=snapshot.schema_version,
        insight_count=snapshot.insight_count or 0,
        evidence_count=snapshot.evidence_count or 0,
        evidence_mode=_evidence_mode(options),
        document_hash=snapshot.document_hash or "",
        current_source_status=stale.current_source_status,
        stale_reason_codes=stale.stale_reason_codes,
        document=document,
        links=_links(snapshot.id),
    )


def _download_headers(filename: str, content_type: str) -> dict[str, str]:
    return {
        "Content-Type": content_type,
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }


@router.get("/{profile_id}/markdown")
def export_profile_markdown(
    profile_id: str, session: Annotated[Session, Depends(get_db_session)]
) -> Response:
    snapshot = _snapshot_or_404(session, profile_id)
    try:
        read_document(snapshot)
    except ProfileError as error:
        _raise_api(error)
    filename = f"echoprofile-{safe_generated_date(snapshot.generated_at)}.md"
    return Response(
        content=snapshot.markdown_content.encode("utf-8"),
        headers=_download_headers(filename, "text/markdown; charset=utf-8"),
    )


@router.get("/{profile_id}/json")
def export_profile_json(
    profile_id: str, session: Annotated[Session, Depends(get_db_session)]
) -> Response:
    snapshot = _snapshot_or_404(session, profile_id)
    try:
        document = read_document(snapshot)
    except ProfileError as error:
        _raise_api(error)
    filename = f"echoprofile-{safe_generated_date(snapshot.generated_at)}.json"
    return Response(
        content=render_json(document).encode("utf-8"),
        headers=_download_headers(filename, "application/json; charset=utf-8"),
    )
