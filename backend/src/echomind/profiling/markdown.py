"""Safe, deterministic Markdown rendering without HTML or third-party parsers."""

import re
from datetime import datetime

from echomind.profiling.schemas import (
    EchoProfileDocument,
    PersonalityFrameworkAssessment,
    PersonalitySynthesis,
    ProfileEvidenceItem,
    ProfileInsightItem,
)

_URL_SCHEME = re.compile(r"(?i)\b(https?)://")


def escape_markdown(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace("<", "&lt;").replace(">", "&gt;").replace("`", "&#96;")
    escaped = re.sub(r"([\[\]()*_#!|])", r"\\\1", escaped)
    escaped = re.sub(r"(?m)^([+\-])(?=\s)", r"\\\1", escaped)
    escaped = _URL_SCHEME.sub(lambda match: f"{match.group(1)}&#58;//", escaped)
    return escaped


def _time(value: datetime | None) -> str:
    return "未指定" if value is None else value.isoformat().replace("+00:00", "Z")


def _insight(lines: list[str], item: ProfileInsightItem) -> None:
    lines.extend(
        [
            f"### {item.profile_insight_ref} · {escape_markdown(item.title)}",
            "",
            f"- 类型：{item.insight_type.value}",
            f"- 分类：{escape_markdown(item.category)}",
            f"- Evidence 状态：{item.evidence_state.value}",
            f"- 支撑强度：{item.confidence:.4f}（{escape_markdown(item.confidence_version)}）",
            f"- 有效时间：{_time(item.valid_from)} — {_time(item.valid_to)}",
            f"- Evidence：{' '.join(f'[{ref}]' for ref in item.evidence_refs) or '无'}",
        ]
    )
    for warning in item.warnings:
        lines.append(f"- 警告：{escape_markdown(warning)}")
    lines.extend(["", escape_markdown(item.statement), ""])
    if item.reasoning_basis:
        lines.extend([f"- 推理依据：{escape_markdown(item.reasoning_basis)}", ""])
    if item.alternative_explanations:
        lines.extend(
            [
                "- 其他可能解释："
                + "；".join(escape_markdown(value) for value in item.alternative_explanations),
                "",
            ]
        )


def _evidence(lines: list[str], item: ProfileEvidenceItem) -> None:
    lines.extend(
        [
            f"### {item.profile_evidence_ref}",
            "",
            f"- 立场：{item.role}",
            f"- 时间：{_time(item.message_timestamp)}",
            f"- 来源角色：{item.sender_role}",
            f"- 当前状态：{'valid' if item.is_valid else 'invalid'}",
            "- 失效原因："
            + ("、".join(escape_markdown(value) for value in item.invalidation_reasons) or "无"),
            f"- 本地追溯：conversation={item.conversation_id} message={item.message_id}",
        ]
    )
    if item.excerpt is not None:
        lines.append(f"- 摘录：{escape_markdown(item.excerpt)}")
    lines.append("")


def _framework(lines: list[str], item: PersonalityFrameworkAssessment) -> None:
    lines.extend(
        [
            f"### {escape_markdown(item.display_name)}",
            "",
            f"**参考结果：{escape_markdown(item.result)}**",
            "",
            escape_markdown(item.summary),
            "",
            "| 维度 | 倾向 | 说明 |",
            "|---|---|---|",
        ]
    )
    for dimension in item.dimensions:
        lines.append(
            "| "
            + " | ".join(
                (
                    escape_markdown(dimension.label),
                    escape_markdown(dimension.tendency),
                    escape_markdown(dimension.summary),
                )
            )
            + " |"
        )
    lines.extend(["", *[f"- 边界：{escape_markdown(value)}" for value in item.caveats], ""])


def _synthesis(lines: list[str], synthesis: PersonalitySynthesis) -> None:
    lines.extend(
        [
            "# EchoProfile 综合人格分析",
            "",
            "> AI 辅助的倾向分析，不是心理诊断或正式人格测评。",
            "",
            "## 1. 综合人格类型",
            "",
            f"# {escape_markdown(synthesis.headline)}",
            "",
            escape_markdown(synthesis.overall_summary),
            "",
            "## 2. 核心性格特征",
            "",
            *[f"- {escape_markdown(value)}" for value in synthesis.core_traits],
            "",
            "## 3. 思考与信息处理方式",
            "",
            escape_markdown(synthesis.thinking_style),
            "",
            "## 4. 决策与行动模式",
            "",
            escape_markdown(synthesis.decision_style),
            "",
            "## 5. 价值观与内在驱动力",
            "",
            escape_markdown(synthesis.motivation_and_values),
            "",
            "## 6. 社交与关系模式",
            "",
            escape_markdown(synthesis.social_and_relationship_style),
            "",
            "## 7. 情绪与压力模式",
            "",
            escape_markdown(synthesis.emotional_and_stress_patterns),
            "",
            "## 8. 可能的优势",
            "",
            *[f"- {escape_markdown(value)}" for value in synthesis.strengths],
            "",
            "## 9. 潜在盲区与成长方向",
            "",
            *[f"- {escape_markdown(value)}" for value in synthesis.growth_edges],
            "",
            "## 10. 内在矛盾与变化",
            "",
            *(
                [f"- {escape_markdown(value)}" for value in synthesis.tensions_and_changes]
                or ["- 暂未识别到足够稳定的矛盾或变化。"]
            ),
            "",
            "## 11. 人格框架参考",
            "",
        ]
    )
    for framework in synthesis.framework_assessments:
        _framework(lines, framework)
    lines.extend(
        [
            "## 12. 不确定性与适用边界",
            "",
            escape_markdown(synthesis.uncertainty_note),
            "",
        ]
    )


def render_markdown(document: EchoProfileDocument) -> str:
    metadata = document.metadata
    if document.personality_synthesis is not None:
        lines: list[str] = []
        _synthesis(lines, document.personality_synthesis)
        lines.extend(["## 13. 档案信息", ""])
        lines.extend(
            [
                f"- Profile 版本：{metadata.profile_version}",
                f"- Schema 版本：{metadata.schema_version}",
                f"- 生成时间：{_time(metadata.generated_at)}",
                f"- 已确认 Insight：{metadata.confirmed_insight_count}",
                "- 当前来源状态：current（历史快照读取时动态检测）",
                "",
                "## 14. 局限性说明",
                "",
                *[f"- {escape_markdown(value)}" for value in metadata.limitations],
            ]
        )
        return "\n".join(lines).rstrip("\n") + "\n"
    displayed_insight_count = sum(len(section.items) for section in document.sections)
    lines = [
        "# EchoProfile",
        "",
        "## 0. 档案说明",
        "",
        f"- Profile 版本：{metadata.profile_version}",
        f"- Schema 版本：{metadata.schema_version}",
        f"- 生成时间：{_time(metadata.generated_at)}",
        f"- 来源策略：{metadata.selection_policy}",
        f"- Evidence 模式：{metadata.evidence_mode}",
        f"- Insight 数量：{displayed_insight_count}",
        f"- Evidence 数量：{metadata.evidence_count}",
        "- 当前来源状态：current（读取历史快照时另行动态检测）",
        "- 重要局限：置信度是机械证据支撑强度，不是科学概率。",
        "",
    ]
    for index, section in enumerate(document.sections, start=1):
        lines.extend([f"## {index}. {section.title}", "", escape_markdown(section.description), ""])
        for item in section.items:
            _insight(lines, item)
    evidence_number = len(document.sections) + 1
    lines.extend([f"## {evidence_number}. 证据索引", ""])
    for evidence_item in document.evidence_index:
        _evidence(lines, evidence_item)
    lines.extend([f"## {evidence_number + 1}. 局限性说明", ""])
    lines.extend(f"- {escape_markdown(value)}" for value in metadata.limitations)
    return "\n".join(lines).rstrip("\n") + "\n"
