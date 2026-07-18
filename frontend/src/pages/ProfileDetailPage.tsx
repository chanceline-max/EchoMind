import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { downloadProfile, fetchMarkdownPreview, fetchProfile } from "../api/profiles";
import type { ProfileEvidenceItem, ProfileInsightItem } from "../types/profiles";

const statusText = { current: "当前", stale: "来源已变化", source_unavailable: "来源不可用" } as const;
const percent = (value: number) => `${Math.round(value * 100)}%`;
const timeRange = (item: ProfileInsightItem) => `${item.valid_from ? new Date(item.valid_from).toLocaleDateString() : "未指定"} — ${item.valid_to ? new Date(item.valid_to).toLocaleDateString() : "至今"}`;

function InsightEntry({ item }: { item: ProfileInsightItem }) {
  return <article className={`profile-insight profile-insight--${item.evidence_state}`}>
    <header><span className="profile-ref">{item.profile_insight_ref}</span><div><h3>{item.title}</h3><p>{item.insight_type} · {item.category} · r{item.insight_revision_number}</p></div><strong>{percent(item.confidence)}</strong></header>
    {item.warnings.map((warning) => <p key={warning} className="profile-warning">{warning}</p>)}
    <p className="profile-statement">{item.statement}</p>
    <dl className="profile-facts"><div><dt>证据状态</dt><dd>{item.evidence_state}</dd></div><div><dt>有效时间</dt><dd>{timeRange(item)}</dd></div><div><dt>Evidence</dt><dd>{item.evidence_refs.join(" · ") || "无"}</dd></div></dl>
    <p className="confidence-explanation">{item.confidence_explanation}</p>
    {item.reasoning_basis && <div className="profile-reasoning"><strong>推理依据</strong><p>{item.reasoning_basis}</p>{item.alternative_explanations.length > 0 && <><strong>其他可能解释</strong><ul>{item.alternative_explanations.map((value) => <li key={value}>{value}</li>)}</ul></>}</div>}
  </article>;
}

function EvidenceEntry({ item }: { item: ProfileEvidenceItem }) {
  return <article className={`profile-evidence${item.is_valid ? "" : " is-invalid"}`}><header><span className="profile-ref">{item.profile_evidence_ref}</span><strong>{item.sender_role === "PROFILE_OWNER" ? "Profile Owner" : "Other"}</strong><span>{item.role}</span><span>{item.is_valid ? "valid" : "invalid"}</span></header><p>{item.message_timestamp ? new Date(item.message_timestamp).toLocaleString() : "时间未知"}</p>{item.excerpt !== null && <blockquote>{item.excerpt}</blockquote>}{item.invalidation_reasons.length > 0 && <p className="profile-warning">{item.invalidation_reasons.join("、")}</p>}<Link to={`/conversations/${item.conversation_id}?message=${item.message_id}`}>查看本地原消息 →</Link></article>;
}

export function ProfileDetailPage() {
  const { profileId = "" } = useParams();
  const [markdown, setMarkdown] = useState<string | null>(null);
  const query = useQuery({ queryKey: ["profile", profileId], queryFn: () => fetchProfile(profileId), staleTime: 0, gcTime: 30_000 });
  const preview = useMutation({ mutationFn: () => fetchMarkdownPreview(profileId), onSuccess: setMarkdown });
  const download = useMutation({ mutationFn: (format: "markdown" | "json") => downloadProfile(profileId, format) });
  if (query.isPending) return <main className="content-page"><p>正在读取 Profile…</p></main>;
  if (query.isError || !query.data) return <main className="content-page"><p className="error-box" role="alert">无法读取 Profile，或服务器返回格式无效。</p></main>;
  const profile = query.data;
  const doDownload = (format: "markdown" | "json") => {
    if (profile.evidence_mode === "excerpts" && !window.confirm("此导出包含聊天 Evidence 摘录。是否继续下载？")) return;
    download.mutate(format);
  };
  return <main className="content-page profile-detail-page">
    <Link className="back-link" to="/profiles">← 返回 Profiles</Link>
    <header className="profile-detail-heading"><div><p className="eyebrow">Immutable EchoProfile</p><h1>档案快照</h1><p>{new Date(profile.generated_at).toLocaleString()} · {profile.profile_version}</p></div><div className={`profile-status-plaque source-state--${profile.current_source_status}`}><span>当前来源状态</span><strong>{statusText[profile.current_source_status]}</strong></div></header>
    {profile.current_source_status !== "current" && <div className="stale-banner" role="alert"><strong>此快照保留生成时内容，来源后来发生了变化。</strong><span>{profile.stale_reason_codes.join(" · ")}</span></div>}
    <section className="profile-meta-strip"><div><span>Schema</span><strong>{profile.schema_version}</strong></div><div><span>策略</span><strong>{profile.document.metadata.selection_policy}</strong></div><div><span>Evidence 模式</span><strong>{profile.evidence_mode}</strong></div><div><span>Insight / Evidence</span><strong>{profile.insight_count} / {profile.evidence_count}</strong></div></section>
    <section className="export-desk"><div><p className="eyebrow">Explicit export</p><h2>导出快照</h2><p>文件包含敏感派生档案。只有点击后才会请求，不会预取或持久缓存。</p></div><div><button onClick={() => doDownload("markdown")}>导出 Markdown</button><button onClick={() => doDownload("json")}>导出 JSON</button></div>{download.isError && <p className="error-box" role="alert">导出失败，请稍后重试。</p>}</section>
    <div className="profile-document">{profile.document.sections.filter((section) => section.items.length > 0).map((section, index) => <section key={section.section_key} className="profile-section"><header><span>{String(index + 1).padStart(2, "0")}</span><div><h2>{section.title}</h2><p>{section.description}</p></div></header><div className="profile-insight-list">{section.items.map((item) => <InsightEntry key={item.insight_id} item={item} />)}</div></section>)}</div>
    <section className="profile-section evidence-index"><header><span>EI</span><div><h2>证据索引</h2><p>I 编号都回到唯一、去重的 E 编号。</p></div></header><div className="profile-evidence-grid">{profile.document.evidence_index.map((item) => <EvidenceEntry key={item.evidence_id} item={item} />)}</div></section>
    <section className="profile-section limitations"><header><span>!</span><div><h2>局限性说明</h2><p>这是一份有边界的历史快照，不是永久真相。</p></div></header><ul>{profile.document.metadata.limitations.map((item) => <li key={item}>{item}</li>)}</ul></section>
    <section className="markdown-preview"><button aria-expanded={markdown !== null} onClick={() => markdown === null ? preview.mutate() : setMarkdown(null)}>{markdown === null ? "查看 Markdown 纯文本" : "收起 Markdown"}</button>{preview.isError && <p className="error-box">无法加载 Markdown 预览。</p>}{markdown !== null && <pre>{markdown}</pre>}</section>
  </main>;
}
