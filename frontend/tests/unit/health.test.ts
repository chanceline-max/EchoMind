import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InvalidHealthResponseError, fetchHealth } from "../../src/api/health";

describe("fetchHealth", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", "http://test.invalid");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("accepts the documented health schema without using a real network", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ status: "ok", service: "echomind-api", version: "0.1.0" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchHealth()).resolves.toEqual({
      status: "ok",
      service: "echomind-api",
      version: "0.1.0",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://test.invalid/api/v1/health",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("rejects a response with the wrong schema", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(fetchHealth()).rejects.toBeInstanceOf(InvalidHealthResponseError);
  });
});
