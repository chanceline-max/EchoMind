"""Immutable snapshot conversion and integrity validation."""

import json
from datetime import datetime

from pydantic import ValidationError

from echomind.models.enums import EvidenceState
from echomind.models.profile_snapshot import ProfileSnapshot
from echomind.profiling.errors import ProfileError
from echomind.profiling.fingerprints import document_hash
from echomind.profiling.schemas import BuiltProfile, EchoProfileDocument


def to_snapshot(built: BuiltProfile) -> ProfileSnapshot:
    document = built.document
    evidence_states = [
        item.evidence_state for section in document.sections for item in section.items
    ]
    historical_state = EvidenceState.VALID
    if EvidenceState.INVALID in evidence_states:
        historical_state = EvidenceState.INVALID
    elif EvidenceState.PARTIAL in evidence_states:
        historical_state = EvidenceState.PARTIAL
    timestamps = [
        item.message_timestamp for item in document.evidence_index if item.message_timestamp
    ]
    return ProfileSnapshot(
        id=document.metadata.profile_id,
        generated_at=document.metadata.generated_at,
        profile_version=document.metadata.profile_version,
        schema_version=document.metadata.schema_version,
        markdown_content=built.markdown_content,
        json_content=json.loads(built.json_content),
        source_range_start=min(timestamps) if timestamps else None,
        source_range_end=max(timestamps) if timestamps else None,
        statistics={
            "confirmed_insight_count": document.metadata.confirmed_insight_count,
            "included_valid_count": document.metadata.included_valid_count,
            "included_partial_count": document.metadata.included_partial_count,
            "invalidated_count": document.metadata.invalidated_count,
            "excluded_count": document.metadata.excluded_count,
        },
        limitations=document.metadata.limitations,
        evidence_state=historical_state,
        invalidated_at=(
            document.metadata.generated_at if historical_state == EvidenceState.INVALID else None
        ),
        metadata_json={"selection_policy": document.metadata.selection_policy},
        source_fingerprint=document.metadata.source_fingerprint,
        generation_fingerprint=document.metadata.generation_fingerprint,
        document_hash=document.metadata.document_hash,
        generation_options_json=built.generation_options,
        source_manifest_json=[item.model_dump(mode="json") for item in built.source_manifest],
        insight_count=document.metadata.confirmed_insight_count,
        evidence_count=document.metadata.evidence_count,
        source_status_at_generation="current",
    )


def restore_document(snapshot: ProfileSnapshot) -> EchoProfileDocument:
    if not snapshot.document_hash:
        raise ProfileError(
            "profile_snapshot_integrity_failed",
            "This Profile snapshot does not contain an integrity hash.",
            status_code=409,
        )
    actual = document_hash(snapshot.json_content)
    if actual != snapshot.document_hash:
        raise ProfileError(
            "profile_snapshot_integrity_failed",
            "The Profile snapshot integrity check failed.",
            status_code=409,
            details={"expected": snapshot.document_hash, "actual": actual},
        )
    try:
        return EchoProfileDocument.model_validate(snapshot.json_content)
    except ValidationError as error:
        raise ProfileError(
            "profile_document_invalid",
            "The stored Profile document is invalid.",
            status_code=409,
        ) from error


def safe_generated_date(value: datetime) -> str:
    return value.strftime("%Y%m%d-%H%M%SZ")
