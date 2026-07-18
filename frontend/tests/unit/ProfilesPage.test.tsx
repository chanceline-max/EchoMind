import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchProfiles, generateProfile } from "../../src/api/profiles";
import { ProfilesPage } from "../../src/pages/ProfilesPage";
import { profileSummary } from "../fixtures/profiles";

vi.mock("../../src/api/profiles", () => ({ fetchProfiles: vi.fn(), generateProfile: vi.fn() }));
const mockedFetch = vi.mocked(fetchProfiles);
const mockedGenerate = vi.mocked(generateProfile);

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><ProfilesPage /></MemoryRouter></QueryClientProvider>);
}

describe("ProfilesPage", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows current, stale and unavailable snapshots with text states", async () => {
    mockedFetch.mockResolvedValue({ items: [profileSummary, { ...profileSummary, id: "p2", current_source_status: "stale", stale_reason_codes: ["insight_revision_changed"] }, { ...profileSummary, id: "p3", current_source_status: "source_unavailable" }], total: 3, limit: 20, offset: 0 });
    renderPage();
    expect(await screen.findByText("当前")).toBeInTheDocument();
    expect(screen.getByText("来源已变化")).toBeInTheDocument();
    expect(screen.getByText("来源不可用")).toBeInTheDocument();
  });

  it("uses confirmed-only references defaults and requires excerpt confirmation", async () => {
    mockedFetch.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    mockedGenerate.mockResolvedValue({ profile_snapshot_id: "profile-1", profile_version: "echo-profile-1.0", schema_version: "echo-profile-document-1.0", generated_at: "2026-07-21T00:00:00Z", source_fingerprint: "a".repeat(64), generation_fingerprint: "b".repeat(64), document_hash: "c".repeat(64), insight_count: 1, evidence_count: 1, source_status: "current", created: false, reused: true, links: { self: "/p", markdown: "/m", json: "/j" } });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();
    expect(await screen.findByText(/还没有 Profile/)).toBeInTheDocument();
    expect(screen.getByLabelText("Evidence 模式")).toHaveValue("references");
    await userEvent.selectOptions(screen.getByLabelText("Evidence 模式"), "excerpts");
    expect(screen.getByText(/敏感导出/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "生成 Profile" }));
    expect(confirm).toHaveBeenCalled();
    await waitFor(() => expect(mockedGenerate).toHaveBeenCalledWith(expect.objectContaining({ evidenceMode: "excerpts", includePartialEvidence: true, includeInvalidated: true, includeReasoning: true })));
    expect(await screen.findByText(/已复用相同来源/)).toBeInTheDocument();
  });

  it("shows safe loading and error states without real network", async () => {
    mockedFetch.mockRejectedValue(new Error("invalid response"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("服务器返回格式无效");
  });
});
