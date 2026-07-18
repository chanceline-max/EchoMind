"""Versioned SHA-256 over content-free confidence inputs."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from echomind.confidence.factors import InsightFeatures

FINGERPRINT_VERSION = "confidence-input-1.0"


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _number(value: float) -> str:
    return format(Decimal(str(value)), "f")


def confidence_input_fingerprint(
    feature: InsightFeatures,
    *,
    confidence_version: str,
    as_of: datetime,
) -> str:
    evidence = [
        {
            "conversation_id": item.conversation_id,
            "evidence_fingerprint": item.evidence_fingerprint,
            "evidence_id": item.evidence_id,
            "evidence_type": item.evidence_type,
            "invalidated_at": _time(item.invalidated_at),
            "is_profile_owner": item.is_profile_owner,
            "is_valid": item.is_valid,
            "message_id": item.message_id,
            "relevance_score": _number(item.relevance_score),
            "sender_id": item.sender_id,
            "stance": item.stance.value,
            "timestamp": _time(item.timestamp),
        }
        for item in sorted(feature.evidence, key=lambda value: value.evidence_id)
    ]
    payload = {
        "as_of": _time(as_of),
        "confidence_version": confidence_version,
        "evidence": evidence,
        "explicit_self_report": feature.explicit_self_report,
        "extraction_version": feature.extraction_version,
        "fingerprint_version": FINGERPRINT_VERSION,
        "has_alternative_explanations": feature.has_alternative_explanations,
        "has_reasoning_basis": feature.has_reasoning_basis,
        "insight_fingerprint": feature.insight_fingerprint,
        "insight_id": feature.insight_id,
        "insight_type": feature.insight_type.value,
        "valid_from": _time(feature.valid_from),
        "valid_to": _time(feature.valid_to),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
