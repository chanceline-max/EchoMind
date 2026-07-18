"""Build the synthetic Stage 9 E2E state through formal local services."""

import asyncio
import io
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select

from echomind.cleaning import CleaningOptions
from echomind.confidence import ConfidenceCalculationRequest, calculate_confidence
from echomind.core.config import Settings
from echomind.db.session import create_db_engine, create_session_factory
from echomind.extraction import ExtractionRequest, extract_candidates
from echomind.models import Conversation, Insight
from echomind.parsers import ErrorMode
from echomind.providers import create_provider
from echomind.services.import_service import import_upload


def source_bytes() -> bytes:
    payload = {
        "format": "echomind-generic-chat",
        "version": "1.0",
        "platform": "synthetic-stage-nine",
        "conversations": [
            {
                "id": "stage-nine-conversation",
                "title": "Stage nine review fixture",
                "participants": [
                    {
                        "id": "owner",
                        "name": "Synthetic Owner",
                        "is_profile_owner": True,
                    },
                    {
                        "id": "other",
                        "name": "Synthetic Other",
                        "is_profile_owner": False,
                    },
                ],
                "messages": [
                    {
                        "id": "stage-nine-message-1",
                        "sender_id": "owner",
                        "timestamp": "2026-07-10T08:00:00+08:00",
                        "type": "text",
                        "content": "Synthetic owner statement alpha.",
                    },
                    {
                        "id": "stage-nine-message-2",
                        "sender_id": "other",
                        "timestamp": "2026-07-10T08:01:00+08:00",
                        "type": "text",
                        "content": "Synthetic contextual reply.",
                        "reply_to_message_id": "stage-nine-message-1",
                    },
                    {
                        "id": "stage-nine-message-3",
                        "sender_id": "owner",
                        "timestamp": "2026-07-10T08:02:00+08:00",
                        "type": "text",
                        "content": "Synthetic owner statement beta.",
                    },
                ],
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def candidate_payload(
    *, title: str, statement: str, references: list[str]
) -> dict[str, object]:
    return {
        "candidates": [
            {
                "insight_type": "fact",
                "category": "background",
                "title": title,
                "statement": statement,
                "evidence_refs": [
                    {
                        "context_message_id": reference,
                        "role": "supporting",
                        "relevance_score": 0.9,
                    }
                    for reference in references
                ],
                "model_confidence": 0.82,
                "explicit_self_report": True,
                "reasoning_basis": None,
                "alternative_explanations": [],
                "valid_from": None,
                "valid_to": None,
            }
        ]
    }


async def seed() -> None:
    settings = Settings()
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    session = factory()
    try:
        upload = UploadFile(
            io.BytesIO(source_bytes()),
            filename="stage-nine-synthetic.json",
        )
        await import_upload(
            session,
            upload=upload,
            parser_name=None,
            error_mode=ErrorMode.STRICT,
            default_timezone=None,
            cleaning_options=CleaningOptions(),
            settings=settings,
            content_length=None,
        )
    finally:
        session.close()

    session = factory()
    try:
        conversation_id = session.scalar(
            select(Conversation.id).where(
                Conversation.title == "Stage nine review fixture"
            )
        )
        if conversation_id is None:
            raise RuntimeError("synthetic Stage 9 conversation was not imported")
    finally:
        session.close()

    request = ExtractionRequest(conversation_ids=[UUID(conversation_id)])
    for title, statement, references in (
        (
            "Synthetic review candidate alpha",
            "The synthetic owner explicitly reports statement alpha.",
            ["m001"],
        ),
        (
            "Synthetic review candidate beta",
            "The synthetic owner explicitly reports statements alpha and beta.",
            ["m001", "m003"],
        ),
    ):
        provider = create_provider(
            settings,
            provider_name="mock",
            mock_response_payload=candidate_payload(
                title=title,
                statement=statement,
                references=references,
            ),
        )
        report = extract_candidates(
            factory, request, settings=settings, provider=provider
        )
        if report.insights_created != 1:
            raise RuntimeError(
                "synthetic Stage 9 extraction did not create one Insight"
            )

    session = factory()
    try:
        insight_ids = list(session.scalars(select(Insight.id).order_by(Insight.title)))
    finally:
        session.close()
    confidence = calculate_confidence(
        factory,
        ConfidenceCalculationRequest(
            insight_ids=[UUID(insight_id) for insight_id in insight_ids],
            as_of=datetime(2026, 7, 17, tzinfo=UTC),
            force_recalculate=True,
        ),
        calculated_at=datetime(2026, 7, 17, 1, tzinfo=UTC),
    )
    if confidence.scored_count != 2:
        raise RuntimeError(
            "synthetic Stage 9 confidence scoring did not score both Insights"
        )
    engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
