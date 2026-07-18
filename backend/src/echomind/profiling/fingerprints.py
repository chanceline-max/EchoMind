"""Canonical SHA-256 fingerprints for Profile sources, generation, and documents."""

import hashlib
import json
from datetime import datetime
from typing import Any

from echomind.profiling.options import ProfileGenerationRequest
from echomind.profiling.schemas import ProfileSourceManifest
from echomind.repositories.profile_repository import ProfileInsightSource

SOURCE_FINGERPRINT_VERSION = "profile-source-1.0"
GENERATION_FINGERPRINT_VERSION = "profile-generation-1.0"
DOCUMENT_HASH_VERSION = "profile-document-sha256"
MARKDOWN_RENDERER_VERSION = "profile-markdown-1.0"
JSON_RENDERER_VERSION = "profile-json-1.0"


def _value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if hasattr(value, "value"):
        return value.value
    return value


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
        default=_value,
    ).encode("utf-8")


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def build_source_manifest(
    sources: list[ProfileInsightSource], request: ProfileGenerationRequest
) -> tuple[list[ProfileSourceManifest], str]:
    manifest: list[ProfileSourceManifest] = []
    components: list[dict[str, object]] = []
    for item in sorted(sources, key=lambda source: source.id):
        content = {
            "insight_type": item.insight_type.value,
            "category": item.category,
            "title": item.title,
            "statement": item.statement,
            "explicit_self_report": item.explicit_self_report,
            "valid_from": _value(item.valid_from),
            "valid_to": _value(item.valid_to),
            "reasoning_basis": item.reasoning_basis,
            "alternative_explanations": list(item.alternative_explanations),
        }
        evidence = [
            {
                "id": evidence_item.evidence_id,
                "evidence_fingerprint": evidence_item.evidence_fingerprint,
                "evidence_type": evidence_item.evidence_type,
                "role": evidence_item.role,
                "relevance_score": evidence_item.relevance_score,
                "is_valid": evidence_item.is_valid,
                "invalidation_reasons": list(evidence_item.invalidation_reasons),
                "invalidated_at": _value(evidence_item.invalidated_at),
                "message_id": evidence_item.message_id,
                "conversation_id": evidence_item.conversation_id,
                "message_timestamp": _value(evidence_item.message_timestamp),
                "sender_role": evidence_item.sender_role,
            }
            for evidence_item in item.evidence
        ]
        component = {
            "insight_id": item.id,
            "revision_number": item.revision_number,
            "status": item.status.value,
            "confidence": item.confidence,
            "confidence_version": item.confidence_version,
            "confidence_input_fingerprint": item.confidence_input_fingerprint,
            "evidence_state": item.evidence_state.value,
            "content": content,
            "evidence": evidence,
        }
        component_hash = sha256(component)
        components.append(component)
        manifest.append(
            ProfileSourceManifest(
                insight_id=item.id,
                revision_number=item.revision_number,
                status=item.status.value,
                evidence_state=item.evidence_state.value,
                confidence=item.confidence,
                confidence_version=item.confidence_version,
                content_fingerprint=sha256(content),
                evidence_fingerprints=[
                    evidence_item.evidence_fingerprint or "missing"
                    for evidence_item in item.evidence
                ],
                evidence_validity=[evidence_item.is_valid for evidence_item in item.evidence],
                source_fingerprint_component=component_hash,
            )
        )
    source_payload = {
        "version": SOURCE_FINGERPRINT_VERSION,
        "profile_version": request.profile_version,
        "schema_version": request.profile_schema_version,
        "selection_policy": "confirmed-only-1.0",
        "scope": request.scope,
        "selected_insight_ids": [item.id for item in sorted(sources, key=lambda row: row.id)],
        "components": components,
    }
    return manifest, sha256(source_payload)


def generation_fingerprint(source_fingerprint: str, request: ProfileGenerationRequest) -> str:
    return sha256(
        {
            "version": GENERATION_FINGERPRINT_VERSION,
            "source_fingerprint": source_fingerprint,
            "profile_version": request.profile_version,
            "schema_version": request.profile_schema_version,
            "options": request.safe_options(),
            "section_mapping_version": "profile-sections-1.0",
            "markdown_renderer_version": MARKDOWN_RENDERER_VERSION,
            "json_renderer_version": JSON_RENDERER_VERSION,
        }
    )


def document_hash(document_value: dict[str, Any]) -> str:
    payload = json.loads(json.dumps(document_value, ensure_ascii=False, allow_nan=False))
    payload["metadata"]["document_hash"] = ""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
