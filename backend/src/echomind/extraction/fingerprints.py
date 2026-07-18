"""Versioned SHA-256 identifiers with conservative, explainable normalization."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

EVIDENCE_FINGERPRINT_VERSION = "evidence-1.0"


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_statement(statement: str) -> str:
    """Trim and collapse whitespace only; preserve case and punctuation."""
    return " ".join(statement.split())


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def insight_fingerprint(
    *,
    extraction_version: str,
    insight_type: str,
    category: str,
    statement: str,
    valid_from: datetime | None,
    valid_to: datetime | None,
) -> str:
    return _digest(
        {
            "category": category,
            "extraction_version": extraction_version,
            "insight_type": insight_type,
            "statement": normalize_statement(statement),
            "valid_from": _time(valid_from),
            "valid_to": _time(valid_to),
        }
    )


def evidence_fingerprint(*, message_id: str, evidence_type: str, excerpt: str) -> str:
    return _digest(
        {
            "evidence_type": evidence_type,
            "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "message_id": message_id,
            "version": EVIDENCE_FINGERPRINT_VERSION,
        }
    )
