"""Run the real API with one explicit offline Provider fixture for Stage 11 E2E."""

from typing import Any

import uvicorn

from echomind.core.config import Settings
from echomind.main import create_app
from echomind.providers import LLMProvider, create_provider


def synthetic_candidate() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "insight_type": "fact",
                "category": "background",
                "title": "Synthetic end-to-end fact",
                "statement": "The synthetic owner explicitly reports a test fact.",
                "evidence_refs": [
                    {
                        "context_message_id": "m001",
                        "role": "supporting",
                        "relevance_score": 0.95,
                    }
                ],
                "model_confidence": 0.75,
                "explicit_self_report": True,
                "reasoning_basis": None,
                "alternative_explanations": [],
                "valid_from": None,
                "valid_to": None,
            }
        ]
    }


def provider_factory(settings: Settings) -> LLMProvider:
    return create_provider(
        settings,
        provider_name="mock",
        mock_response_payload=synthetic_candidate(),
    )


app = create_app(analysis_provider_factory=provider_factory)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
