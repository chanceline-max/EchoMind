"""Explicitly unavailable local-model boundary for stage six."""

from typing import ClassVar

from echomind.providers.errors import ProviderError, ProviderErrorCode
from echomind.providers.schemas import LLMRequest, LLMResult, ResponseModelT


class LocalModelProvider:
    provider_name: ClassVar[str] = "local"
    provider_version: ClassVar[str] = "0.0"
    supports_remote_calls: ClassVar[bool] = False
    supports_structured_output: ClassVar[bool] = True
    available: ClassVar[bool] = False

    def generate_structured(
        self,
        request: LLMRequest,
        response_schema: type[ResponseModelT],
    ) -> LLMResult[ResponseModelT]:
        del response_schema
        raise ProviderError(
            ProviderErrorCode.LOCAL_PROVIDER_NOT_CONFIGURED,
            message="A local model provider is not configured in this release.",
            provider_name=self.provider_name,
            request_id=str(request.request_id),
        )
