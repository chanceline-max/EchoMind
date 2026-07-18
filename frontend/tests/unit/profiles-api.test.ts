import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { downloadProfile, fetchProfile, fetchProfiles } from "../../src/api/profiles";
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
});
