import { apiJson, isRecord } from "./client";
import { APIError } from "../types/api";
import type {
  InsightDetail,
  InsightFilters,
  InsightPage,
  InsightRevision,
  InsightSummary,
  ReviewMutationResponse,
  RevisionPage,
} from "../types/insights";

const invalid = () =>
  new APIError(0, { error_code: "invalid_response", message: "服务器返回格式无效。" });

const isStringOrNull = (value: unknown): value is string | null =>
  typeof value === "string" || value === null;

const validSummary = (value: unknown): value is InsightSummary =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.title === "string" &&
  typeof value.statement_summary === "string" &&
  typeof value.category === "string" &&
  typeof value.insight_type === "string" &&
  typeof value.status === "string" &&
  typeof value.confidence === "number" &&
  typeof value.confidence_version === "string" &&
  (typeof value.model_confidence === "number" || value.model_confidence === null) &&
  typeof value.evidence_state === "string" &&
  typeof value.evidence_count === "number" &&
  typeof value.valid_evidence_count === "number" &&
  typeof value.revision_number === "number" &&
  isStringOrNull(value.reviewed_at);

const validEvidence = (value: unknown): boolean =>
  isRecord(value) &&
  typeof value.evidence_id === "string" &&
  typeof value.excerpt === "string" &&
  typeof value.is_valid === "boolean" &&
  Array.isArray(value.invalidation_reasons) &&
  value.invalidation_reasons.every((item) => typeof item === "string") &&
  (value.sender_role === "PROFILE_OWNER" || value.sender_role === "OTHER") &&
  typeof value.message_link === "string";

const validDetail = (value: unknown): value is InsightDetail => {
  if (!isRecord(value) || !validSummary(value)) return false;
  const record: Record<string, unknown> = value;
  return (
    typeof record.statement === "string" &&
    Array.isArray(record.alternative_explanations) &&
    record.alternative_explanations.every((item: unknown) => typeof item === "string") &&
    Array.isArray(record.evidence) &&
    record.evidence.every(validEvidence) &&
    Array.isArray(record.allowed_actions) &&
    record.allowed_actions.every((item: unknown) => typeof item === "string")
  );
};

const validRevision = (value: unknown): value is InsightRevision =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.insight_id === "string" &&
  typeof value.revision_number === "number" &&
  typeof value.action === "string" &&
  typeof value.actor_type === "string" &&
  typeof value.created_at === "string" &&
  typeof value.expected_previous_revision === "number" &&
  isRecord(value.changed_fields_json) &&
  isRecord(value.snapshot_json) &&
  isStringOrNull(value.note);

function validPage<T>(
  value: unknown,
  validateItem: (item: unknown) => item is T,
): value is { items: T[]; total: number; limit: number; offset: number } {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(validateItem) &&
    typeof value.total === "number" &&
    typeof value.limit === "number" &&
    typeof value.offset === "number"
  );
}

export async function fetchInsights(filters: InsightFilters): Promise<InsightPage> {
  const query = new URLSearchParams({
    limit: "20",
    offset: String(filters.offset),
    sort: filters.sort,
  });
  const optional: Array<[string, string]> = [
    ["status", filters.status],
    ["insight_type", filters.insightType],
    ["category", filters.category],
    ["evidence_state", filters.evidenceState],
    ["min_confidence", filters.minConfidence],
    ["max_confidence", filters.maxConfidence],
  ];
  optional.forEach(([key, value]) => value && query.set(key, value));
  const value = await apiJson(`/api/v1/insights?${query}`);
  if (!validPage(value, validSummary)) throw invalid();
  return value;
}

export async function fetchInsight(id: string): Promise<InsightDetail> {
  const value = await apiJson(`/api/v1/insights/${encodeURIComponent(id)}`);
  if (!validDetail(value)) throw invalid();
  return value;
}

export async function fetchInsightRevisions(id: string): Promise<RevisionPage> {
  const value = await apiJson(`/api/v1/insights/${encodeURIComponent(id)}/revisions`);
  if (!validPage(value, validRevision)) throw invalid();
  return value;
}

async function reviewMutation(
  path: string,
  method: "PATCH" | "POST",
  body: Record<string, unknown>,
): Promise<ReviewMutationResponse> {
  const value = await apiJson(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!isRecord(value) || !validDetail(value.insight) || !validRevision(value.revision)) {
    throw invalid();
  }
  return value as unknown as ReviewMutationResponse;
}

export const editInsight = (id: string, body: Record<string, unknown>) =>
  reviewMutation(`/api/v1/insights/${encodeURIComponent(id)}`, "PATCH", body);
export const confirmInsight = (id: string, body: Record<string, unknown>) =>
  reviewMutation(`/api/v1/insights/${encodeURIComponent(id)}/confirm`, "POST", body);
export const rejectInsight = (id: string, body: Record<string, unknown>) =>
  reviewMutation(`/api/v1/insights/${encodeURIComponent(id)}/reject`, "POST", body);
export const restoreInsight = (id: string, body: Record<string, unknown>) =>
  reviewMutation(`/api/v1/insights/${encodeURIComponent(id)}/restore`, "POST", body);
export const supersedeInsight = (id: string, body: Record<string, unknown>) =>
  reviewMutation(`/api/v1/insights/${encodeURIComponent(id)}/supersede`, "POST", body);
