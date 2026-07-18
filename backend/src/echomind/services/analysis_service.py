"""Minimal synchronous bridge from extraction to deterministic confidence scoring."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from echomind.confidence.options import CONFIDENCE_VERSION, ConfidenceCalculationRequest
from echomind.confidence.service import calculate_confidence
from echomind.core.config import Settings
from echomind.db.types import utc_now
from echomind.extraction.options import DEFAULT_EXTRACTION_VERSION, ExtractionRequest
from echomind.extraction.persistence import SessionFactory
from echomind.extraction.service import extract_candidates
from echomind.providers import LLMProvider, create_provider
from echomind.schemas.analysis import (
    AnalysisCapabilities,
    AnalysisErrorRecord,
    AnalysisRequest,
    AnalysisResponse,
)

ProviderFactory = Callable[[Settings], LLMProvider]
ProviderName = Literal["mock", "openai_compatible", "local"]


def configured_model_name(settings: Settings) -> str:
    if settings.llm_provider == "openai_compatible":
        return settings.llm_openai_compatible_model or "unconfigured-model"
    if settings.llm_provider == "local":
        return "local-model"
    return "mock-model"


def default_provider_factory(settings: Settings) -> LLMProvider:
    return create_provider(
        settings,
        provider_name=cast(ProviderName, settings.llm_provider),
        mock_response_payload={"candidates": []},
    )


def analysis_capabilities(settings: Settings) -> AnalysisCapabilities:
    provider = settings.llm_provider
    remote = provider == "openai_compatible"
    if provider == "mock":
        available = True
    elif provider == "local":
        available = False
    else:
        available = bool(
            settings.llm_remote_enabled
            and settings.llm_openai_compatible_endpoint
            and settings.llm_openai_compatible_api_key
            and settings.llm_openai_compatible_model
        )
    return AnalysisCapabilities(
        configured_provider=provider,
        provider_available=available,
        remote_provider=remote,
        remote_consent_required=remote,
        extraction_version=DEFAULT_EXTRACTION_VERSION,
        confidence_version=CONFIDENCE_VERSION,
        max_conversations_per_request=100,
    )


def run_analysis(
    session_factory: SessionFactory,
    payload: AnalysisRequest,
    *,
    settings: Settings,
    provider_factory: ProviderFactory = default_provider_factory,
    completed_at: datetime | None = None,
) -> AnalysisResponse:
    effective_time = (completed_at or utc_now()).astimezone(UTC)
    extraction_request = ExtractionRequest(
        conversation_ids=payload.conversation_ids,
        start_at=payload.start_at,
        end_at=payload.end_at,
        provider_name=cast(ProviderName, settings.llm_provider),
        model_name=configured_model_name(settings),
        remote_consent=payload.remote_consent,
        stop_on_window_error=payload.stop_on_window_error,
    )
    extraction = extract_candidates(
        session_factory,
        extraction_request,
        settings=settings,
        provider=provider_factory(settings),
    )
    confidence_scored = 0
    confidence_failed = 0
    errors = [
        AnalysisErrorRecord(
            error_code=item.error_code,
            message=item.message,
            recoverable=item.recoverable,
            conversation_id=item.conversation_id,
            window_id=item.window_id,
        )
        for item in extraction.errors
    ]
    if extraction.insight_ids:
        confidence = calculate_confidence(
            session_factory,
            ConfidenceCalculationRequest(
                insight_ids=[UUID(value) for value in extraction.insight_ids],
                as_of=effective_time,
                stop_on_error=False,
            ),
            calculated_at=effective_time,
        )
        confidence_scored = confidence.scored_count
        confidence_failed = confidence.failed_count
        errors.extend(
            AnalysisErrorRecord(
                error_code=item.error_code,
                message=item.message,
                recoverable=item.recoverable,
                insight_id=item.insight_id,
            )
            for item in confidence.errors
        )
    return AnalysisResponse(
        request_id=extraction.request_id,
        provider_name=extraction.provider_name,
        conversation_count=extraction.conversation_count,
        selected_message_count=extraction.selected_message_count,
        window_count=extraction.window_count,
        successful_window_count=extraction.successful_window_count,
        failed_window_count=extraction.failed_window_count,
        candidates_received=extraction.candidates_received,
        candidates_accepted=extraction.candidates_accepted,
        insights_created=extraction.insights_created,
        insights_reused=extraction.insights_reused,
        insight_ids=extraction.insight_ids,
        confidence_scored_count=confidence_scored,
        confidence_failed_count=confidence_failed,
        stopped_early=extraction.stopped_early,
        errors=errors,
        insights_link="/insights",
    )
