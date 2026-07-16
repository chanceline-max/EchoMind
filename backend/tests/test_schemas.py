"""Pydantic schemas validate boundaries independently from ORM models."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from echomind.models.enums import FileType, InsightType
from echomind.schemas import InsightCreate, MessageCreate, SourceFileCreate, SourceFileRead
from tests.db_helpers import create_evidence_graph


def test_source_file_schema_rejects_paths_and_unknown_fields() -> None:
    base = {
        "filename": "synthetic.json",
        "file_type": FileType.JSON,
        "file_hash": "a" * 64,
        "parser_name": "test",
        "parser_version": "1",
    }
    with pytest.raises(ValidationError, match="path"):
        SourceFileCreate.model_validate({**base, "filename": "C:\\private\\chat.json"})
    with pytest.raises(ValidationError, match="Extra inputs"):
        SourceFileCreate.model_validate({**base, "secret": "must not be accepted"})


def test_message_schema_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        MessageCreate(
            conversation_id=UUID("00000000-0000-4000-8000-000000000001"),
            source_message_id="message-1",
            sender_id=UUID("00000000-0000-4000-8000-000000000002"),
            timestamp=datetime(2026, 1, 1),
            raw_content="synthetic",
            normalized_content="synthetic",
        )


def test_inference_schema_preserves_reasoning_fields_without_deciding_semantics() -> None:
    schema = InsightCreate(
        category="synthetic",
        insight_type=InsightType.INFERENCE,
        title="A possible explanation",
        statement="Synthetic only",
        confidence=0.4,
        extraction_version="test-v1",
        reasoning_basis="Based on two synthetic examples",
        alternative_explanations=["A different synthetic explanation"],
    )

    assert schema.alternative_explanations == ["A different synthetic explanation"]


def test_read_schema_from_orm_omits_storage_path(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    graph.source_file.storage_path = "relative/internal-only.json"
    db_session.commit()

    output = SourceFileRead.model_validate(graph.source_file).model_dump()

    assert output["imported_at"].tzinfo is UTC
    assert "storage_path" not in output
