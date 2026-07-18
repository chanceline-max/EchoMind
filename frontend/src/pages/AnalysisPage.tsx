import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { fetchAnalysisCapabilities, startAnalysis } from "../api/analysis";
import { fetchConversations } from "../api/conversations";
import { APIError } from "../types/api";

function safeError(error: Error): string {
  if (error instanceof APIError) {
    if (error.body.error_code === "remote_consent_required") return "远程分析需要本次明确同意。";
    if (error.body.error_code === "provider_not_configured") return "当前分析 Provider 未配置。";
  }
  return error.message || "分析请求失败。";
}

export function AnalysisPage() {
  const [selected, setSelected] = useState<string[]>([]);
  const [remoteConsent, setRemoteConsent] = useState(false);
  const capabilities = useQuery({
    queryKey: ["analysis-capabilities"],
    queryFn: fetchAnalysisCapabilities,
    retry: false,
  });
  const conversations = useQuery({
    queryKey: ["analysis-conversations"],
    queryFn: () => fetchConversations("", 0),
    retry: false,
  });
  const analysis = useMutation({
    mutationFn: startAnalysis,
  });
  const toggle = (id: string) =>
    setSelected((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  const available = capabilities.data?.provider_available === true;
  const consentMissing = capabilities.data?.remote_consent_required === true && !remoteConsent;

  return (
    <main className="content-page analysis-page">
      <div className="analysis-heading">
        <div><p className="eyebrow">MVP ANALYSIS</p><h1>分析会话</h1></div>
        <p>选择明确范围后，同步抽取有证据的候选 Insight，并执行可解释的置信度评分。</p>
      </div>

      <section className="provider-card" aria-label="分析能力">
        <span>当前 Provider</span>
        {capabilities.isPending && <strong>正在读取配置…</strong>}
        {capabilities.isError && <p className="error-box" role="alert">无法读取分析能力。</p>}
        {capabilities.data && <>
          <strong>{capabilities.data.configured_provider}</strong>
          <small>{available ? "可用" : "未配置或不可用"} · {capabilities.data.extraction_version} · {capabilities.data.confidence_version}</small>
        </>}
      </section>

      {capabilities.data?.remote_provider && (
        <section className="remote-warning">
          <strong>远程分析会发送当前所选会话窗口的 normalized_content。</strong>
          <label><input type="checkbox" checked={remoteConsent} onChange={(event) => setRemoteConsent(event.target.checked)} /> 我同意本次远程发送</label>
        </section>
      )}

      <section className="conversation-picker" aria-labelledby="conversation-picker-title">
        <div className="section-heading"><div><p className="eyebrow">SCOPE</p><h2 id="conversation-picker-title">选择 Conversation</h2></div><span>已选择 {selected.length}</span></div>
        {conversations.isPending && <p>正在读取会话…</p>}
        {conversations.isError && <p className="error-box" role="alert">无法读取会话。</p>}
        {conversations.data?.total === 0 && <p className="empty-state">还没有可分析的会话，请先导入聊天记录。</p>}
        <div className="analysis-conversation-list">
          {conversations.data?.items.map((item) => (
            <label key={item.id} className="analysis-conversation-row">
              <input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} />
              <span><strong>{item.title ?? "未命名会话"}</strong><small>{item.platform} · {item.message_count} 条消息</small></span>
              <time>{item.started_at ? new Date(item.started_at).toLocaleDateString() : "时间未知"} — {item.ended_at ? new Date(item.ended_at).toLocaleDateString() : "时间未知"}</time>
            </label>
          ))}
        </div>
      </section>

      <div className="analysis-action">
        <button
          className="primary-button"
          disabled={!available || selected.length === 0 || consentMissing || analysis.isPending}
          onClick={() => analysis.mutate({ conversationIds: selected, remoteConsent })}
        >开始分析</button>
        {analysis.isPending && <p role="status">正在分析所选会话。</p>}
      </div>

      {analysis.isError && <p className="error-box" role="alert">{safeError(analysis.error)}</p>}
      {analysis.data && (
        <section className="analysis-result" aria-live="polite">
          <p className="eyebrow">RESULT</p><h2>分析完成</h2>
          <div className="analysis-metrics">
            <span><strong>{analysis.data.selected_message_count}</strong> 消息</span>
            <span><strong>{analysis.data.candidates_accepted}</strong> 候选</span>
            <span><strong>{analysis.data.insights_created}</strong> 新 Insight</span>
            <span><strong>{analysis.data.confidence_scored_count}</strong> 已评分</span>
          </div>
          {analysis.data.insight_ids.length === 0 && <p>本次没有生成候选 Insight。</p>}
          {(analysis.data.failed_window_count > 0 || analysis.data.confidence_failed_count > 0) && <p className="error-box">部分分析或评分失败；已成功创建的 Insight 已保留。</p>}
          {analysis.data.errors.length > 0 && <ul>{analysis.data.errors.map((error, index) => <li key={`${error.error_code}-${index}`}>{error.error_code}: {error.message}</li>)}</ul>}
          <Link className="primary-link" to={analysis.data.insights_link}>查看生成的 Insights</Link>
        </section>
      )}
    </main>
  );
}
