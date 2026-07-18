import { apiFetch, apiJson, isRecord, parseApiError } from "./client";
import { APIError } from "../types/api";
import type {
  ProfileDetail,
  ProfileDocument,
  ProfileEvidenceItem,
  ProfileGenerationOptions,
  ProfileGenerationResponse,
  ProfileInsightItem,
  ProfilePage,
  ProfileSection,
  ProfileSummary,
} from "../types/profiles";

const invalid = () =>
  new APIError(0, { error_code: "invalid_response", message: "服务器返回格式无效。" });
const stringOrNull = (value: unknown) => typeof value === "string" || value === null;
const stringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

const validEvidence = (value: unknown): value is ProfileEvidenceItem =>
  isRecord(value) &&
  typeof value.profile_evidence_ref === "string" &&
  typeof value.evidence_id === "string" &&
  typeof value.message_id === "string" &&
  typeof value.conversation_id === "string" &&
  typeof value.evidence_type === "string" &&
  ["supports", "contradicts", "context"].includes(String(value.role)) &&
  typeof value.relevance_score === "number" &&
  typeof value.is_valid === "boolean" &&
  stringArray(value.invalidation_reasons) &&
  stringOrNull(value.message_timestamp) &&
  ["PROFILE_OWNER", "OTHER"].includes(String(value.sender_role)) &&
  stringOrNull(value.excerpt);

const validInsight = (value: unknown): value is ProfileInsightItem =>
  isRecord(value) &&
  typeof value.profile_insight_ref === "string" &&
  typeof value.insight_id === "string" &&
  typeof value.insight_revision_number === "number" &&
  typeof value.insight_type === "string" &&
  typeof value.category === "string" &&
  typeof value.title === "string" &&
  typeof value.statement === "string" &&
  typeof value.confidence === "number" &&
  typeof value.confidence_version === "string" &&
  typeof value.confidence_explanation === "string" &&
  typeof value.evidence_state === "string" &&
  typeof value.explicit_self_report === "boolean" &&
  stringOrNull(value.valid_from) &&
  stringOrNull(value.valid_to) &&
  stringOrNull(value.reasoning_basis) &&
  stringArray(value.alternative_explanations) &&
  stringArray(value.evidence_refs) &&
  stringArray(value.warnings);

const validSection = (value: unknown): value is ProfileSection =>
  isRecord(value) &&
  typeof value.section_key === "string" &&
  typeof value.title === "string" &&
  typeof value.description === "string" &&
  Array.isArray(value.items) &&
  value.items.every(validInsight);

const validDocument = (value: unknown): value is ProfileDocument =>
  isRecord(value) &&
  isRecord(value.metadata) &&
  typeof value.metadata.profile_id === "string" &&
  value.metadata.selection_policy === "confirmed-only-1.0" &&
  typeof value.metadata.document_hash === "string" &&
  typeof value.metadata.evidence_count === "number" &&
  stringArray(value.metadata.limitations) &&
  Array.isArray(value.sections) &&
  value.sections.every(validSection) &&
  Array.isArray(value.evidence_index) &&
  value.evidence_index.every(validEvidence);

const validSummary = (value: unknown): value is ProfileSummary =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.generated_at === "string" &&
  typeof value.profile_version === "string" &&
  typeof value.schema_version === "string" &&
  typeof value.insight_count === "number" &&
  typeof value.evidence_count === "number" &&
  ["references", "excerpts"].includes(String(value.evidence_mode)) &&
  typeof value.document_hash === "string" &&
  ["current", "stale", "source_unavailable"].includes(String(value.current_source_status)) &&
  stringArray(value.stale_reason_codes);

export async function fetchProfiles(offset: number): Promise<ProfilePage> {
  const value = await apiJson(`/api/v1/profiles?limit=20&offset=${offset}`);
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(validSummary) ||
    typeof value.total !== "number" ||
    typeof value.limit !== "number" ||
    typeof value.offset !== "number"
  ) throw invalid();
  return value as unknown as ProfilePage;
}

export async function fetchProfile(id: string): Promise<ProfileDetail> {
  const value = await apiJson(`/api/v1/profiles/${encodeURIComponent(id)}`);
  if (!validSummary(value) || !isRecord(value) || !validDocument(value.document) || !isRecord(value.links)) {
    throw invalid();
  }
  return value as unknown as ProfileDetail;
}

export async function generateProfile(
  options: ProfileGenerationOptions,
): Promise<ProfileGenerationResponse> {
  const value = await apiJson("/api/v1/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      request_id: crypto.randomUUID(),
      profile_version: "echo-profile-1.0",
      profile_schema_version: "echo-profile-document-1.0",
      scope: "all_confirmed",
      selected_insight_ids: [],
      include_partial_evidence: options.includePartialEvidence,
      include_invalidated: options.includeInvalidated,
      evidence_mode: options.evidenceMode,
      include_reasoning: options.includeReasoning,
      generated_as_of: options.generatedAsOf,
    }),
  });
  if (
    !isRecord(value) ||
    typeof value.profile_snapshot_id !== "string" ||
    typeof value.created !== "boolean" ||
    typeof value.reused !== "boolean" ||
    typeof value.document_hash !== "string" ||
    !isRecord(value.links)
  ) throw invalid();
  return value as unknown as ProfileGenerationResponse;
}

export async function fetchMarkdownPreview(id: string): Promise<string> {
  const response = await apiFetch(`/api/v1/profiles/${encodeURIComponent(id)}/markdown`, {
    headers: { Accept: "text/markdown" },
  });
  if (!response.ok) throw parseApiError(response.status, await response.json().catch(() => null));
  return response.text();
}

export async function downloadProfile(id: string, format: "markdown" | "json"): Promise<void> {
  const response = await apiFetch(`/api/v1/profiles/${encodeURIComponent(id)}/${format}`);
  if (!response.ok) throw parseApiError(response.status, await response.json().catch(() => null));
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = format === "markdown" ? "echoprofile.md" : "echoprofile.json";
    anchor.click();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
