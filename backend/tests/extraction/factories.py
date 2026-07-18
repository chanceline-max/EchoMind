"""Synthetic extraction fixtures with no real chat content or network access."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from echomind.models import (
    Conversation,
    Message,
    Participant,
    SourceFile,
    conversation_participants,
)
from echomind.models.enums import FileType, MessageType
from echomind.providers import LLMProvider, LLMRequest, LLMResult, LLMUsage


class ScriptedProvider(LLMProvider):
    provider_name: ClassVar[str] = "mock"
    provider_version: ClassVar[str] = "test-1.0"
    supports_remote_calls: ClassVar[bool] = False
    supports_structured_output: ClassVar[bool] = True

    def __init__(self, payloads: Sequence[dict[str, Any] | Exception]) -> None:
        self.payloads = list(payloads)
        self.requests: list[LLMRequest] = []

    def generate_structured[ResponseT: BaseModel](
        self, request: LLMRequest, response_schema: type[ResponseT]
    ) -> LLMResult[ResponseT]:
        self.requests.append(request)
        payload = self.payloads.pop(0) if self.payloads else {"candidates": []}
        if isinstance(payload, Exception):
            raise payload
        output = response_schema.model_validate(payload, strict=True)
        return LLMResult[ResponseT](
            request_id=request.request_id,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model_name=request.model_name,
            output=output,
            usage=LLMUsage(
                estimated_input_characters=sum(len(item.content) for item in request.user_content),
                estimated_output_limit=request.max_output_tokens,
            ),
            attempts=1,
            duration_ms=0,
            request_version=request.request_version,
        )


def session_factory_for(session: Session) -> sessionmaker[Session]:
    return sessionmaker(bind=session.get_bind(), autoflush=False, expire_on_commit=False)


def create_chat(
    session: Session,
    *,
    conversation_suffix: str = "1",
    owner_count: int = 1,
    messages: int = 4,
    content_size: int | None = None,
    archived: bool = False,
) -> tuple[Conversation, list[Participant], list[Message]]:
    source = SourceFile(
        filename=f"synthetic-{conversation_suffix}.json",
        file_type=FileType.JSON,
        file_hash=(conversation_suffix[-1] * 64)[:64],
        byte_size=100,
        parser_name="synthetic",
        parser_version="1.0",
    )
    conversation = Conversation(
        source_file=source,
        platform="synthetic",
        source_conversation_id=f"conversation-{conversation_suffix}",
        archived_at=datetime(2026, 1, 20, tzinfo=UTC) if archived else None,
    )
    participants = [
        Participant(
            canonical_name=f"Private Name {conversation_suffix}-{index}",
            is_profile_owner=index < owner_count,
        )
        for index in range(max(2, owner_count))
    ]
    session.add_all([source, conversation, *participants])
    session.flush()
    for participant in participants:
        session.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                participant_id=participant.id,
            )
        )
    rows: list[Message] = []
    base = datetime(2026, 1, 1, 8, tzinfo=UTC)
    for index in range(messages):
        normalized = (
            "N" * content_size if content_size is not None else f"Synthetic normalized {index}."
        )
        row = Message(
            conversation=conversation,
            sender=participants[0 if index % 2 == 0 else 1],
            source_message_id=f"source-private-{conversation_suffix}-{index}",
            timestamp=base + timedelta(days=index),
            sequence_index=index,
            source_order=index,
            source_location=f"$.messages[{index}]",
            message_type=MessageType.TEXT,
            raw_content=f"RAW_PRIVATE_{conversation_suffix}_{index}",
            normalized_content=normalized,
            metadata_json={"private_marker": f"METADATA_PRIVATE_{index}"},
            cleaning_operations_json=[{"private": "CLEANING_PRIVATE"}],
        )
        rows.append(row)
        session.add(row)
    session.commit()
    return conversation, participants, rows


def evidence_ref(message: str, role: str = "supporting", relevance: float = 0.9) -> dict[str, Any]:
    return {
        "context_message_id": message,
        "role": role,
        "relevance_score": relevance,
    }


def candidate(
    *,
    insight_type: str = "fact",
    refs: list[dict[str, Any]] | None = None,
    explicit: bool = True,
    **updates: Any,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "insight_type": insight_type,
        "category": "background",
        "title": "Synthetic candidate",
        "statement": "The profile owner reports a synthetic preference.",
        "evidence_refs": refs or [evidence_ref("m001")],
        "model_confidence": 0.8,
        "explicit_self_report": explicit,
        "reasoning_basis": None,
        "alternative_explanations": [],
        "valid_from": None,
        "valid_to": None,
    }
    value.update(updates)
    return value


REQUEST_ID = UUID("00000000-0000-4000-8000-000000000007")
