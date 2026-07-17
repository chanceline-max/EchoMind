import { APIError, type APIErrorBody } from "../types/api";

export const readApiBaseUrl = (): string => {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!configuredUrl) {
    throw new Error("VITE_API_BASE_URL is not configured");
  }
  return configuredUrl.replace(/\/+$/, "");
};

export const apiFetch = (path: string, init?: RequestInit): Promise<Response> =>
  fetch(`${readApiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

export const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

export const parseApiError = (status: number, value: unknown): APIError => {
  const body: APIErrorBody =
    isRecord(value) && typeof value.error_code === "string" && typeof value.message === "string"
      ? {
          error_code: value.error_code,
          message: value.message,
          recoverable: typeof value.recoverable === "boolean" ? value.recoverable : undefined,
          safe_filename: typeof value.safe_filename === "string" ? value.safe_filename : undefined,
          location: typeof value.location === "string" ? value.location : undefined,
        }
      : { error_code: "invalid_error_response", message: "服务器返回了无法识别的错误。" };
  return new APIError(status, body);
};

export async function apiJson(path: string, init?: RequestInit): Promise<unknown> {
  const response = await apiFetch(path, init);
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new APIError(response.status, {
      error_code: "invalid_response",
      message: "服务器返回格式无效。",
    });
  }
  if (!response.ok) {
    throw parseApiError(response.status, value);
  }
  return value;
}
