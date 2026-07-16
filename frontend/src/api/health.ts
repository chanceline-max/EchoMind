import { apiFetch } from "./client";
import type { HealthResponse } from "../types/health";

export class InvalidHealthResponseError extends Error {
  constructor() {
    super("The backend health response does not match the expected schema");
    this.name = "InvalidHealthResponseError";
  }
}

const isHealthResponse = (value: unknown): value is HealthResponse => {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    candidate.status === "ok" &&
    typeof candidate.service === "string" &&
    candidate.service.length > 0 &&
    typeof candidate.version === "string" &&
    candidate.version.length > 0
  );
};

export const fetchHealth = async (): Promise<HealthResponse> => {
  const response = await apiFetch("/api/v1/health");
  if (!response.ok) {
    throw new Error(`Backend health check failed with status ${response.status}`);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new InvalidHealthResponseError();
  }

  if (!isHealthResponse(payload)) {
    throw new InvalidHealthResponseError();
  }

  return payload;
};
