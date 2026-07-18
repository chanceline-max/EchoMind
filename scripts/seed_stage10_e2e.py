"""Extend the Stage 9 seed with a formal, synthetic Profile source graph."""

import asyncio
import io
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import UploadFile
from seed_stage9_e2e import seed as seed_stage_nine
from sqlalchemy import select

from echomind.cleaning import CleaningOptions
from echomind.confidence import ConfidenceCalculationRequest, calculate_confidence
from echomind.core.config import Settings
from echomind.db.session import create_db_engine, create_session_factory
from echomind.extraction import ExtractionRequest, extract_candidates
from echomind.models import Conversation, Insight, Message
from echomind.parsers import ErrorMode
from echomind.providers import create_provider
from echomind.schemas.insight_review import ReviewActionRequest
from echomind.services.import_service import import_upload
from echomind.services.insight_review_service import confirm_insight
from echomind.services.message_service import set_analysis_exclusion


def source_bytes() -> bytes:
    messages = [
        ("profile-message-1", "Synthetic profile owner statement alpha."),
        ("profile-message-2", "Synthetic profile owner statement beta."),
        ("profile-message-3", "Synthetic profile owner statement gamma."),
        ("profile-message-4", "Synthetic profile owner statement delta."),
    ]
    payload = {
        "format": "echomind-generic-chat",
        "version": "1.0",
        "platform": "synthetic-stage-ten",
        "conversations": [
            {
                "id": "stage-ten-conversation",
                "title": "Stage ten Profile fixture",
                "participants": [
                    {
                        "id": "profile-owner",
                        "name": "Synthetic Profile Owner",
                        "is_profile_owner": True,
                    }
                ],
                "messages": [
                    {
                        "id": message_id,
                        "sender_id": "profile-owner",
                        "timestamp": f"2026-07-{10 + index:02d}T08:00:00+08:00",
                        "type": "text",
                        "content": content,
                    }
                    for index, (message_id, content) in enumerate(messages)
                ],
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def candidate(
    insight_type: str,
    category: str,
    title: str,
    statement: str,
    references: list[tuple[str, str]],
    *,
    reasoning: bool = False,
) -> dict[str, object]:
    return {
        "candidates": [
            {
                "insight_type": insight_type,
                "category": category,
                "title": title,
                "statement": statement,
                "evidence_refs": [
                    {"context_message_id": ref, "role": role, "relevance_score": 0.9}
                    for ref, role in references
                ],
                "model_confidence": 0.75,
                "explicit_self_report": insight_type in {"fact", "preference"},
                "reasoning_basis": "Synthetic bounded reasoning." if reasoning else None,
                "alternative_explanations": ["Synthetic alternative."] if reasoning else [],
                "valid_from": None,
                "valid_to": None,
            }
        ]
    }


async def seed() -> None:
    await seed_stage_nine()
    settings = Settings()
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        await import_upload(
            session,
            upload=UploadFile(io.BytesIO(source_bytes()), filename="stage-ten-synthetic.json"),
            parser_name=None,
            error_mode=ErrorMode.STRICT,
            default_timezone=None,
            cleaning_options=CleaningOptions(),
            settings=settings,
            content_length=None,
        )
    with factory() as session:
        conversation_id = session.scalar(
            select(Conversation.id).where(Conversation.title == "Stage ten Profile fixture")
        )
    if conversation_id is None:
        raise RuntimeError("synthetic Stage 10 conversation was not imported")
    request = ExtractionRequest(conversation_ids=[UUID(conversation_id)])
    payloads = (
        candidate(
            "fact",
            "background",
            "Profile background",
            "Synthetic confirmed background.",
            [("m001", "supporting")],
        ),
        candidate(
            "preference",
            "preference",
            "Profile preference",
            "Synthetic confirmed preference.",
            [("m002", "supporting")],
        ),
        candidate(
            "contradiction",
            "internal_conflict",
            "Profile contradiction",
            "Synthetic evidence remains in conflict.",
            [("m001", "supporting"), ("m003", "contradicting")],
            reasoning=True,
        ),
        candidate(
            "hypothesis",
            "thinking_pattern",
            "Profile hypothesis",
            "Synthetic hypothesis remains pending verification.",
            [("m004", "supporting")],
            reasoning=True,
        ),
    )
    for payload in payloads:
        report = extract_candidates(
            factory,
            request,
            settings=settings,
            provider=create_provider(settings, provider_name="mock", mock_response_payload=payload),
        )
        if report.insights_created != 1:
            raise RuntimeError("synthetic Stage 10 extraction did not create one Insight")
    with factory() as session:
        created_ids = list(
            session.scalars(
                select(Insight.id).where(Insight.title.like("Profile %")).order_by(Insight.title)
            )
        )
    if len(created_ids) != 4:
        raise RuntimeError("synthetic Stage 10 extraction did not create four Insights")
    confidence = calculate_confidence(
        factory,
        ConfidenceCalculationRequest(
            insight_ids=[UUID(value) for value in created_ids],
            as_of=datetime(2026, 7, 21, tzinfo=UTC),
            force_recalculate=True,
        ),
        calculated_at=datetime(2026, 7, 21, 1, tzinfo=UTC),
    )
    if confidence.scored_count != 4:
        raise RuntimeError("synthetic Stage 10 scoring did not cover four Insights")
    with factory() as session:
        for insight_id in created_ids:
            confirm_insight(session, insight_id, ReviewActionRequest(expected_revision=0))
        partial_message_id = session.scalar(
            select(Message.id).where(
                Message.conversation_id == conversation_id,
                Message.source_message_id == "profile-message-3",
            )
        )
        if partial_message_id is None:
            raise RuntimeError("synthetic partial Evidence message is missing")
    with factory() as session:
        set_analysis_exclusion(session, message_id=partial_message_id, excluded=True)
    engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
