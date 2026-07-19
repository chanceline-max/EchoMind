import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  confirmInsight,
  editInsight,
  fetchInsight,
  fetchInsightRevisions,
  rejectInsight,
  restoreInsight,
  supersedeInsight,
} from "../api/insights";
import {
  categoryLabel,
  changedFieldLabel,
  evidenceRoleLabel,
  evidenceStateLabel,
  insightStatusLabel,
  insightTypeLabel,
  insightTypeOptions,
  invalidationReasonLabel,
  revisionActionLabel,
  senderRoleLabel,
} from "../labels";
import { APIError } from "../types/api";

type ReviewCommand =
  | { kind: "confirm"; body: Record<string, unknown> }
  | { kind: "reject"; body: Record<string, unknown> }
  | { kind: "restore"; body: Record<string, unknown> }
  | { kind: "supersede"; body: Record<string, unknown> }
  | { kind: "edit"; body: Record<string, unknown> };

const percent = (value: number | null) => value === null ? "未提供" : `${Math.round(value * 100)}%`;

export function InsightDetailPage() {
  const id = useParams().insightId ?? "";
  const queryClient = useQueryClient();
  const [showEditor, setShowEditor] = useState(false);
  const [showSupersede, setShowSupersede] = useState(false);
  const detail = useQuery({ queryKey: ["insight", id], queryFn: () => fetchInsight(id), enabled: Boolean(id) });
  const revisions = useQuery({ queryKey: ["insight-revisions", id], queryFn: () => fetchInsightRevisions(id), enabled: Boolean(id) });
  const mutation = useMutation({
    mutationFn: ({ kind, body }: ReviewCommand) => {
      if (kind === "edit") return editInsight(id, body);
      if (kind === "confirm") return confirmInsight(id, body);
      if (kind === "reject") return rejectInsight(id, body);
      if (kind === "restore") return restoreInsight(id, body);
      return supersedeInsight(id, body);
    },
    onSuccess: async () => {
      setShowEditor(false);
      setShowSupersede(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["insight", id] }),
        queryClient.invalidateQueries({ queryKey: ["insight-revisions", id] }),
        queryClient.invalidateQueries({ queryKey: ["insights"] }),
      ]);
    },
  });
  const insight = detail.data;
  const expected = insight?.revision_number ?? 0;
  const conflict =
    mutation.error instanceof APIError &&
    mutation.error.body.error_code === "insight_revision_conflict";

  const submitEdit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!insight) return;
    const data = new FormData(event.currentTarget);
    const textValue = (name: string) => {
      const value = data.get(name);
      return typeof value === "string" ? value : "";
    };
    const body: Record<string, unknown> = { expected_revision: expected };
    const title = textValue("title");
    const statement = textValue("statement");
    const category = textValue("category");
    const insightType = textValue("insight_type");
    const reviewNote = textValue("review_note") || null;
    if (title !== insight.title) body.title = title;
    if (statement !== insight.statement) body.statement = statement;
    if (category !== insight.category) body.category = category;
    if (insightType !== insight.insight_type) body.insight_type = insightType;
    if (reviewNote !== insight.review_note) body.review_note = reviewNote;
    mutation.mutate({
      kind: "edit",
      body,
    });
  };

  if (detail.isPending) return <main className="content-page"><p>正在读取洞察…</p></main>;
  if (detail.isError || !insight) return <main className="content-page"><p className="error-box">无法读取洞察。</p></main>;

  return (
    <main className="content-page review-page">
      <Link className="back-link" to="/insights">← 返回洞察列表</Link>
      <div className="insight-detail-heading">
        <div><p className="eyebrow">{categoryLabel(insight.category)} · {insightTypeLabel(insight.insight_type)}</p><h1>{insight.title}</h1></div>
        <div className={`evidence-seal seal-${insight.evidence_state}`}><small>最终置信度</small><strong>{percent(insight.confidence)}</strong><span>{evidenceStateLabel(insight.evidence_state)}</span></div>
      </div>

      {conflict && <div className="conflict-box" role="alert"><strong>此洞察已在其他页面被修改。</strong><span>当前内容没有被覆盖，请重新加载后再提交。</span><button onClick={() => { mutation.reset(); void detail.refetch(); void revisions.refetch(); }}>重新加载</button></div>}
      {mutation.isError && !conflict && <p className="error-box" role="alert">审核操作失败：{mutation.error.message}</p>}

      <section className="claim-sheet">
        <div className="claim-meta"><span className={`status-chip status-${insight.status}`}>{insightStatusLabel(insight.status)}</span><span>修订版本 {insight.revision_number}</span><span>模型自评 {percent(insight.model_confidence)}</span><span>规则版本 {insight.confidence_version}</span></div>
        <p className="claim-statement">{insight.statement}</p>
        {insight.confidence_explanation && <div className="reasoning-note"><strong>为什么是这个置信度</strong><p>{insight.confidence_explanation}</p></div>}
        {insight.reasoning_basis && <div className="reasoning-note"><strong>推理依据</strong><p>{insight.reasoning_basis}</p></div>}
        {insight.alternative_explanations.length > 0 && <div className="reasoning-note"><strong>其他可能解释</strong><ul>{insight.alternative_explanations.map((item) => <li key={item}>{item}</li>)}</ul></div>}
      </section>

      <section className="review-actions" aria-label="审核操作">
        <button onClick={() => setShowEditor(!showEditor)}>编辑候选</button>
        {insight.allowed_actions.includes("confirm") && <button className="primary-button" disabled={mutation.isPending} onClick={() => mutation.mutate({ kind: "confirm", body: { expected_revision: expected } })}>确认洞察</button>}
        {insight.allowed_actions.includes("reject") && <button className="danger-button" disabled={mutation.isPending} onClick={() => { const note = window.prompt("请填写驳回原因（不会删除证据或历史）"); if (note) mutation.mutate({ kind: "reject", body: { expected_revision: expected, note } }); }}>驳回</button>}
        {insight.allowed_actions.includes("restore_to_proposed") && <button onClick={() => mutation.mutate({ kind: "restore", body: { expected_revision: expected, target_status: "proposed" } })}>恢复为待审核</button>}
        {insight.allowed_actions.includes("restore_to_confirmed") && <button onClick={() => mutation.mutate({ kind: "restore", body: { expected_revision: expected, target_status: "confirmed" } })}>恢复并确认</button>}
        {insight.allowed_actions.includes("supersede") && <button onClick={() => setShowSupersede(!showSupersede)}>用其他洞察替代</button>}
      </section>

      {showEditor && <form className="panel review-form" onSubmit={submitEdit}>
        <h2>编辑审核字段</h2>
        <label>标题<input name="title" defaultValue={insight.title} required /></label>
        <label>陈述<textarea name="statement" defaultValue={insight.statement} required rows={5} /></label>
        <div className="split-fields"><label>分类<input name="category" defaultValue={insight.category} required /></label><label>类型<select name="insight_type" defaultValue={insight.insight_type}>{insightTypeOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label></div>
        <label>审核说明<textarea name="review_note" defaultValue={insight.review_note ?? ""} rows={3} /></label>
        <p className="hint">标题、陈述和分类不会直接改变置信度；类型或有效期会触发规则重算。</p>
        <button className="primary-button" disabled={mutation.isPending}>保存修订 {expected + 1}</button>
      </form>}

      {showSupersede && <form className="panel review-form" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); mutation.mutate({ kind: "supersede", body: { expected_revision: expected, replacement_insight_id: data.get("replacement"), note: data.get("note") || null } }); }}>
        <h2>替代当前洞察</h2><p>当前记录和证据都会保留，只把状态标记为已替代。</p>
        <label>替代洞察 ID<input name="replacement" required /></label><label>说明<textarea name="note" rows={2} /></label><button>确认替代</button>
      </form>}

      <section className="review-section"><div className="section-heading"><p className="eyebrow">可追溯证据</p><h2>证据链</h2><span>{insight.valid_evidence_count}/{insight.evidence_count} 有效</span></div>
        <div className="evidence-list">{insight.evidence.map((evidence) => <article key={evidence.evidence_id} className={`evidence-card${evidence.is_valid ? "" : " is-invalid"}`}><header><strong>{senderRoleLabel(evidence.sender_role)}</strong><span>{evidenceRoleLabel(evidence.stance)}</span><span>{evidence.is_valid ? "有效" : "已失效"}</span></header><blockquote>{evidence.excerpt}</blockquote>{evidence.invalidation_reasons.length > 0 && <p className="invalidation-line">失效原因：{evidence.invalidation_reasons.map(invalidationReasonLabel).join("、")}</p>}<Link to={evidence.message_link}>查看原消息 →</Link></article>)}</div>
      </section>

      <section className="review-section"><div className="section-heading"><p className="eyebrow">仅追加记录</p><h2>修订历史</h2><span>{revisions.data?.total ?? 0} 条</span></div>
        {revisions.isPending && <p>正在读取修订…</p>}{revisions.isError && <p className="error-box">无法读取修订历史。</p>}
        <ol className="revision-list">{revisions.data?.items.map((revision) => <li key={revision.id}><div><strong>第 {revision.revision_number} 版 · {revisionActionLabel(revision.action)}</strong><span>{revision.actor_type === "system" ? "系统传播" : "本地用户"}</span></div><time>{new Date(revision.created_at).toLocaleString()}</time>{revision.note && <p>{revision.note}</p>}<small>变更：{Object.keys(revision.changed_fields_json).map(changedFieldLabel).join("、") || "状态已复核"}</small></li>)}</ol>
      </section>
    </main>
  );
}
