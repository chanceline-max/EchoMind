"""Construct one EchoProfileDocument used by both renderers."""

from collections import defaultdict
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from echomind.models.enums import EvidenceState, InsightType
from echomind.profiling.fingerprints import (
    build_source_manifest,
    document_hash,
    generation_fingerprint,
)
from echomind.profiling.json_renderer import render_json
from echomind.profiling.markdown import render_markdown
from echomind.profiling.options import ProfileGenerationRequest
from echomind.profiling.schemas import (
    BuiltProfile,
    EchoProfileDocument,
    ProfileDocumentMetadata,
    ProfileEvidenceItem,
    ProfileInsightItem,
    ProfileSection,
)
from echomind.profiling.sections import SECTION_DEFINITIONS, route_section, sort_section_items
from echomind.repositories.profile_repository import ProfileEvidenceSource, ProfileInsightSource

BASE_LIMITATIONS = (
    "Profile 只基于当前已确认 Insight。",
    "未确认、已驳回和已被取代的 Insight 未作为有效内容纳入。",
    "confidence 是机械证据支撑强度，不是科学概率。",
    "Profile 不构成医疗、心理或人格诊断。",
    "Evidence 可能随消息排除或数据变化而失效。",
    "历史快照不会随源数据变化自动修改。",
    "stale 快照可能不代表当前最新审核状态。",
    "contradiction 表示冲突证据存在，不代表某一方正确。",
    "hypothesis 仍需要未来验证。",
)


def _warnings(item: ProfileInsightSource) -> list[str]:
    warnings: list[str] = []
    if item.evidence_state == EvidenceState.PARTIAL:
        warnings.append("部分证据已失效。")
    if item.evidence_state == EvidenceState.INVALID:
        warnings.append("该判断当前没有有效 Evidence，不能作为当前有效结论使用。")
    if item.insight_type == InsightType.HYPOTHESIS:
        warnings.append("待验证假设。")
    if item.insight_type == InsightType.CONTRADICTION:
        warnings.append("此分数表示冲突证据的存在受到支持，不代表某一方正确。")
    return warnings


def _evidence_item(
    source: ProfileEvidenceSource, ref: str, request: ProfileGenerationRequest
) -> ProfileEvidenceItem:
    return ProfileEvidenceItem(
        profile_evidence_ref=ref,
        evidence_id=source.evidence_id,
        message_id=source.message_id,
        conversation_id=source.conversation_id,
        evidence_type=source.evidence_type,
        role=source.role,
        relevance_score=source.relevance_score,
        is_valid=source.is_valid,
        invalidation_reasons=list(source.invalidation_reasons),
        message_timestamp=source.message_timestamp,
        sender_role=source.sender_role,
        excerpt=source.excerpt if request.evidence_mode == "excerpts" else None,
    )


def build_profile(
    sources: list[ProfileInsightSource],
    request: ProfileGenerationRequest,
    *,
    generated_at: datetime,
) -> BuiltProfile:
    manifest, source_fingerprint = build_source_manifest(sources, request)
    generation = generation_fingerprint(source_fingerprint, request)
    profile_id = str(uuid5(NAMESPACE_URL, f"echomind:{generation}"))

    visible: list[ProfileInsightSource] = []
    for item in sources:
        if item.evidence_state == EvidenceState.PARTIAL and not request.include_partial_evidence:
            continue
        if item.evidence_state == EvidenceState.INVALID and not request.include_invalidated:
            continue
        visible.append(item)

    by_section: dict[str, list[ProfileInsightSource]] = defaultdict(list)
    for item in visible:
        by_section[route_section(item)].append(item)
    ordered_sources: list[ProfileInsightSource] = []
    for section_key, _, _ in SECTION_DEFINITIONS:
        sort_section_items(section_key, by_section[section_key])
        ordered_sources.extend(by_section[section_key])

    insight_refs = {item.id: f"I{index:03d}" for index, item in enumerate(ordered_sources, 1)}
    evidence_sources = {
        evidence.evidence_id: evidence for item in ordered_sources for evidence in item.evidence
    }
    ordered_evidence = sorted(
        evidence_sources.values(),
        key=lambda item: (
            item.message_timestamp is None,
            item.message_timestamp.isoformat() if item.message_timestamp else "",
            item.conversation_id,
            item.message_id,
            item.evidence_id,
        ),
    )
    evidence_refs = {
        item.evidence_id: f"E{index:03d}" for index, item in enumerate(ordered_evidence, 1)
    }
    sections: list[ProfileSection] = []
    for section_key, title, description in SECTION_DEFINITIONS:
        items: list[ProfileInsightItem] = []
        for source in by_section[section_key]:
            valid_count = sum(item.is_valid for item in source.evidence)
            factors = source.confidence_factors or {}
            items.append(
                ProfileInsightItem(
                    profile_insight_ref=insight_refs[source.id],
                    insight_id=source.id,
                    insight_revision_number=source.revision_number,
                    insight_type=source.insight_type,
                    category=source.category,
                    title=source.title,
                    statement=source.statement,
                    confidence=source.confidence,
                    confidence_version=source.confidence_version,
                    confidence_explanation=source.confidence_explanation
                    or "当前证据在机械规则下的支撑强度，不是科学概率。",
                    evidence_state=source.evidence_state,
                    explicit_self_report=source.explicit_self_report,
                    valid_from=source.valid_from,
                    valid_to=source.valid_to,
                    reasoning_basis=source.reasoning_basis if request.include_reasoning else None,
                    alternative_explanations=(
                        list(source.alternative_explanations) if request.include_reasoning else []
                    ),
                    evidence_refs=[evidence_refs[item.evidence_id] for item in source.evidence],
                    warnings=_warnings(source),
                    minimum_rule_code=(
                        str(factors.get("minimum_rule_code"))
                        if factors.get("minimum_rule_code") is not None
                        else None
                    ),
                    valid_evidence_count=valid_count,
                    invalid_evidence_count=len(source.evidence) - valid_count,
                )
            )
        sections.append(
            ProfileSection(
                section_key=section_key,
                title=title,
                description=description,
                items=items,
            )
        )

    limitations = list(BASE_LIMITATIONS)
    if request.evidence_mode == "excerpts":
        limitations.append("excerpts 模式可能包含敏感聊天片段，请妥善保管导出文件。")
    valid_count = sum(item.evidence_state == EvidenceState.VALID for item in visible)
    partial_count = sum(item.evidence_state == EvidenceState.PARTIAL for item in visible)
    invalid_count = sum(item.evidence_state == EvidenceState.INVALID for item in sources)
    conversations = {item.conversation_id for item in ordered_evidence}
    source_files = {item.source_file_id for item in ordered_evidence}
    metadata = ProfileDocumentMetadata(
        profile_id=profile_id,
        profile_version=request.profile_version,
        schema_version=request.profile_schema_version,
        generated_at=generated_at,
        generated_as_of=request.generated_as_of,
        selection_policy="confirmed-only-1.0",
        scope=request.scope,
        evidence_mode=request.evidence_mode,
        source_fingerprint=source_fingerprint,
        generation_fingerprint=generation,
        document_hash="",
        confirmed_insight_count=len(sources),
        included_valid_count=valid_count,
        included_partial_count=partial_count,
        invalidated_count=invalid_count,
        excluded_count=len(sources) - len(visible),
        evidence_count=len(ordered_evidence),
        conversation_count=len(conversations),
        source_file_count=len(source_files),
        limitations=limitations,
    )
    document = EchoProfileDocument(
        metadata=metadata,
        sections=sections,
        evidence_index=[
            _evidence_item(item, evidence_refs[item.evidence_id], request)
            for item in ordered_evidence
        ],
    )
    metadata.document_hash = document_hash(document.model_dump(mode="json"))
    json_content = render_json(document)
    markdown_content = render_markdown(document)
    return BuiltProfile(
        document=document,
        markdown_content=markdown_content,
        json_content=json_content,
        source_manifest=manifest,
        generation_options=request.safe_options(),
    )
