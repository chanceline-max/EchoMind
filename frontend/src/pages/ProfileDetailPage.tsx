import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { downloadProfile, fetchMarkdownPreview, fetchProfile } from "../api/profiles";
import {
  categoryLabel,
  evidenceModeLabel,
  evidenceRoleLabel,
  evidenceStateLabel,
  insightTypeLabel,
  invalidationReasonLabel,
  profileSourceStatusLabel,
  selectionPolicyLabel,
  senderRoleLabel,
  staleReasonLabel,
} from "../labels";
import type {
  PersonalityFrameworkAssessment,
  PersonalitySynthesis,
  PersonalityTendency,
  ProfileEvidenceItem,
  ProfileInsightItem,
} from "../types/profiles";

const percent = (value: number) => `${Math.round(value * 100)}%`;
const timeRange = (item: ProfileInsightItem) => `${item.valid_from ? new Date(item.valid_from).toLocaleDateString() : "未指定"} — ${item.valid_to ? new Date(item.valid_to).toLocaleDateString() : "至今"}`;

function InsightEntry({ item }: { item: ProfileInsightItem }) {
  return <article className={`profile-insight profile-insight--${item.evidence_state}`}>
    <header><span className="profile-ref">{item.profile_insight_ref}</span><div><h3>{item.title}</h3><p>{insightTypeLabel(item.insight_type)} · {categoryLabel(item.category)} · 第 {item.insight_revision_number} 版</p></div><strong>{percent(item.confidence)}</strong></header>
    {item.warnings.map((warning) => <p key={warning} className="profile-warning">{warning}</p>)}
    <p className="profile-statement">{item.statement}</p>
    <dl className="profile-facts"><div><dt>证据状态</dt><dd>{evidenceStateLabel(item.evidence_state)}</dd></div><div><dt>有效时间</dt><dd>{timeRange(item)}</dd></div><div><dt>证据引用</dt><dd>{item.evidence_refs.join(" · ") || "无"}</dd></div></dl>
    <p className="confidence-explanation">{item.confidence_explanation}</p>
    {item.reasoning_basis && <div className="profile-reasoning"><strong>推理依据</strong><p>{item.reasoning_basis}</p>{item.alternative_explanations.length > 0 && <><strong>其他可能解释</strong><ul>{item.alternative_explanations.map((value) => <li key={value}>{value}</li>)}</ul></>}</div>}
  </article>;
}

function EvidenceEntry({ item }: { item: ProfileEvidenceItem }) {
  return <article className={`profile-evidence${item.is_valid ? "" : " is-invalid"}`}><header><span className="profile-ref">{item.profile_evidence_ref}</span><strong>{senderRoleLabel(item.sender_role)}</strong><span>{evidenceRoleLabel(item.role)}</span><span>{item.is_valid ? "有效" : "已失效"}</span></header><p>{item.message_timestamp ? new Date(item.message_timestamp).toLocaleString() : "时间未知"}</p>{item.excerpt !== null && <blockquote>{item.excerpt}</blockquote>}{item.invalidation_reasons.length > 0 && <p className="profile-warning">{item.invalidation_reasons.map(invalidationReasonLabel).join("、")}</p>}<Link to={`/conversations/${item.conversation_id}?message=${item.message_id}`}>查看本地原消息 →</Link></article>;
}

const tendencyLabel: Record<PersonalityTendency, string> = {
  low: "较低",
  moderately_low: "中等偏低",
  balanced: "相对均衡",
  moderately_high: "中等偏高",
  high: "较高",
  insufficient: "信息不足",
};
const assessmentConfidenceLabel = {
  low: "低参考强度",
  medium: "中等参考强度",
  high: "较高参考强度",
  insufficient: "信息不足",
} as const;

function NarrativeSection({ number, title, children }: { number: string; title: string; children: ReactNode }) {
  return <section className="portrait-section"><span className="portrait-number">{number}</span><div><h2>{title}</h2>{children}</div></section>;
}

function FrameworkCard({ assessment }: { assessment: PersonalityFrameworkAssessment }) {
  return <article className={`framework-card framework-card--${assessment.framework}`}>
    <header><div><p>{assessment.display_name}</p><h3>{assessment.result}</h3></div><span>{assessmentConfidenceLabel[assessment.confidence]}</span></header>
    <p className="framework-summary">{assessment.summary}</p>
    <div className="dimension-ledger">{assessment.dimensions.map((dimension) => <div key={dimension.dimension_key}><div><strong>{dimension.label}</strong><span>{tendencyLabel[dimension.tendency]}</span></div><p>{dimension.summary}</p></div>)}</div>
    <ul className="framework-caveats">{assessment.caveats.map((value) => <li key={value}>{value}</li>)}</ul>
  </article>;
}

function PersonalityPortrait({ synthesis }: { synthesis: PersonalitySynthesis }) {
  return <div className="personality-portrait">
    <section className="portrait-thesis"><p className="eyebrow">综合人格类型</p><h2>{synthesis.headline}</h2><p>{synthesis.overall_summary}</p><div className="trait-ribbon">{synthesis.core_traits.map((trait) => <span key={trait}>{trait}</span>)}</div></section>
    <div className="portrait-reading">
      <NarrativeSection number="01" title="思考与信息处理方式"><p>{synthesis.thinking_style}</p></NarrativeSection>
      <NarrativeSection number="02" title="决策与行动模式"><p>{synthesis.decision_style}</p></NarrativeSection>
      <NarrativeSection number="03" title="价值观与内在驱动力"><p>{synthesis.motivation_and_values}</p></NarrativeSection>
      <NarrativeSection number="04" title="社交与关系模式"><p>{synthesis.social_and_relationship_style}</p></NarrativeSection>
      <NarrativeSection number="05" title="情绪与压力模式"><p>{synthesis.emotional_and_stress_patterns}</p></NarrativeSection>
    </div>
    <section className="strength-growth"><div><p className="eyebrow">可能的优势</p><ul>{synthesis.strengths.map((value) => <li key={value}>{value}</li>)}</ul></div><div><p className="eyebrow">成长方向</p><ul>{synthesis.growth_edges.map((value) => <li key={value}>{value}</li>)}</ul></div></section>
    <NarrativeSection number="06" title="内在矛盾与变化">{synthesis.tensions_and_changes.length > 0 ? <ul>{synthesis.tensions_and_changes.map((value) => <li key={value}>{value}</li>)}</ul> : <p>暂未识别到足够稳定的矛盾或变化。</p>}</NarrativeSection>
    <section className="framework-spread"><header><p className="eyebrow">双框架校准</p><h2>人格框架参考</h2><p>Big Five 与 MBTI 从不同角度提供描述语言，它们不是正式测评，也不替代上面的完整分析。</p></header><div>{synthesis.framework_assessments.map((assessment) => <FrameworkCard key={assessment.framework} assessment={assessment} />)}</div></section>
    <section className="portrait-boundary"><span>边界</span><div><h2>不确定性与适用范围</h2><p>{synthesis.uncertainty_note}</p><small>综合输入 {synthesis.input_insight_count} 条已确认洞察{synthesis.omitted_insight_count > 0 ? `，另有 ${synthesis.omitted_insight_count} 条因上下文预算未纳入` : ""}。模型：{synthesis.model_name}</small></div></section>
  </div>;
}

export function ProfileDetailPage() {
  const { profileId = "" } = useParams();
  const [markdown, setMarkdown] = useState<string | null>(null);
  const query = useQuery({ queryKey: ["profile", profileId], queryFn: () => fetchProfile(profileId), staleTime: 0, gcTime: 30_000 });
  const preview = useMutation({ mutationFn: () => fetchMarkdownPreview(profileId), onSuccess: setMarkdown });
  const download = useMutation({ mutationFn: (format: "markdown" | "json") => downloadProfile(profileId, format) });
  if (query.isPending) return <main className="content-page"><p>正在读取认知档案…</p></main>;
  if (query.isError || !query.data) return <main className="content-page"><p className="error-box" role="alert">无法读取认知档案，或服务器返回格式无效。</p></main>;
  const profile = query.data;
  const synthesis = profile.document.personality_synthesis;
  const doDownload = (format: "markdown" | "json") => {
    if (profile.evidence_mode === "excerpts" && !window.confirm("此导出包含聊天证据摘录。是否继续下载？")) return;
    download.mutate(format);
  };
  return <main className="content-page profile-detail-page">
    <Link className="back-link" to="/profiles">← 返回认知档案</Link>
    <header className="profile-detail-heading"><div><p className="eyebrow">不可变 EchoProfile</p><h1>档案快照</h1><p>{new Date(profile.generated_at).toLocaleString()} · {profile.profile_version}</p></div><div className={`profile-status-plaque source-state--${profile.current_source_status}`}><span>当前来源状态</span><strong>{profileSourceStatusLabel(profile.current_source_status)}</strong></div></header>
    {profile.current_source_status !== "current" && <div className="stale-banner" role="alert"><strong>此快照保留生成时内容，来源后来发生了变化。</strong><span>{profile.stale_reason_codes.map(staleReasonLabel).join(" · ")}</span></div>}
    <section className="profile-meta-strip"><div><span>结构版本</span><strong>{profile.schema_version}</strong></div><div><span>策略</span><strong>{selectionPolicyLabel(profile.document.metadata.selection_policy)}</strong></div><div><span>分析形式</span><strong>{synthesis ? "综合人格分析" : evidenceModeLabel(profile.evidence_mode)}</strong></div><div><span>已确认洞察</span><strong>{profile.insight_count}</strong></div></section>
    <section className="export-desk"><div><p className="eyebrow">显式导出</p><h2>导出快照</h2><p>文件包含敏感派生档案。只有点击后才会请求，不会预取或持久缓存。</p></div><div><button onClick={() => doDownload("markdown")}>导出 Markdown</button><button onClick={() => doDownload("json")}>导出 JSON</button></div>{download.isError && <p className="error-box" role="alert">导出失败，请稍后重试。</p>}</section>
    {synthesis ? <PersonalityPortrait synthesis={synthesis} /> : <>
      <div className="profile-document">{profile.document.sections.filter((section) => section.items.length > 0).map((section, index) => <section key={section.section_key} className="profile-section"><header><span>{String(index + 1).padStart(2, "0")}</span><div><h2>{section.title}</h2><p>{section.description}</p></div></header><div className="profile-insight-list">{section.items.map((item) => <InsightEntry key={item.insight_id} item={item} />)}</div></section>)}</div>
      <section className="profile-section evidence-index"><header><span>EI</span><div><h2>证据索引</h2><p>I 编号都回到唯一、去重的 E 编号。</p></div></header><div className="profile-evidence-grid">{profile.document.evidence_index.map((item) => <EvidenceEntry key={item.evidence_id} item={item} />)}</div></section>
    </>}
    <section className="profile-section limitations"><header><span>!</span><div><h2>局限性说明</h2><p>这是一份有边界的历史快照，不是永久真相。</p></div></header><ul>{profile.document.metadata.limitations.map((item) => <li key={item}>{item}</li>)}</ul></section>
    <section className="markdown-preview"><button aria-expanded={markdown !== null} onClick={() => markdown === null ? preview.mutate() : setMarkdown(null)}>{markdown === null ? "查看 Markdown 纯文本" : "收起 Markdown"}</button>{preview.isError && <p className="error-box">无法加载 Markdown 预览。</p>}{markdown !== null && <pre>{markdown}</pre>}</section>
  </main>;
}
