import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { batchConfirmInsights, fetchInsight, fetchInsights } from "../../src/api/insights";
import { APIError } from "../../src/types/api";
import { insightSummary } from "../fixtures/insights";

describe("Insight API runtime validation", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "http://test.invalid"));
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

  it("rejects a malformed list without accepting partial content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [{ id: "only-id" }], total: 1, limit: 20, offset: 0 }), { status: 200 })));
    await expect(fetchInsights({ reviewBucket: "manual", status: "", insightType: "", category: "", evidenceState: "", minConfidence: "", maxConfidence: "", sort: "updated_at_desc", offset: 0 })).rejects.toMatchObject({ body: { error_code: "invalid_response" } });
  });

  it("rejects detail evidence with an invalid sender role", async () => {
    const malformed = { ...insightSummary, statement: "Synthetic", alternative_explanations: [], allowed_actions: [], evidence: [{ evidence_id: "e", excerpt: "x", is_valid: true, invalidation_reasons: [], sender_role: "Private Person", message_link: "/x" }] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(malformed), { status: 200 })));
    await expect(fetchInsight("insight-1")).rejects.toBeInstanceOf(APIError);
  });

  it("validates a batch confirmation response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      confirmed_ids: ["insight-1"], confirmed_count: 1,
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(batchConfirmInsights([
      { insight_id: "insight-1", expected_revision: 0 },
    ])).resolves.toEqual({ confirmed_ids: ["insight-1"], confirmed_count: 1 });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://test.invalid/api/v1/insights/batch-confirm",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("rejects an empty batch confirmation response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      confirmed_ids: [], confirmed_count: 0,
    }), { status: 200 })));
    await expect(batchConfirmInsights([
      { insight_id: "insight-1", expected_revision: 0 },
    ])).rejects.toMatchObject({ body: { error_code: "invalid_response" } });
  });
});
