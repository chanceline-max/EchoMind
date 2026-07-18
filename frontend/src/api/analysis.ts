import { apiJson, isRecord } from "./client";
import { APIError } from "../types/api";
import type {
  AnalysisCapabilities,
  AnalysisErrorRecord,
  AnalysisResponse,
  StartAnalysisInput,
} from "../types/analysis";

const invalid = () =>
  new APIError(0, { error_code: "invalid_response", message: "服务器返回格式无效。" });

const isErrorRecord = (value: unknown): value is AnalysisErrorRecord =>
  isRecord(value) &&
  typeof value.error_code === "string" &&
  typeof value.message === "string" &&
  typeof value.recoverable === "boolean";

export async function fetchAnalysisCapabilities(): Promise<AnalysisCapabilities> {
  const value = await apiJson("/api/v1/analysis/capabilities");
  if (
    !isRecord(value) ||
    typeof value.configured_provider !== "string" ||
    typeof value.provider_available !== "boolean" ||
    typeof value.remote_provider !== "boolean" ||
    typeof value.remote_consent_required !== "boolean" ||
    typeof value.extraction_version !== "string" ||
    typeof value.confidence_version !== "string" ||
    typeof value.max_conversations_per_request !== "number"
  ) {
    throw invalid();
  }
  return value as unknown as AnalysisCapabilities;
}

export async function startAnalysis(input: StartAnalysisInput): Promise<AnalysisResponse> {
  const value = await apiJson("/api/v1/analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_ids: input.conversationIds,
      remote_consent: input.remoteConsent,
    }),
  });
  if (
    !isRecord(value) ||
    typeof value.request_id !== "string" ||
    typeof value.provider_name !== "string" ||
    typeof value.conversation_count !== "number" ||
    typeof value.selected_message_count !== "number" ||
    typeof value.window_count !== "number" ||
    typeof value.successful_window_count !== "number" ||
    typeof value.failed_window_count !== "number" ||
    typeof value.candidates_received !== "number" ||
    typeof value.candidates_accepted !== "number" ||
    typeof value.insights_created !== "number" ||
    typeof value.insights_reused !== "number" ||
    !Array.isArray(value.insight_ids) ||
    !value.insight_ids.every((item) => typeof item === "string") ||
    typeof value.confidence_scored_count !== "number" ||
    typeof value.confidence_failed_count !== "number" ||
    typeof value.stopped_early !== "boolean" ||
    !Array.isArray(value.errors) ||
    !value.errors.every(isErrorRecord) ||
    typeof value.insights_link !== "string"
  ) {
    throw invalid();
  }
  return value as unknown as AnalysisResponse;
}
