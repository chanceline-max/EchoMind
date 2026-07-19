import type { EvidenceState, InsightStatus, InsightType } from "./types/insights";
import type { EvidenceMode, ProfileSourceStatus } from "./types/profiles";

type LabelOption<T extends string> = Readonly<{ value: T; label: string }>;

export const insightStatusOptions: readonly LabelOption<InsightStatus>[] = [
  { value: "proposed", label: "待审核" },
  { value: "confirmed", label: "已确认" },
  { value: "rejected", label: "已驳回" },
  { value: "superseded", label: "已替代" },
];

export const insightTypeOptions: readonly LabelOption<InsightType>[] = [
  { value: "fact", label: "事实" },
  { value: "preference", label: "偏好" },
  { value: "pattern", label: "模式" },
  { value: "inference", label: "推断" },
  { value: "hypothesis", label: "假设" },
  { value: "contradiction", label: "矛盾" },
  { value: "change", label: "变化" },
];

export const evidenceStateOptions: readonly LabelOption<EvidenceState>[] = [
  { value: "valid", label: "有效" },
  { value: "partial", label: "部分有效" },
  { value: "invalid", label: "已失效" },
];

function labelFrom(value: string, labels: Readonly<Record<string, string>>): string {
  return labels[value] ?? value;
}

export const insightStatusLabel = (value: InsightStatus): string =>
  insightStatusOptions.find((item) => item.value === value)?.label ?? value;

export const insightTypeLabel = (value: InsightType): string =>
  insightTypeOptions.find((item) => item.value === value)?.label ?? value;

export const evidenceStateLabel = (value: EvidenceState): string =>
  evidenceStateOptions.find((item) => item.value === value)?.label ?? value;

export const categoryLabel = (value: string): string => {
  const labels: Readonly<Record<string, string>> = {
    background: "背景信息",
    preference: "偏好",
    pattern: "行为模式",
    thinking_pattern: "思维模式",
    behavior_execution: "行为与执行",
    emotional_response: "情绪反应",
    relationship_pattern: "关系模式",
    values_motivation: "价值观与动机",
    internal_conflict: "内在冲突",
    values: "价值观",
    goals: "目标",
    relationships: "关系",
    communication: "沟通方式",
    learning: "学习",
    work: "工作",
    wellbeing: "生活状态",
    contradiction: "矛盾",
    temporal_change: "时间变化",
    change: "变化",
    other: "其他",
  };
  return labels[value.toLowerCase()] ?? value;
};

export const senderRoleLabel = (value: "PROFILE_OWNER" | "OTHER"): string =>
  value === "PROFILE_OWNER" ? "本人" : "其他参与者";

export const evidenceRoleLabel = (value: string): string =>
  labelFrom(value, {
    supporting: "支持证据",
    supports: "支持",
    contradicting: "反对证据",
    contradicts: "反对",
    contextual: "上下文证据",
    context: "上下文",
  });

export const invalidationReasonLabel = (value: string): string =>
  labelFrom(value, {
    source_message_excluded: "原消息已排除分析",
    source_message_archived: "原消息已归档",
    user_marked_invalid: "用户标记为无效",
    source_missing: "来源不存在",
    other_system_reason: "其他系统原因",
  });

export const revisionActionLabel = (value: string): string =>
  labelFrom(value, {
    confirmed: "已确认",
    rejected: "已驳回",
    restored_to_proposed: "已恢复为待审核",
    restored_to_confirmed: "已恢复并确认",
    edited: "已编辑",
    superseded: "已替代",
    evidence_invalidated: "证据已失效",
    evidence_revalidated: "证据已恢复有效",
  });

export const changedFieldLabel = (value: string): string =>
  labelFrom(value, {
    title: "标题",
    statement: "陈述",
    category: "分类",
    insight_type: "类型",
    valid_from: "有效期开始",
    valid_to: "有效期结束",
    review_note: "审核说明",
    status: "状态",
    evidence_state: "证据状态",
    confidence: "置信度",
  });

export const profileSourceStatusLabel = (value: ProfileSourceStatus): string =>
  labelFrom(value, {
    current: "当前有效",
    stale: "来源已变化",
    source_unavailable: "来源不可用",
  });

export const staleReasonLabel = (value: string): string =>
  labelFrom(value, {
    insight_revision_changed: "洞察修订已变化",
    confirmed_set_changed: "已确认洞察集合已变化",
    evidence_changed: "证据状态已变化",
    source_missing: "来源不存在",
  });

export const evidenceModeLabel = (value: EvidenceMode): string =>
  value === "references" ? "仅引用" : "包含证据摘录";

export const providerLabel = (value: string): string =>
  labelFrom(value, {
    mock: "离线模拟模型",
    openai_compatible: "OpenAI 兼容远程模型",
    local: "本地模型",
  });

export const selectionPolicyLabel = (value: string): string =>
  value === "confirmed-only-1.0" ? "仅纳入已确认洞察" : value;
