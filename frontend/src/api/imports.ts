import { isRecord, parseApiError, readApiBaseUrl, apiJson } from "./client";
import { APIError, type ImportDetail } from "../types/api";

export interface ImportOptions {
  parserName: string;
  errorMode: "strict" | "lenient";
  defaultTimezone: string;
  redactSensitiveData: boolean;
  excludeSystemMessages: boolean;
  excludeRecalledMessages: boolean;
  excludeDuplicates: boolean;
}

export interface UploadHandle {
  promise: Promise<ImportDetail>;
  cancel: () => void;
}

export function validateImportDetail(value: unknown): ImportDetail {
  if (
    !isRecord(value) ||
    typeof value.source_file_id !== "string" ||
    typeof value.filename !== "string" ||
    typeof value.file_hash !== "string" ||
    typeof value.file_type !== "string" ||
    typeof value.byte_size !== "number" ||
    typeof value.parser_name !== "string" ||
    typeof value.parser_version !== "string" ||
    typeof value.cleaning_pipeline_version !== "string" ||
    typeof value.imported_at !== "string" ||
    typeof value.conversation_count !== "number" ||
    typeof value.participant_count !== "number" ||
    typeof value.message_count !== "number" ||
    typeof value.excluded_message_count !== "number" ||
    typeof value.analysis_unit_count !== "number" ||
    typeof value.parser_warning_count !== "number" ||
    typeof value.cleaning_warning_count !== "number" ||
    !Array.isArray(value.warnings) ||
    !isRecord(value.links)
  ) {
    throw new APIError(0, {
      error_code: "invalid_response",
      message: "导入结果格式无效。",
    });
  }
  return value as unknown as ImportDetail;
}

export function uploadImport(
  file: File,
  options: ImportOptions,
  onProgress: (percent: number) => void,
): UploadHandle {
  const request = new XMLHttpRequest();
  const form = new FormData();
  form.append("file", file);
  if (options.parserName) form.append("parser_name", options.parserName);
  form.append("error_mode", options.errorMode);
  if (options.defaultTimezone.trim()) form.append("default_timezone", options.defaultTimezone.trim());
  form.append(
    "cleaning_options_json",
    JSON.stringify({
      redact_sensitive_data: options.redactSensitiveData,
      exclude_system_messages: options.excludeSystemMessages,
      exclude_recalled_messages: options.excludeRecalledMessages,
      exclude_duplicates: options.excludeDuplicates,
    }),
  );

  const promise = new Promise<ImportDetail>((resolve, reject) => {
    const cleanup = () => {
      request.upload.onprogress = null;
      request.onload = null;
      request.onerror = null;
      request.onabort = null;
    };
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => {
      try {
        const value: unknown = JSON.parse(request.responseText);
        if (request.status < 200 || request.status >= 300) {
          reject(parseApiError(request.status, value));
        } else {
          resolve(validateImportDetail(value));
        }
      } catch (error) {
        reject(
          error instanceof APIError
            ? error
            : new APIError(request.status, {
                error_code: "invalid_response",
                message: "服务器返回格式无效。",
              }),
        );
      } finally {
        cleanup();
      }
    };
    request.onerror = () => {
      cleanup();
      reject(new APIError(0, { error_code: "network_error", message: "无法连接本地后端。" }));
    };
    request.onabort = () => {
      cleanup();
      reject(new APIError(0, { error_code: "cancelled", message: "导入已取消。" }));
    };
    request.open("POST", `${readApiBaseUrl()}/api/v1/imports`);
    request.setRequestHeader("Accept", "application/json");
    request.send(form);
  });
  return { promise, cancel: () => request.abort() };
}

export async function fetchImport(id: string): Promise<ImportDetail> {
  return validateImportDetail(await apiJson(`/api/v1/imports/${encodeURIComponent(id)}`));
}
