const readApiBaseUrl = (): string => {
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
