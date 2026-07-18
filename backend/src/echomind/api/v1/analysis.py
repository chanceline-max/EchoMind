"""User-reachable, bounded synchronous analysis endpoints."""

from typing import cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from echomind.api.dependencies import require_allowed_origin, set_private_response_headers
from echomind.api.errors import ApiError
from echomind.core.config import Settings
from echomind.extraction.errors import ExtractionError
from echomind.providers.errors import ProviderError
from echomind.schemas.analysis import AnalysisCapabilities, AnalysisRequest, AnalysisResponse
from echomind.services.analysis_service import (
    ProviderFactory,
    analysis_capabilities,
    run_analysis,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/capabilities", response_model=AnalysisCapabilities)
def read_analysis_capabilities(request: Request, response: Response) -> AnalysisCapabilities:
    settings = cast(Settings, request.app.state.settings)
    set_private_response_headers(response)
    return analysis_capabilities(settings)


@router.post("", response_model=AnalysisResponse, dependencies=[Depends(require_allowed_origin)])
def create_analysis(
    payload: AnalysisRequest,
    request: Request,
    response: Response,
) -> AnalysisResponse:
    settings = cast(Settings, request.app.state.settings)
    capabilities = analysis_capabilities(settings)
    if not capabilities.provider_available:
        raise ApiError(
            "provider_not_configured",
            status_code=503,
            message="The configured analysis provider is not available.",
        )
    if capabilities.remote_consent_required and not payload.remote_consent:
        raise ApiError(
            "remote_consent_required",
            status_code=422,
            message="Remote analysis requires explicit consent for this request.",
        )
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    provider_factory = cast(ProviderFactory, request.app.state.analysis_provider_factory)
    try:
        result = run_analysis(
            factory,
            payload,
            settings=settings,
            provider_factory=provider_factory,
        )
    except ExtractionError as error:
        raise ApiError(
            error.error_code.value,
            status_code=404 if error.error_code.value == "conversation_not_found" else 422,
            message=error.message,
            recoverable=error.recoverable,
        ) from error
    except ProviderError as error:
        raise ApiError(
            error.error_code.value,
            status_code=503,
            message=error.message,
            recoverable=error.recoverable,
        ) from error
    set_private_response_headers(response)
    return result
