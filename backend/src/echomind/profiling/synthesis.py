"""Bounded, structured personality synthesis from confirmed Insight content."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from echomind.core.config import Settings
from echomind.profiling.options import ProfileGenerationRequest
from echomind.profiling.schemas import (
    PersonalityFrameworkAssessment,
    PersonalitySynthesis,
)
from echomind.providers import LLMContent, LLMProvider, LLMRequest, create_provider
from echomind.repositories.profile_repository import ProfileInsightSource
from echomind.services.analysis_service import configured_model_name

ProfileProviderFactory = Callable[[Settings], LLMProvider]
ProviderName = Literal["mock", "openai_compatible", "local"]
SYNTHESIS_VERSION: Literal["personality-synthesis-1.0"] = "personality-synthesis-1.0"
_MAX_CONTEXT_CHARACTERS = 80_000
_MAX_CONTENT_CHARACTERS = 18_000


class PersonalitySynthesisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    headline: str = Field(min_length=1, max_length=120)
    overall_summary: str = Field(min_length=1, max_length=4_000)
    core_traits: list[str] = Field(min_length=3, max_length=8)
    thinking_style: str = Field(min_length=1, max_length=2_000)
    decision_style: str = Field(min_length=1, max_length=2_000)
    motivation_and_values: str = Field(min_length=1, max_length=2_000)
    social_and_relationship_style: str = Field(min_length=1, max_length=2_000)
    emotional_and_stress_patterns: str = Field(min_length=1, max_length=2_000)
    strengths: list[str] = Field(min_length=2, max_length=8)
    growth_edges: list[str] = Field(min_length=2, max_length=8)
    tensions_and_changes: list[str] = Field(max_length=8)
    framework_assessments: list[PersonalityFrameworkAssessment] = Field(
        min_length=2,
        max_length=2,
    )
    uncertainty_note: str = Field(min_length=1, max_length=1_500)

    @model_validator(mode="after")
    def validate_frameworks(self) -> PersonalitySynthesisOutput:
        if [item.framework for item in self.framework_assessments] != ["big_five", "mbti"]:
            raise ValueError("framework assessments must contain Big Five followed by MBTI")
        return self


def _insufficient_mock_payload() -> dict[str, object]:
    insufficient = "当前使用离线 Mock Provider，未执行真实人格推断。"
    return {
        "headline": "等待真实分析的人格档案",
        "overall_summary": (
            "当前档案已经完成结构和安全边界验证，但离线 Mock Provider 不会根据真实内容"
            "生成人格判断。配置并显式授权远程 Provider 后，才能获得综合人物分析。"
        ),
        "core_traits": ["信息不足", "暂不分型", "等待用户授权分析"],
        "thinking_style": insufficient,
        "decision_style": insufficient,
        "motivation_and_values": insufficient,
        "social_and_relationship_style": insufficient,
        "emotional_and_stress_patterns": insufficient,
        "strengths": ["不在信息不足时强行定型", "保留用户最终解释权"],
        "growth_edges": ["补充更多跨场景信息", "使用正式问卷交叉验证"],
        "tensions_and_changes": [],
        "framework_assessments": [
            {
                "framework": "big_five",
                "display_name": "Big Five",
                "result": "暂时无法判断",
                "confidence": "insufficient",
                "summary": insufficient,
                "dimensions": [
                    {
                        "dimension_key": key,
                        "label": label,
                        "tendency": "insufficient",
                        "summary": "信息不足，暂不判断。",
                    }
                    for key, label in (
                        ("openness", "开放性"),
                        ("conscientiousness", "尽责性"),
                        ("extraversion", "外向性"),
                        ("agreeableness", "宜人性"),
                        ("emotional_stability", "情绪稳定性"),
                    )
                ],
                "caveats": ["聊天推断不能替代标准化 Big Five 问卷。"],
            },
            {
                "framework": "mbti",
                "display_name": "MBTI",
                "result": "暂时无法判断",
                "confidence": "insufficient",
                "summary": insufficient,
                "dimensions": [
                    {
                        "dimension_key": key,
                        "label": label,
                        "tendency": "insufficient",
                        "summary": "信息不足，暂不判断。",
                    }
                    for key, label in (
                        ("energy", "精力方向 E / I"),
                        ("information", "信息方式 S / N"),
                        ("decisions", "决策方式 T / F"),
                        ("lifestyle", "生活方式 J / P"),
                    )
                ],
                "caveats": ["MBTI 只提供参考语言，不能定义固定人格。"],
            },
        ],
        "uncertainty_note": "当前结果不包含真实人格推断，也不构成任何诊断。",
    }


def default_profile_provider_factory(settings: Settings) -> LLMProvider:
    return create_provider(
        settings,
        provider_name=cast(ProviderName, settings.llm_provider),
        mock_response_payload=_insufficient_mock_payload(),
    )


def _context_payload(source: ProfileInsightSource) -> dict[str, object]:
    return {
        "insight_type": source.insight_type.value,
        "category": source.category,
        "title": source.title,
        "statement": source.statement,
        "confidence": source.confidence,
        "evidence_state": source.evidence_state.value,
        "explicit_self_report": source.explicit_self_report,
        "valid_from": source.valid_from.isoformat() if source.valid_from else None,
        "valid_to": source.valid_to.isoformat() if source.valid_to else None,
        "reasoning_basis": source.reasoning_basis,
        "alternative_explanations": list(source.alternative_explanations),
    }


def _context_messages(
    sources: list[ProfileInsightSource],
) -> tuple[list[LLMContent], int, int]:
    serialized: list[str] = []
    used = 0
    total = 0
    for source in sources:
        value = json.dumps(
            _context_payload(source),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        cost = len(value) + 1
        if total + cost > _MAX_CONTEXT_CHARACTERS:
            break
        serialized.append(value)
        total += cost
        used += 1
    chunks: list[LLMContent] = []
    current: list[str] = []
    current_length = 0
    for value in serialized:
        if current and current_length + len(value) + 1 > _MAX_CONTENT_CHARACTERS:
            chunks.append(LLMContent(content="\n".join(current)))
            current = []
            current_length = 0
        current.append(value)
        current_length += len(value) + 1
    if current:
        chunks.append(LLMContent(content="\n".join(current)))
    return chunks, used, len(sources) - used


_SYSTEM_INSTRUCTION = """
你是 EchoMind 的综合人格分析器。输入仅包含用户已经确认的结构化 Insight，不包含原始聊天。
请把多条信息综合为一份连贯、克制、简体中文的人物性格分析，不要逐条复述输入。

硬性要求：
1. 不使用医疗、心理诊断或病理化语言。
2. 区分稳定特征、场景性表现、变化和矛盾；信息不足时明确写“暂时无法判断”。
3. 不生成 Evidence、Insight 编号、原消息引用或来源列表。
4. 必须按顺序提供 Big Five 和 MBTI 两种参考框架。
5. Big Five 必须包含开放性、尽责性、外向性、宜人性、情绪稳定性五维。
6. MBTI 必须包含 E/I、S/N、T/F、J/P 四维，可给出类型区间，但不得声称正式测评。
7. 两种框架都只是辅助解释，不能代替完整人物分析或决定职业、关系和人生选择。
8. confidence 表示当前输入对该参考映射的充分程度，只允许 low、medium、high、insufficient。
9. 不把模型推断写成确定事实；保留其他可能解释和用户最终解释权。
10. 输出必须严格符合提供的 JSON Schema。
""".strip()


def synthesize_personality(
    sources: list[ProfileInsightSource],
    request: ProfileGenerationRequest,
    *,
    settings: Settings,
    provider: LLMProvider,
) -> PersonalitySynthesis:
    content, used, omitted = _context_messages(sources)
    if not content:
        raise ValueError("personality synthesis requires at least one bounded Insight")
    model_name = configured_model_name(settings)
    result = provider.generate_structured(
        LLMRequest(
            request_id=request.request_id,
            system_instruction=_SYSTEM_INSTRUCTION,
            user_content=content,
            response_schema_name="PersonalitySynthesisOutput",
            provider_name=provider.provider_name,
            model_name=model_name,
            temperature=0.0,
            max_output_tokens=min(4_096, settings.llm_max_output_tokens),
            timeout_seconds=settings.llm_request_timeout_seconds,
            metadata_json={
                "feature": "profile_synthesis",
                "version": SYNTHESIS_VERSION,
                "insight_count": used,
                "omitted_count": omitted,
            },
            remote_consent=request.remote_consent,
        ),
        PersonalitySynthesisOutput,
    )
    return PersonalitySynthesis(
        synthesis_version=SYNTHESIS_VERSION,
        **result.output.model_dump(),
        provider_name=result.provider_name,
        model_name=result.model_name,
        input_insight_count=used,
        omitted_insight_count=omitted,
    )
