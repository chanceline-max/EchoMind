"""Fixed local explanation templates; no model and no chat content."""

from echomind.confidence.schemas import ConfidenceFactors, MinimumRuleCode
from echomind.models.enums import EvidenceState, InsightType


def build_explanation(
    *,
    insight_type: InsightType,
    evidence_state: EvidenceState,
    factors: ConfidenceFactors,
    minimum_rule_passed: bool,
    minimum_rule_code: MinimumRuleCode,
) -> str:
    if evidence_state is EvidenceState.INVALID:
        opening = "当前没有有效证据，支撑强度设为 0.0；Insight 保留并标记为证据失效。"
    elif not minimum_rule_passed:
        opening = (
            f"当前证据未满足 {minimum_rule_code.value} 最低规则，"
            "支撑强度按保守规则设为 0.0，Insight 状态不变。"
        )
    else:
        opening = f"当前支撑强度为 {factors.final_confidence:.4f}。"
    contradiction = (
        f"发现 {factors.contradicting_evidence_count} 条有效相反证据，"
        "它会降低普通判断的当前支撑强度。"
        if factors.contradicting_evidence_count
        else "未发现有效相反证据。"
    )
    span = (
        f"证据覆盖 {factors.unique_timestamp_count} 个时间点"
        if factors.unique_timestamp_count
        else "证据未形成有效时间点"
    )
    special = ""
    if insight_type is InsightType.HYPOTHESIS:
        special = "该类型为待验证假设，confidence-1.0 的最高值限制为 0.60。"
    elif insight_type is InsightType.CONTRADICTION:
        special = "该分数表示相互冲突证据的存在得到多大程度支撑，不代表其中某一方正确。"
    explanation = (
        f"{opening} 当前证据状态为 {evidence_state.value}；基于 "
        f"{factors.valid_evidence_count} 条有效证据和 "
        f"{factors.invalid_evidence_count} 条无效证据，{span}、"
        f"分布在 {factors.unique_conversation_count} 个会话，其中 "
        f"{factors.owner_evidence_count} 条来自档案所有者。{contradiction} "
        f"该类型上限为 {factors.type_cap:.2f}。{special} "
        "该结果由 confidence-1.0 机械规则计算，可在证据变化后重新计算；"
        "它不是结论为真的科学概率，也不是对用户可信程度的评价。"
        "模型自评未参与最终分数。"
    )
    return explanation[:4_000]
