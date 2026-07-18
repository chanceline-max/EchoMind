import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { fetchInsights } from "../api/insights";
import { Pagination } from "../components/Pagination";
import type { InsightFilters, InsightSummary } from "../types/insights";

const initialFilters: InsightFilters = {
  status: "",
  insightType: "",
  category: "",
  evidenceState: "",
  minConfidence: "",
  maxConfidence: "",
  sort: "updated_at_desc",
  offset: 0,
};

const percent = (value: number) => `${Math.round(value * 100)}%`;

function InsightRow({ insight }: { insight: InsightSummary }) {
  return (
    <Link className="insight-row" to={`/insights/${insight.id}`}>
      <div className="insight-row__top">
        <div>
          <span className={`status-chip status-${insight.status}`}>{insight.status}</span>
          <span className="type-chip">{insight.insight_type}</span>
        </div>
        <strong className="confidence-number">{percent(insight.confidence)}</strong>
      </div>
      <h2>{insight.title}</h2>
      <p>{insight.statement_summary}</p>
      <dl className="row-facts">
        <div><dt>分类</dt><dd>{insight.category}</dd></div>
        <div><dt>证据</dt><dd>{insight.valid_evidence_count}/{insight.evidence_count} 有效</dd></div>
        <div><dt>证据状态</dt><dd>{insight.evidence_state}</dd></div>
        <div><dt>修订</dt><dd>r{insight.revision_number}</dd></div>
      </dl>
    </Link>
  );
}

export function InsightsPage() {
  const [filters, setFilters] = useState(initialFilters);
  const query = useQuery({
    queryKey: ["insights", filters],
    queryFn: () => fetchInsights(filters),
    staleTime: 0,
  });
  const update = (field: Exclude<keyof InsightFilters, "offset">, value: string) =>
    setFilters((current) => ({ ...current, [field]: value, offset: 0 }));

  return (
    <main className="content-page review-page">
      <div className="review-heading">
        <div><p className="eyebrow">Stage 9 · Human review</p><h1>Insight 审核台</h1></div>
        <p>AI 结论先作为候选保留。沿证据链检查、修订，再决定确认、驳回或替代。</p>
      </div>
      <section className="filter-desk" aria-label="Insight 筛选">
        <label>状态<select value={filters.status} onChange={(event) => update("status", event.target.value)}><option value="">全部</option><option value="proposed">proposed</option><option value="confirmed">confirmed</option><option value="rejected">rejected</option><option value="superseded">superseded</option></select></label>
        <label>类型<select value={filters.insightType} onChange={(event) => update("insightType", event.target.value)}><option value="">全部</option>{["fact", "preference", "pattern", "inference", "hypothesis", "contradiction", "change"].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>证据<select value={filters.evidenceState} onChange={(event) => update("evidenceState", event.target.value)}><option value="">全部</option><option value="valid">valid</option><option value="partial">partial</option><option value="invalid">invalid</option></select></label>
        <label>分类<input value={filters.category} onChange={(event) => update("category", event.target.value)} placeholder="例如 values" /></label>
        <label>最低置信度<input aria-label="最低置信度" type="number" min="0" max="1" step="0.05" value={filters.minConfidence} onChange={(event) => update("minConfidence", event.target.value)} /></label>
        <label>最高置信度<input aria-label="最高置信度" type="number" min="0" max="1" step="0.05" value={filters.maxConfidence} onChange={(event) => update("maxConfidence", event.target.value)} /></label>
        <label>排序<select value={filters.sort} onChange={(event) => update("sort", event.target.value)}><option value="updated_at_desc">最近更新</option><option value="created_at_desc">最近创建</option><option value="confidence_desc">置信度从高到低</option><option value="confidence_asc">置信度从低到高</option></select></label>
      </section>
      {query.isPending && <p className="loading-line">正在读取候选 Insight…</p>}
      {query.isError && <p className="error-box" role="alert">无法读取 Insight，或服务器返回格式无效。</p>}
      {query.data?.items.length === 0 && <div className="empty-state">没有符合当前条件的 Insight。</div>}
      {query.data && query.data.items.length > 0 && <>
        <p className="result-count">共 {query.data.total} 条，不因多条 Evidence 重复计数</p>
        <div className="insight-list">{query.data.items.map((item) => <InsightRow key={item.id} insight={item} />)}</div>
        <Pagination offset={filters.offset} limit={query.data.limit} total={query.data.total} onChange={(value) => setFilters((current) => ({ ...current, offset: value }))} />
      </>}
    </main>
  );
}
