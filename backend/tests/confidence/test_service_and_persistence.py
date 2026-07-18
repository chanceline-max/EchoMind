"""Database persistence, idempotency, recalculation, status and privacy."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from echomind.confidence import ConfidenceCalculationRequest, calculate_confidence
from echomind.models import Evidence, Insight, Message, Participant
from echomind.models.enums import EvidenceState, InsightStatus, InsightType
from tests.confidence.factories import AS_OF, CALCULATED_AT, create_confidence_graph
from tests.extraction.factories import session_factory_for


def request(insight: Insight, **updates: object) -> ConfidenceCalculationRequest:
    values: dict[str, object] = {"insight_ids": [UUID(insight.id)], "as_of": AS_OF}
    values.update(updates)
    return ConfidenceCalculationRequest.model_validate(values)


def test_unscored_insight_is_persisted_with_all_stage_eight_fields(
    db_session: Session,
) -> None:
    insight, _ = create_confidence_graph(db_session)
    original = (insight.title, insight.statement, insight.status, insight.model_confidence)
    report = calculate_confidence(
        session_factory_for(db_session), request(insight), calculated_at=CALCULATED_AT
    )
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert report.scored_count == 1
    assert stored.confidence_version == "confidence-1.0"
    assert stored.confidence_input_fingerprint is not None
    assert stored.confidence_factors_json is not None
    assert stored.confidence_factors_json["minimum_rule_passed"] is True
    assert stored.confidence_factors_json["minimum_rule_code"] == "passed"
    assert stored.confidence_explanation is not None
    assert stored.confidence_as_of == AS_OF
    assert stored.confidence_calculated_at == CALCULATED_AT
    assert (stored.title, stored.statement, stored.status, stored.model_confidence) == original


def test_second_identical_run_does_not_update_or_change_calculated_at(
    db_session: Session,
) -> None:
    insight, _ = create_confidence_graph(db_session)
    factory = session_factory_for(db_session)
    calculate_confidence(factory, request(insight), calculated_at=CALCULATED_AT)
    updates = 0

    def count_updates(*args: object) -> None:
        nonlocal updates
        statement = str(args[2])
        if statement.lstrip().upper().startswith("UPDATE INSIGHTS"):
            updates += 1

    event.listen(db_session.get_bind(), "before_cursor_execute", count_updates)
    try:
        report = calculate_confidence(
            factory,
            request(insight),
            calculated_at=CALCULATED_AT + timedelta(hours=1),
        )
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", count_updates)
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert report.unchanged_count == 1
    assert report.results[0].changed is False
    assert stored.confidence_calculated_at == CALCULATED_AT
    assert updates == 0


def test_force_recalculate_only_refreshes_persistence_time(db_session: Session) -> None:
    insight, _ = create_confidence_graph(db_session)
    factory = session_factory_for(db_session)
    first = calculate_confidence(factory, request(insight), calculated_at=CALCULATED_AT)
    second = calculate_confidence(
        factory,
        request(insight, force_recalculate=True),
        calculated_at=CALCULATED_AT + timedelta(hours=1),
    )
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert first.results[0].final_confidence == second.results[0].final_confidence
    assert second.results[0].changed is True
    assert stored.confidence_calculated_at == CALCULATED_AT + timedelta(hours=1)


def test_evidence_invalidation_recalculates_state_and_score(db_session: Session) -> None:
    insight, evidence = create_confidence_graph(db_session)
    factory = session_factory_for(db_session)
    calculate_confidence(factory, request(insight), calculated_at=CALCULATED_AT)
    db_session.expire_all()
    previous = db_session.get(Insight, insight.id)
    assert previous is not None
    previous_confidence = previous.confidence
    evidence[0].is_valid = False
    evidence[0].invalidated_at = AS_OF - timedelta(days=1)
    db_session.commit()
    report = calculate_confidence(
        factory, request(insight), calculated_at=CALCULATED_AT + timedelta(hours=1)
    )
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert previous_confidence > 0
    assert stored.confidence == 0.0
    assert stored.evidence_state is EvidenceState.INVALID
    assert stored.status is InsightStatus.PROPOSED
    assert report.results[0].input_fingerprint_changed is True


def test_partial_state_uses_only_valid_evidence_but_keeps_valid_ratio(
    db_session: Session,
) -> None:
    insight, evidence = create_confidence_graph(db_session, evidence_count=2)
    evidence[1].is_valid = False
    evidence[1].invalidated_at = AS_OF - timedelta(days=1)
    db_session.commit()
    calculate_confidence(
        session_factory_for(db_session), request(insight), calculated_at=CALCULATED_AT
    )
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert stored.confidence_factors_json is not None
    assert stored.evidence_state is EvidenceState.PARTIAL
    assert stored.confidence_factors_json["valid_evidence_count"] == 1
    assert stored.confidence_factors_json["invalid_evidence_count"] == 1
    assert stored.confidence_factors_json["valid_ratio"] == 0.5


def test_rejected_and_superseded_are_skipped_by_default_but_can_be_included(
    db_session: Session,
) -> None:
    rejected, _ = create_confidence_graph(db_session, status=InsightStatus.REJECTED)
    report = calculate_confidence(
        session_factory_for(db_session), request(rejected), calculated_at=CALCULATED_AT
    )
    assert report.skipped_rejected_count == 1
    assert report.scored_count == 0
    included = calculate_confidence(
        session_factory_for(db_session),
        request(rejected, include_rejected=True),
        calculated_at=CALCULATED_AT,
    )
    assert included.scored_count == 1
    stored = db_session.get(Insight, rejected.id)
    assert stored is not None
    assert stored.status is InsightStatus.REJECTED

    stored.status = InsightStatus.SUPERSEDED
    stored.confidence_version = "unscored"
    stored.confidence_input_fingerprint = None
    db_session.commit()
    skipped = calculate_confidence(
        session_factory_for(db_session), request(stored), calculated_at=CALCULATED_AT
    )
    assert skipped.skipped_superseded_count == 1
    included = calculate_confidence(
        session_factory_for(db_session),
        request(stored, include_superseded=True),
        calculated_at=CALCULATED_AT,
    )
    assert included.scored_count == 1


def test_confirmed_insight_is_scored(db_session: Session) -> None:
    insight, _ = create_confidence_graph(db_session, status=InsightStatus.CONFIRMED)
    report = calculate_confidence(
        session_factory_for(db_session), request(insight), calculated_at=CALCULATED_AT
    )
    assert report.scored_count == 1
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert stored.status is InsightStatus.CONFIRMED


def test_missing_ids_stop_or_continue_without_silent_ignoring(db_session: Session) -> None:
    insight, _ = create_confidence_graph(db_session)
    missing = uuid4()
    stop = ConfidenceCalculationRequest(
        insight_ids=[missing, UUID(insight.id)], as_of=AS_OF, stop_on_error=True
    )
    stopped = calculate_confidence(
        session_factory_for(db_session), stop, calculated_at=CALCULATED_AT
    )
    assert stopped.failed_count == 1
    assert stopped.stopped_early is True
    assert stopped.scored_count == 0
    keep_going = stop.model_copy(update={"stop_on_error": False})
    continued = calculate_confidence(
        session_factory_for(db_session), keep_going, calculated_at=CALCULATED_AT
    )
    assert continued.failed_count == 1
    assert continued.scored_count == 1


def test_contradiction_roles_incomplete_is_persisted_as_zero_safely(
    db_session: Session,
) -> None:
    insight, _ = create_confidence_graph(db_session, insight_type=InsightType.CONTRADICTION)
    report = calculate_confidence(
        session_factory_for(db_session), request(insight), calculated_at=CALCULATED_AT
    )
    assert report.failed_count == 0
    assert report.minimum_rule_failed_count == 1
    assert report.results[0].error_code == "contradiction_roles_incomplete"
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert stored.confidence == 0.0


def test_report_factors_and_explanation_do_not_expose_content(db_session: Session) -> None:
    insight, evidence = create_confidence_graph(db_session)
    report = calculate_confidence(
        session_factory_for(db_session), request(insight), calculated_at=CALCULATED_AT
    )
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    serialized = (
        report.model_dump_json()
        + str(stored.confidence_factors_json)
        + str(stored.confidence_explanation)
    )
    for forbidden in [
        insight.title,
        insight.statement,
        evidence[0].excerpt,
        "RAW_PRIVATE",
        "Private Name",
        "SELECT ",
        "E:\\private",
    ]:
        assert forbidden not in serialized


def test_database_queries_project_no_chat_or_evidence_content(db_session: Session) -> None:
    insight, _ = create_confidence_graph(db_session)
    statements: list[str] = []

    def capture_statement(*args: object) -> None:
        statements.append(str(args[2]).casefold())

    event.listen(db_session.get_bind(), "before_cursor_execute", capture_statement)
    try:
        calculate_confidence(
            session_factory_for(db_session), request(insight), calculated_at=CALCULATED_AT
        )
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture_statement)
    sql = "\n".join(statements)
    for forbidden_column in [
        "insights.title",
        "insights.statement",
        "evidence.excerpt",
        "messages.raw_content",
        "messages.normalized_content",
        "participants.canonical_name",
        "source_files.filename",
    ]:
        assert forbidden_column not in sql


def test_model_confidence_change_does_not_trigger_recalculation(db_session: Session) -> None:
    insight, _ = create_confidence_graph(db_session)
    factory = session_factory_for(db_session)
    calculate_confidence(factory, request(insight), calculated_at=CALCULATED_AT)
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    first_fingerprint = stored.confidence_input_fingerprint
    first_confidence = stored.confidence
    stored.model_confidence = 0.1
    db_session.commit()
    report = calculate_confidence(
        factory, request(stored), calculated_at=CALCULATED_AT + timedelta(hours=1)
    )
    assert report.unchanged_count == 1
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert stored.confidence_input_fingerprint == first_fingerprint
    assert stored.confidence == first_confidence


def test_content_and_display_edits_do_not_change_confidence_input_fingerprint(
    db_session: Session,
) -> None:
    insight, evidence = create_confidence_graph(db_session)
    factory = session_factory_for(db_session)
    calculate_confidence(factory, request(insight), calculated_at=CALCULATED_AT)
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    fingerprint = stored.confidence_input_fingerprint
    stored.title = "Edited title"
    stored.statement = "Edited statement"
    evidence_row = db_session.get(Evidence, evidence[0].id)
    assert evidence_row is not None
    evidence_row.excerpt = "Edited excerpt without changing the stored evidence fingerprint"
    evidence_row.excerpt_end = len(evidence_row.excerpt)
    message = db_session.get(Message, evidence_row.message_id)
    assert message is not None
    message.raw_content = "Edited raw content"
    message.normalized_content = "Edited normalized content"
    participant = db_session.get(Participant, message.sender_id)
    assert participant is not None
    participant.canonical_name = "Edited display name"
    db_session.commit()
    report = calculate_confidence(
        factory, request(stored), calculated_at=CALCULATED_AT + timedelta(hours=1)
    )
    assert report.unchanged_count == 1
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert stored.confidence_input_fingerprint == fingerprint


def test_relevance_change_triggers_recalculation(db_session: Session) -> None:
    insight, evidence = create_confidence_graph(db_session)
    factory = session_factory_for(db_session)
    calculate_confidence(factory, request(insight), calculated_at=CALCULATED_AT)
    evidence[0].relevance_score = 0.1
    db_session.commit()
    report = calculate_confidence(
        factory, request(insight), calculated_at=CALCULATED_AT + timedelta(hours=1)
    )
    assert report.results[0].input_fingerprint_changed is True
    assert report.results[0].changed is True


def test_multiple_profile_owners_fail_safely_without_updating_insight(
    db_session: Session,
) -> None:
    insight, _ = create_confidence_graph(db_session)
    other = db_session.scalar(select(Participant).where(Participant.is_profile_owner.is_(False)))
    assert other is not None
    other.is_profile_owner = True
    db_session.commit()
    report = calculate_confidence(
        session_factory_for(db_session), request(insight), calculated_at=CALCULATED_AT
    )
    assert report.failed_count == 1
    assert report.errors[0].error_code == "profile_owner_inconsistent"
    db_session.expire_all()
    stored = db_session.get(Insight, insight.id)
    assert stored is not None
    assert stored.confidence_version == "unscored"


def test_evidence_rows_are_not_modified_by_scoring(db_session: Session) -> None:
    insight, evidence = create_confidence_graph(db_session)
    before = (evidence[0].excerpt, evidence[0].relevance_score, evidence[0].is_valid)
    calculate_confidence(
        session_factory_for(db_session), request(insight), calculated_at=CALCULATED_AT
    )
    db_session.expire_all()
    stored = db_session.scalar(select(Evidence).where(Evidence.id == evidence[0].id))
    assert stored is not None
    assert (stored.excerpt, stored.relevance_score, stored.is_valid) == before
