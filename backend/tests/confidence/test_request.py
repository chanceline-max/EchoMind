"""Strict, explicit confidence recalculation request boundaries."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from echomind.confidence.options import ConfidenceCalculationRequest


def test_request_deduplicates_ids_stably_and_normalizes_as_of_to_utc() -> None:
    first, second = uuid4(), uuid4()
    request = ConfidenceCalculationRequest(
        insight_ids=[first, second, first],
        as_of=datetime(2026, 7, 19, 8, tzinfo=timezone(timedelta(hours=8))),
    )

    assert request.insight_ids == [first, second]
    assert request.as_of == datetime(2026, 7, 19, tzinfo=UTC)


@pytest.mark.parametrize(
    "updates",
    [
        {"insight_ids": []},
        {"as_of": datetime(2026, 7, 19)},
        {"confidence_version": "confidence-2.0"},
        {"unexpected": True},
    ],
)
def test_invalid_request_is_rejected(updates: dict[str, object]) -> None:
    values: dict[str, object] = {
        "insight_ids": [uuid4()],
        "as_of": datetime(2026, 7, 19, tzinfo=UTC),
    }
    values.update(updates)
    with pytest.raises(ValidationError):
        ConfidenceCalculationRequest.model_validate(values)


def test_request_defaults_do_not_select_skipped_statuses_or_force_writes() -> None:
    request = ConfidenceCalculationRequest(
        insight_ids=[uuid4()],
        as_of=datetime(2026, 7, 19, tzinfo=UTC),
    )

    assert request.include_rejected is False
    assert request.include_superseded is False
    assert request.force_recalculate is False
    assert request.stop_on_error is True
