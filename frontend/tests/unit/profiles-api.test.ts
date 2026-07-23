import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { downloadProfile, fetchProfile, fetchProfiles, generateProfile } from "../../src/api/profiles";
import { APIError } from "../../src/types/api";
import { profileDetail, profileSummary } from "../fixtures/profiles";

describe("Profile API runtime validation and downloads", () => {
  beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "http://test.invalid"));
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("validates list and rejects malformed detail without rendering partial data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ items: [profileSummary], total: 1, limit: 20, offset: 0 }), { status: 200 })).mockResolvedValueOnce(new Response(JSON.stringify({ ...profileDetail, document: { metadata: {} } }), { status: 200 })));
    await expect(fetchProfiles(0)).resolves.toMatchObject({ total: 1 });
    await expect(fetchProfile("profile-1")).rejects.toBeInstanceOf(APIError);
  });

  it("downloads only after invocation and always releases the Object URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("# EchoProfile\n", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const create = vi.fn().mockReturnValue("blob:synthetic");
    const revoke = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL: create, revokeObjectURL: revoke });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    expect(fetchMock).not.toHaveBeenCalled();
    await downloadProfile("profile-1", "markdown");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(create).toHaveBeenCalledTimes(1);
    expect(revoke).toHaveBeenCalledWith("blob:synthetic");
  });

  it("sends the explicit Profile 2.0 synthesis and consent contract", async () => {
    const response = {
      profile_snapshot_id: "profile-2",
      profile_version: "echo-profile-2.0",
      schema_version: "echo-profile-document-2.0",
      generated_at: "2026-07-23T00:00:00Z",
      source_fingerprint: "a".repeat(64),
      generation_fingerprint: "b".repeat(64),
      document_hash: "c".repeat(64),
      insight_count: 2,
      evidence_count: 3,
      source_status: "current",
      created: true,
      reused: false,
      links: { self: "/p", markdown: "/m", json: "/j" },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "00000000-0000-0000-0000-000000000001" });

    await generateProfile({
      includePartialEvidence: true,
      includeInvalidated: true,
      evidenceMode: "references",
      includeReasoning: true,
      includePersonalitySynthesis: true,
      remoteConsent: true,
      generatedAsOf: "2026-07-23T00:00:00Z",
    });

    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    if (typeof request.body !== "string") throw new Error("Profile request body is not JSON");
    expect(JSON.parse(request.body)).toMatchObject({
      profile_version: "echo-profile-2.0",
      profile_schema_version: "echo-profile-document-2.0",
      evidence_mode: "references",
      include_personality_synthesis: true,
      remote_consent: true,
    });
  });
});
