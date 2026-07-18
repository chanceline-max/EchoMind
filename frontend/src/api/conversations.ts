import { apiJson, isRecord } from "./client";
import { APIError, type ConversationDetail, type ConversationSummary, type MessageSummary, type PaginatedResponse } from "../types/api";

const invalid = () =>
  new APIError(0, { error_code: "invalid_response", message: "服务器返回格式无效。" });

const validConversation = (value: unknown): value is ConversationSummary =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.source_file_id === "string" &&
  typeof value.platform === "string" &&
  typeof value.message_count === "number";

const validMessage = (value: unknown): value is MessageSummary =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.sender_id === "string" &&
  typeof value.sender_display_name === "string" &&
  typeof value.raw_content === "string" &&
  typeof value.normalized_content === "string" &&
  Array.isArray(value.exclusion_reasons) &&
  typeof value.excluded_from_analysis === "boolean";

function validatePage<T>(value: unknown, validItem: (item: unknown) => item is T): PaginatedResponse<T> {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(validItem) ||
    typeof value.total !== "number" ||
    typeof value.limit !== "number" ||
    typeof value.offset !== "number"
  ) throw invalid();
  return value as unknown as PaginatedResponse<T>;
}

export async function fetchConversations(sourceFileId: string, offset: number) {
  const query = new URLSearchParams({ limit: "20", offset: String(offset) });
  if (sourceFileId) query.set("source_file_id", sourceFileId);
  return validatePage(await apiJson(`/api/v1/conversations?${query}`), validConversation);
}

export async function fetchConversation(id: string): Promise<ConversationDetail> {
  const value = await apiJson(`/api/v1/conversations/${encodeURIComponent(id)}`);
  if (!validConversation(value) || !isRecord(value) || !Array.isArray(value.participants)) throw invalid();
  return value as unknown as ConversationDetail;
}

export async function fetchMessages(id: string, offset: number) {
  return validatePage(
    await apiJson(`/api/v1/conversations/${encodeURIComponent(id)}/messages?limit=20&offset=${offset}`),
    validMessage,
  );
}

export async function setMessageExcluded(id: string, excluded: boolean): Promise<MessageSummary> {
  const value = await apiJson(`/api/v1/messages/${encodeURIComponent(id)}/analysis-exclusion`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ excluded }),
  });
  if (!validMessage(value)) throw invalid();
  return value;
}

export interface MessageLocation {
  message_id: string;
  conversation_id: string;
  zero_based_index: number;
  suggested_offset: number;
}

export async function fetchMessageLocation(id: string): Promise<MessageLocation> {
  const value = await apiJson(`/api/v1/messages/${encodeURIComponent(id)}/location`);
  if (
    !isRecord(value) ||
    typeof value.message_id !== "string" ||
    typeof value.conversation_id !== "string" ||
    typeof value.zero_based_index !== "number" ||
    typeof value.suggested_offset !== "number"
  ) throw invalid();
  return value as unknown as MessageLocation;
}
