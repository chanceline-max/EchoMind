import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchAnalysisCapabilities, startAnalysis } from "../../src/api/analysis";
import { APIError } from "../../src/types/api";

const capabilities = {
  configured_provider: "mock",
  provider_available: true,
  remote_provider: false,
  remote_consent_required: false,
  extraction_version: "candidate-extraction-1.1",
  confidence_version: "confidence-1.0",
  max_conversations_per_request: 100,
};

describe("analysis API", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("validates capabilities and sends only bounded analysis controls", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(capabilities), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        request_id: "request-1", provider_name: "mock", conversation_count: 1,
        selected_message_count: 2, window_count: 1, successful_window_count: 1,
        failed_window_count: 0, candidates_received: 0, candidates_accepted: 0,
        insights_created: 0, insights_reused: 0, insight_ids: [],
        confidence_scored_count: 0, confidence_failed_count: 0, stopped_early: false,
        errors: [], insights_link: "/insights",
      }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchAnalysisCapabilities()).resolves.toEqual(capabilities);
    await startAnalysis({ conversationIds: ["conversation-1"], remoteConsent: false });
    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      conversation_ids: ["conversation-1"], remote_consent: false,
    });
    expect(init.cache).toBe("no-store");
  });

  it("rejects an invalid response shape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ provider_available: true }), { status: 200 })));
    await expect(fetchAnalysisCapabilities()).rejects.toBeInstanceOf(APIError);
  });
});
