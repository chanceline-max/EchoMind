import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadProfile, fetchMarkdownPreview, fetchProfile } from "../../src/api/profiles";
import { ProfileDetailPage } from "../../src/pages/ProfileDetailPage";
import { profileDetail } from "../fixtures/profiles";

vi.mock("../../src/api/profiles", () => ({ fetchProfile: vi.fn(), fetchMarkdownPreview: vi.fn(), downloadProfile: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/profiles/profile-1"]}><Routes><Route path="/profiles/:profileId" element={<ProfileDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("ProfileDetailPage", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders structured sections, warnings, refs and pure-text Markdown", async () => {
    vi.mocked(fetchProfile).mockResolvedValue(profileDetail);
    vi.mocked(fetchMarkdownPreview).mockResolvedValue("# EchoProfile\n<script>still text</script>\n");
    renderPage();
    expect(await screen.findByText("Synthetic profile statement.")).toBeInTheDocument();
    expect(screen.getByText("部分证据已失效。")).toBeInTheDocument();
    expect(screen.getByText("待验证假设。")).toBeInTheDocument();
    expect(screen.getAllByText("E001").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /查看本地原消息/ })).toHaveAttribute("href", "/conversations/conversation-1?message=message-1");
    await userEvent.click(screen.getByRole("button", { name: "查看 Markdown 纯文本" }));
    expect(await screen.findByText(/<script>still text<\/script>/)).toBeInTheDocument();
    expect(document.querySelector(".markdown-preview pre")).not.toBeNull();
    expect(document.querySelector("[dangerouslySetInnerHTML]")).toBeNull();
  });

  it("warns again before excerpt export and reports download failure", async () => {
    vi.mocked(fetchProfile).mockResolvedValue({ ...profileDetail, evidence_mode: "excerpts", document: { ...profileDetail.document, metadata: { ...profileDetail.document.metadata, evidence_mode: "excerpts" } } });
    vi.mocked(downloadProfile).mockRejectedValue(new Error("synthetic failure"));
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "导出 JSON" }));
    expect(confirm).toHaveBeenCalled();
    await waitFor(() => expect(downloadProfile).toHaveBeenCalledWith("profile-1", "json"));
    expect(await screen.findByRole("alert")).toHaveTextContent("导出失败");
  });
});
