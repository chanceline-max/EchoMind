import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { batchConfirmInsights, fetchInsights } from "../api/insights";
import { Pagination } from "../components/Pagination";
import {
  categoryLabel,
  evidenceStateLabel,
  evidenceStateOptions,
  insightStatusLabel,
  insightStatusOptions,
  insightTypeLabel,
  insightTypeOptions,
} from "../labels";
import type { InsightFilters, InsightSummary } from "../types/insights";

const initialFilters: InsightFilters = {
  reviewBucket: "manual",
  status: "proposed",
  insightType: "",
  category: "",
  evidenceState: "",
  minConfidence: "",
  maxConfidence: "",
  sort: "updated_at_desc",
  offset: 0,
};

const batchFilters: InsightFilters = {
  reviewBucket: "batch_eligible",
  status: "proposed",
  insightType: "",
  category: "",
  evidenceState: "valid",
  minConfidence: "",
  maxConfidence: "",
  sort: "confidence_desc",
  offset: 0,
};

const percent = (value: number) => `${Math.round(value * 100)}%`;

function InsightRow({ insight }: { insight: InsightSummary }) {
  return (
    <Link className="insight-row" to={`/insights/${insight.id}`}>
      <div className="insight-row__top">
        <div>
          <span className={`status-chip status-${insight.status}`}>{insightStatusLabel(insight.status)}</span>
          <span className="type-chip">{insightTypeLabel(insight.insight_type)}</span>
        </div>
        <strong className="confidence-number">{percent(insight.confidence)}</strong>
      </div>
      <h2>{insight.title}</h2>
      <p>{insight.statement_summary}</p>
      <dl className="row-facts">
        <div><dt>分类</dt><dd>{categoryLabel(insight.category)}</dd></div>
        <div><dt>证据</dt><dd>{insight.valid_evidence_count}/{insight.evidence_count} 有效</dd></div>
        <div><dt>证据状态</dt><dd>{evidenceStateLabel(insight.evidence_state)}</dd></div>
        <div><dt>修订</dt><dd>第 {insight.revision_number} 版</dd></div>
      </dl>
    </Link>
  );
}

export function InsightsPage() {
  const [filters, setFilters] = useState(initialFilters);
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["insights", filters],
    queryFn: () => fetchInsights(filters),
    staleTime: 0,
  });
  const batchCandidates = useQuery({
    queryKey: ["insights", "batch-eligible"],
    queryFn: () => fetchInsights(batchFilters),
    staleTime: 0,
  });
  const batchConfirmation = useMutation({
    mutationFn: () => batchConfirmInsights(
      (batchCandidates.data?.items ?? []).map((item) => ({
        insight_id: item.id,
        expected_revision: item.revision_number,
      })),
    ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["insights"] });
    },
  });
  const update = (field: Exclude<keyof InsightFilters, "offset">, value: string) =>
    setFilters((current) => ({ ...current, [field]: value, offset: 0 }));

  return (
    <main className="content-page review-page">
      <div className="review-heading">
        <div><p className="eyebrow">人工审核</p><h1>洞察审核台</h1></div>
        <p>AI 判断先作为候选保留。沿证据链检查、修订，再决定确认、驳回或替代。已保存候选会保留生成时的语言；中文输出规则只影响之后重新分析产生的新候选。</p>
      </div>
      <section className="panel" aria-labelledby="batch-review-title">
        <div className="section-heading">
          <div><p className="eyebrow">减少逐条操作</p><h2 id="batch-review-title">高置信快速确认</h2></div>
          <span>{batchCandidates.data?.total ?? 0} 条待处理</span>
        </div>
        <p>仅包含置信度严格高于 50%、证据有效的事实、偏好、模式和变化。推断、假设、矛盾以及刚好 50% 的候选仍需逐条审核。</p>
        {batchCandidates.isPending && <p className="loading-line">正在检查可批量确认的候选…</p>}
        {batchCandidates.isError && <p className="error-box" role="alert">无法读取批量确认范围。</p>}
        {batchCandidates.data && batchCandidates.data.items.length === 0 && <p className="empty-state">目前没有可批量确认的高置信候选。</p>}
        {batchCandidates.data && batchCandidates.data.items.length > 0 && <>
          <ul className="revision-list" aria-label="本批确认范围">
            {batchCandidates.data.items.map((item) => <li key={item.id}><Link to={`/insights/${item.id}`}>{item.title}</Link><small>{insightTypeLabel(item.insight_type)} · {percent(item.confidence)}</small></li>)}
          </ul>
          <div className="generator-action">
            <button
              className="primary-button"
              disabled={batchConfirmation.isPending}
              onClick={() => {
                const count = batchCandidates.data.items.length;
                if (window.confirm(`将批量确认当前 ${count} 条高置信候选，并为每条写入独立修订记录。是否继续？`)) {
                  batchConfirmation.mutate();
                }
              }}
            >{batchConfirmation.isPending ? "正在批量确认…" : `批量确认当前 ${batchCandidates.data.items.length} 条`}</button>
            <span>{batchCandidates.data.total > batchCandidates.data.items.length ? "完成后可继续处理下一批" : "这是当前全部符合条件的候选"}</span>
          </div>
        </>}
        {batchConfirmation.isError && <p className="error-box" role="alert">批量确认失败，整批均未写入。请刷新后重试。</p>}
        {batchConfirmation.data && <p className="success-box" role="status">已批量确认 {batchConfirmation.data.confirmed_count} 条洞察，每条均保留独立修订记录。</p>}
      </section>
      <section className="filter-desk" aria-label="洞察筛选">
        <label>审核队列<select value={filters.reviewBucket} onChange={(event) => update("reviewBucket", event.target.value)}><option value="manual">需逐条审核</option><option value="">全部记录</option></select></label>
        <label>状态<select value={filters.status} onChange={(event) => update("status", event.target.value)}><option value="">全部</option>{insightStatusOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label>类型<select value={filters.insightType} onChange={(event) => update("insightType", event.target.value)}><option value="">全部</option>{insightTypeOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label>证据<select value={filters.evidenceState} onChange={(event) => update("evidenceState", event.target.value)}><option value="">全部</option>{evidenceStateOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label>分类<input value={filters.category} onChange={(event) => update("category", event.target.value)} placeholder="例如：价值观" /></label>
        <label>最低置信度<input aria-label="最低置信度" type="number" min="0" max="1" step="0.05" value={filters.minConfidence} onChange={(event) => update("minConfidence", event.target.value)} /></label>
        <label>最高置信度<input aria-label="最高置信度" type="number" min="0" max="1" step="0.05" value={filters.maxConfidence} onChange={(event) => update("maxConfidence", event.target.value)} /></label>
        <label>排序<select value={filters.sort} onChange={(event) => update("sort", event.target.value)}><option value="updated_at_desc">最近更新</option><option value="created_at_desc">最近创建</option><option value="confidence_desc">置信度从高到低</option><option value="confidence_asc">置信度从低到高</option></select></label>
      </section>
      {query.isPending && <p className="loading-line">正在读取候选洞察…</p>}
      {query.isError && <p className="error-box" role="alert">无法读取洞察，或服务器返回格式无效。</p>}
      {query.data?.items.length === 0 && <div className="empty-state">没有符合当前条件的洞察。</div>}
      {query.data && query.data.items.length > 0 && <>
        <p className="result-count">共 {query.data.total} 条，不因多条证据重复计数</p>
        <div className="insight-list">{query.data.items.map((item) => <InsightRow key={item.id} insight={item} />)}</div>
        <Pagination offset={filters.offset} limit={query.data.limit} total={query.data.total} onChange={(value) => setFilters((current) => ({ ...current, offset: value }))} />
      </>}
    </main>
  );
}
