"""EchoProfile 2.0 personality synthesis and presentation privacy."""

import json
from typing import cast

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from echomind.core.config import Settings
from echomind.db.session import create_session_factory
from echomind.profiling.service import generate_profile, read_document
from echomind.profiling.synthesis import default_profile_provider_factory
from echomind.providers import LLMProvider
from tests.profiling.factories import create_profile_graph, profile_request


def test_profile_two_synthesizes_two_reference_frameworks_without_visible_evidence(
    db_session: Session,
    settings: Settings,
) -> None:
    create_profile_graph(db_session)
    factory = create_session_factory(cast(Engine, db_session.get_bind()))
    request = profile_request(
        profile_version="echo-profile-2.0",
        profile_schema_version="echo-profile-document-2.0",
        include_personality_synthesis=True,
    )
    snapshot, created = generate_profile(
        factory,
        request,
        settings=settings,
        provider=default_profile_provider_factory(settings),
    )

    assert created is True
    assert snapshot.profile_version == "echo-profile-2.0"
    document = read_document(snapshot)
    synthesis = document.personality_synthesis
    assert synthesis is not None
    assert [item.framework for item in synthesis.framework_assessments] == [
        "big_five",
        "mbti",
    ]
    assert document.evidence_index == []
    assert all(item.evidence_refs == [] for section in document.sections for item in section.items)
    assert "Big Five" in snapshot.markdown_content
    assert "MBTI" in snapshot.markdown_content
    assert "证据索引" not in snapshot.markdown_content
    exported = json.dumps(snapshot.json_content)
    assert "profile_evidence_ref" not in exported
    assert "message_id" not in exported
    assert "conversation_id" not in exported


def test_profile_one_remains_readable_with_legacy_evidence_presentation(
    db_session: Session,
    settings: Settings,
) -> None:
    create_profile_graph(db_session)
    factory = create_session_factory(cast(Engine, db_session.get_bind()))
    snapshot, _ = generate_profile(
        factory,
        profile_request(
            profile_version="echo-profile-1.0",
            profile_schema_version="echo-profile-document-1.0",
        ),
        settings=settings,
    )
    document = read_document(snapshot)
    assert document.personality_synthesis is None
    assert document.evidence_index
    assert "证据索引" in snapshot.markdown_content


def test_default_profile_provider_is_local_mock(settings: Settings) -> None:
    provider = default_profile_provider_factory(settings)
    assert isinstance(provider, LLMProvider)
    assert provider.provider_name == "mock"
    assert provider.supports_remote_calls is False
