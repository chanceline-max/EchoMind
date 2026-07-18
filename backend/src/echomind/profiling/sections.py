"""Versioned section routing and deterministic in-section ordering."""

from datetime import datetime

from echomind.models.enums import EvidenceState, InsightType
from echomind.repositories.profile_repository import ProfileInsightSource

SECTION_MAPPING_VERSION = "profile-sections-1.0"
SECTION_DEFINITIONS = (
    ("background", "基础背景", "用户明确确认的背景事实。"),
    ("preferences", "稳定偏好", "明确表达或跨场景稳定出现的偏好。"),
    ("thinking_patterns", "思维模式", "重复出现的思考结构。"),
    ("behavior_execution", "行为与执行模式", "行动和执行中的可观察结构。"),
    ("emotional_responses", "情绪反应模式", "在特定情境中的反应结构，非诊断。"),
    ("relationship_patterns", "人际关系模式", "人际互动中有证据支持的结构。"),
    ("values_motivation", "价值观与核心驱动力", "用户确认的价值取向与动力。"),
    ("internal_conflicts", "内部冲突与张力", "并存但尚未消解的内部张力。"),
    ("temporal_changes", "时间演化", "同一主题在不同时间点的可识别变化。"),
    ("contradictions", "矛盾信息", "当前存在冲突证据的信息。"),
    ("hypotheses", "待验证假设", "有解释力但仍需未来验证的暂定推断。"),
    ("other_confirmed", "其他已确认判断", "无法归入其他章节的已确认判断。"),
    ("invalidated", "证据已失效", "当前没有完整有效证据的历史判断。"),
)


def route_section(item: ProfileInsightSource) -> str:
    if item.evidence_state == EvidenceState.INVALID:
        return "invalidated"
    if item.insight_type == InsightType.CONTRADICTION:
        return "contradictions"
    if item.insight_type == InsightType.HYPOTHESIS:
        return "hypotheses"
    if item.insight_type == InsightType.CHANGE or item.category == "temporal_change":
        return "temporal_changes"
    if item.category == "background":
        return "background"
    if item.insight_type == InsightType.PREFERENCE or item.category == "preference":
        return "preferences"
    mapping = {
        "thinking_pattern": "thinking_patterns",
        "behavior_execution": "behavior_execution",
        "emotional_response": "emotional_responses",
        "relationship_pattern": "relationship_patterns",
        "values_motivation": "values_motivation",
        "internal_conflict": "internal_conflicts",
    }
    return mapping.get(item.category, "other_confirmed")


def _date_key(value: datetime | None) -> tuple[int, str]:
    return (1, "") if value is None else (0, value.isoformat())


def sort_section_items(section_key: str, items: list[ProfileInsightSource]) -> None:
    if section_key == "temporal_changes":
        items.sort(key=lambda item: (_date_key(item.valid_from), _date_key(item.valid_to), item.id))
    elif section_key in {"contradictions", "hypotheses"}:
        items.sort(key=lambda item: (-item.confidence, -item.updated_at.timestamp(), item.id))
    else:
        items.sort(key=lambda item: (-item.confidence, _date_key(item.valid_from), item.id))
