"""Profile generation, idempotent persistence, and dynamic stale detection."""

from datetime import datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from echomind.core.config import Settings
from echomind.db.types import utc_now
from echomind.models.profile_snapshot import ProfileSnapshot
from echomind.profiling.document import build_profile
from echomind.profiling.errors import ProfileError
from echomind.profiling.fingerprints import build_source_manifest, generation_fingerprint
from echomind.profiling.options import ProfileGenerationRequest
from echomind.profiling.persistence import restore_document, to_snapshot
from echomind.profiling.schemas import EchoProfileDocument, ProfileSourceManifest, StalenessResult
from echomind.profiling.synthesis import synthesize_personality
from echomind.providers import LLMProvider
from echomind.repositories import profile_repository
from echomind.services.analysis_service import configured_model_name


def _enforce_limits(
    sources: list[profile_repository.ProfileInsightSource], settings: Settings
) -> None:
    evidence_ids = {evidence.evidence_id for item in sources for evidence in item.evidence}
    if len(sources) > settings.profile_max_insights:
        raise ProfileError(
            "profile_limit_exceeded",
            "The Profile Insight limit was exceeded.",
            details={"limit": settings.profile_max_insights, "actual": len(sources)},
        )
    if len(evidence_ids) > settings.profile_max_evidence:
        raise ProfileError(
            "profile_limit_exceeded",
            "The Profile Evidence limit was exceeded.",
            details={"limit": settings.profile_max_evidence, "actual": len(evidence_ids)},
        )
    for item in sources:
        if len(item.statement) > settings.profile_max_statement_characters:
            raise ProfileError(
                "profile_limit_exceeded",
                "A Profile statement exceeds the configured limit.",
                details={
                    "limit": settings.profile_max_statement_characters,
                    "actual": len(item.statement),
                },
            )
        if (
            item.reasoning_basis
            and len(item.reasoning_basis) > settings.profile_max_reasoning_characters
        ):
            raise ProfileError(
                "profile_limit_exceeded",
                "A Profile reasoning field exceeds the configured limit.",
                details={
                    "limit": settings.profile_max_reasoning_characters,
                    "actual": len(item.reasoning_basis),
                },
            )


def generate_profile(
    session_factory: sessionmaker[Session],
    request: ProfileGenerationRequest,
    *,
    settings: Settings,
    provider: LLMProvider | None = None,
    generated_at: datetime | None = None,
) -> tuple[ProfileSnapshot, bool]:
    generated_at = generated_at or utc_now()
    effective_request = request
    if request.include_personality_synthesis:
        if provider is None:
            raise ProfileError(
                "profile_synthesis_provider_unavailable",
                "Personality synthesis requires an available structured Provider.",
                status_code=503,
            )
        effective_request = request.model_copy(
            update={
                "synthesis_provider_name": provider.provider_name,
                "synthesis_model_name": configured_model_name(settings),
            }
        )
    for attempt in range(2):
        with session_factory() as read_session:
            sources = profile_repository.load_profile_sources(read_session, effective_request)
        _enforce_limits(sources, settings)
        _, source_fingerprint = build_source_manifest(sources, effective_request)
        expected_generation = generation_fingerprint(source_fingerprint, effective_request)
        with session_factory() as existing_session:
            existing = profile_repository.find_by_generation_fingerprint(
                existing_session, expected_generation
            )
            if existing is not None:
                return existing, False
        synthesis = (
            synthesize_personality(
                sources,
                effective_request,
                settings=settings,
                provider=provider,
            )
            if effective_request.include_personality_synthesis and provider is not None
            else None
        )
        built = build_profile(
            sources,
            effective_request,
            generated_at=generated_at,
            personality_synthesis=synthesis,
        )
        json_bytes = len(built.json_content.encode("utf-8"))
        markdown_bytes = len(built.markdown_content.encode("utf-8"))
        if json_bytes > settings.profile_max_json_bytes:
            raise ProfileError(
                "profile_limit_exceeded",
                "The rendered JSON exceeds the configured byte limit.",
                details={"limit": settings.profile_max_json_bytes, "actual": json_bytes},
            )
        if markdown_bytes > settings.profile_max_markdown_bytes:
            raise ProfileError(
                "profile_limit_exceeded",
                "The rendered Markdown exceeds the configured byte limit.",
                details={"limit": settings.profile_max_markdown_bytes, "actual": markdown_bytes},
            )
        with session_factory() as write_session:
            existing = profile_repository.find_by_generation_fingerprint(
                write_session, built.document.metadata.generation_fingerprint
            )
            if existing is not None:
                return existing, False
            current = profile_repository.load_profile_sources(write_session, effective_request)
            _, current_fingerprint = build_source_manifest(current, effective_request)
            if current_fingerprint != built.document.metadata.source_fingerprint:
                if attempt == 0:
                    continue
                raise ProfileError(
                    "profile_source_changed",
                    "The Profile source changed during generation.",
                    status_code=409,
                    recoverable=True,
                )
            return profile_repository.add_snapshot(write_session, to_snapshot(built))
    raise ProfileError("profile_generation_failed", "Profile generation failed.")


def _request_from_snapshot(snapshot: ProfileSnapshot) -> ProfileGenerationRequest:
    options = snapshot.generation_options_json
    if options is None:
        raise ProfileError(
            "profile_source_unavailable",
            "The Profile generation options are unavailable.",
            status_code=409,
        )
    supported_pairs = {
        ("echo-profile-1.0", "echo-profile-document-1.0"),
        ("echo-profile-2.0", "echo-profile-document-2.0"),
    }
    if (snapshot.profile_version, snapshot.schema_version) not in supported_pairs:
        raise ProfileError(
            "profile_source_unavailable",
            "The Profile version cannot be reconstructed.",
            status_code=409,
        )
    try:
        return ProfileGenerationRequest.model_validate(
            {
                "request_id": UUID(int=0),
                "profile_version": snapshot.profile_version,
                "profile_schema_version": snapshot.schema_version,
                **options,
            }
        )
    except (ValidationError, TypeError) as error:
        raise ProfileError(
            "profile_source_unavailable",
            "The Profile generation options are unavailable.",
            status_code=409,
        ) from error


def detect_staleness(session: Session, snapshot: ProfileSnapshot) -> StalenessResult:
    request = _request_from_snapshot(snapshot)
    stored_raw = snapshot.source_manifest_json
    if stored_raw is None:
        return StalenessResult(
            current_source_status="source_unavailable", stale_reason_codes=["source_missing"]
        )
    stored = [ProfileSourceManifest.model_validate(item) for item in stored_raw]
    stored_by_id = {item.insight_id: item for item in stored}
    try:
        current_sources = profile_repository.load_profile_sources(
            session, request, require_confirmed=request.scope == "all_confirmed"
        )
    except ProfileError as error:
        if request.scope == "all_confirmed" and error.error_code == "no_confirmed_insights":
            return StalenessResult(
                current_source_status="stale", stale_reason_codes=["confirmed_set_changed"]
            )
        return StalenessResult(
            current_source_status="source_unavailable", stale_reason_codes=["source_missing"]
        )
    current_manifest, current_fingerprint = build_source_manifest(current_sources, request)
    if current_fingerprint == snapshot.source_fingerprint:
        return StalenessResult(current_source_status="current", stale_reason_codes=[])
    current_by_id = {item.insight_id: item for item in current_manifest}
    reasons: set[str] = set()
    if set(current_by_id) != set(stored_by_id):
        reasons.add(
            "confirmed_set_changed" if request.scope == "all_confirmed" else "source_missing"
        )
    for insight_id in set(current_by_id) & set(stored_by_id):
        before = stored_by_id[insight_id]
        after = current_by_id[insight_id]
        if before.revision_number != after.revision_number:
            reasons.add("insight_revision_changed")
        if before.status != after.status:
            reasons.add("insight_status_changed")
        if (
            before.confidence != after.confidence
            or before.confidence_version != after.confidence_version
        ):
            reasons.add("confidence_changed")
        if before.evidence_state != after.evidence_state:
            reasons.add("evidence_state_changed")
        if (
            before.evidence_fingerprints != after.evidence_fingerprints
            or before.evidence_validity != after.evidence_validity
        ):
            reasons.add("evidence_changed")
        if before.content_fingerprint != after.content_fingerprint:
            reasons.add("insight_content_changed")
    if "source_missing" in reasons:
        return StalenessResult(
            current_source_status="source_unavailable", stale_reason_codes=sorted(reasons)
        )
    return StalenessResult(
        current_source_status="stale", stale_reason_codes=sorted(reasons or {"evidence_changed"})
    )


def read_document(snapshot: ProfileSnapshot) -> EchoProfileDocument:
    return restore_document(snapshot)
