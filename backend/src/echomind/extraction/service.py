"""Stage-seven orchestration: snapshot, window, provider, validate, persist."""

from __future__ import annotations

from echomind.core.config import Settings
from echomind.extraction.candidate_validation import validate_candidate
from echomind.extraction.context import select_context
from echomind.extraction.errors import ExtractionError, ExtractionErrorCode
from echomind.extraction.options import ExtractionRequest
from echomind.extraction.persistence import PersistenceCounts, SessionFactory, persist_window
from echomind.extraction.prompts import PROMPT_VERSION, SYSTEM_INSTRUCTION
from echomind.extraction.schemas import (
    CandidateInsightBatch,
    ExtractionErrorRecord,
    ExtractionReport,
    WindowResult,
)
from echomind.extraction.windows import ContextWindow, build_windows
from echomind.providers import LLMContent, LLMProvider, LLMRequest, ProviderError, create_provider


def _record(error: ExtractionError) -> ExtractionErrorRecord:
    details = {
        key: value for key, value in error.details.items() if isinstance(value, (str, int, bool))
    }
    return ExtractionErrorRecord(
        error_code=error.error_code.value,
        message=error.message,
        request_id=error.request_id,
        window_id=error.window_id,
        conversation_id=error.conversation_id,
        recoverable=error.recoverable,
        details=details,
    )


def _provider_error(
    error: ProviderError, request: ExtractionRequest, window: ContextWindow
) -> ExtractionError:
    return ExtractionError(
        ExtractionErrorCode.PROVIDER_ERROR,
        message="The provider could not process this extraction window.",
        request_id=request.request_id,
        window_id=window.window_id,
        conversation_id=window.conversation_id,
        recoverable=error.recoverable,
        details={"rule": error.error_code.value, "actual": error.attempts},
    )


def _llm_request(
    request: ExtractionRequest,
    window: ContextWindow,
    *,
    max_output_tokens: int,
) -> LLMRequest:
    return LLMRequest(
        system_instruction=SYSTEM_INSTRUCTION,
        user_content=[LLMContent(role="user", content=window.provider_json())],
        response_schema_name="CandidateInsightBatch",
        provider_name=request.provider_name,
        model_name=request.model_name,
        temperature=0.0,
        max_output_tokens=max_output_tokens,
        timeout_seconds=30.0,
        metadata_json={
            "pipeline_stage": "candidate_extraction",
            "extraction_version": request.extraction_version,
            "window_id": window.window_id,
            "message_count": len(window.messages),
            "conversation_count": 1,
            "schema_version": PROMPT_VERSION,
        },
        remote_consent=request.remote_consent,
        request_version="1.0",
    )


def _empty_report(
    request: ExtractionRequest,
    conversation_count: int,
    selected: int,
    excluded: int,
    windows: list[ContextWindow],
) -> ExtractionReport:
    return ExtractionReport(
        request_id=request.request_id,
        extraction_version=request.extraction_version,
        provider_name=request.provider_name,
        model_name=request.model_name,
        conversation_count=conversation_count,
        selected_message_count=selected,
        excluded_message_count=excluded,
        truncated_message_count=len(
            {
                message.database_message_id
                for window in windows
                for message in window.messages
                if message.content_truncated
            }
        ),
        window_count=len(windows),
        successful_window_count=0,
        failed_window_count=0,
        candidates_received=0,
        candidates_accepted=0,
        candidates_rejected=0,
        insights_created=0,
        insights_reused=0,
        evidence_created=0,
        evidence_reused=0,
        links_created=0,
        links_reused=0,
        insight_ids=[],
        stopped_early=False,
    )


def extract_candidates(
    session_factory: SessionFactory,
    request: ExtractionRequest,
    *,
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
) -> ExtractionReport:
    """Run extraction synchronously without an HTTP API or ExtractionRun table."""
    resolved_settings = settings or Settings()
    if provider is None:
        provider = create_provider(
            resolved_settings,
            provider_name=request.provider_name,
            mock_response_payload={"candidates": []},
        )
    read_session = session_factory()
    try:
        selection = select_context(read_session, request)
    finally:
        read_session.rollback()
        read_session.close()
    windows = [
        window
        for conversation in selection.conversations
        for window in build_windows(conversation.messages, request)
    ]
    report = _empty_report(
        request,
        len(selection.conversations),
        selection.selected_message_count,
        selection.excluded_message_count,
        windows,
    )
    for window in windows:
        provider_attempts = 0
        received = 0
        accepted = []
        rejected = 0
        counts = PersistenceCounts()
        window_error: ExtractionError | None = None
        try:
            result = provider.generate_structured(
                _llm_request(
                    request,
                    window,
                    max_output_tokens=min(2_048, resolved_settings.llm_max_output_tokens),
                ),
                CandidateInsightBatch,
            )
            provider_attempts = result.attempts
            received = len(result.output.candidates)
            if received > request.max_candidates_per_window:
                raise ExtractionError(
                    ExtractionErrorCode.CANDIDATE_BATCH_INVALID,
                    message="The provider returned too many candidates for this window.",
                    request_id=request.request_id,
                    window_id=window.window_id,
                    conversation_id=window.conversation_id,
                    details={
                        "rule": "candidate_limit",
                        "limit": request.max_candidates_per_window,
                        "actual": received,
                    },
                )
            for index, candidate in enumerate(result.output.candidates):
                try:
                    accepted.append(
                        validate_candidate(
                            candidate,
                            window,
                            candidate_index=index,
                            request_id=str(request.request_id),
                        )
                    )
                except ExtractionError as error:
                    rejected += 1
                    error.request_id = str(request.request_id)
                    report.errors.append(_record(error))
            counts = persist_window(
                session_factory,
                accepted,
                extraction_version=request.extraction_version,
                provider_name=result.provider_name,
                provider_request_id=str(result.request_id),
                model_name=result.model_name,
                request_id=str(request.request_id),
                window_id=window.window_id,
                conversation_id=window.conversation_id,
            )
        except ProviderError as error:
            provider_attempts = error.attempts
            window_error = _provider_error(error, request, window)
        except ExtractionError as error:
            window_error = error
        if window_error is not None:
            report.failed_window_count += 1
            report.errors.append(_record(window_error))
        else:
            report.successful_window_count += 1
        report.candidates_received += received
        report.candidates_accepted += len(accepted)
        report.candidates_rejected += rejected
        report.insights_created += counts.insights_created
        report.insights_reused += counts.insights_reused
        report.evidence_created += counts.evidence_created
        report.evidence_reused += counts.evidence_reused
        report.links_created += counts.links_created
        report.links_reused += counts.links_reused
        report.insight_ids.extend(
            insight_id for insight_id in counts.insight_ids if insight_id not in report.insight_ids
        )
        report.window_results.append(
            WindowResult(
                window_id=window.window_id,
                conversation_id=window.conversation_id,
                message_count=len(window.messages),
                truncated_message_count=window.truncated_message_count,
                provider_attempts=provider_attempts,
                candidates_received=received,
                candidates_accepted=len(accepted),
                candidates_rejected=rejected,
                insights_created=counts.insights_created,
                insights_reused=counts.insights_reused,
                error_code=window_error.error_code.value if window_error else None,
            )
        )
        if window_error is not None and request.stop_on_window_error:
            report.stopped_early = len(report.window_results) < len(windows)
            break
    return report
