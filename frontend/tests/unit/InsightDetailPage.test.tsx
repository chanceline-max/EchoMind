import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  confirmInsight,
  editInsight,
  fetchInsight,
  fetchInsightRevisions,
  rejectInsight,
  restoreInsight,
  supersedeInsight,
} from "../../src/api/insights";
import { InsightDetailPage } from "../../src/pages/InsightDetailPage";
import { APIError } from "../../src/types/api";
import type { InsightDetail, ReviewMutationResponse, RevisionPage } from "../../src/types/insights";
import { insightSummary } from "../fixtures/insights";

vi.mock("../../src/api/insights", () => ({
  fetchInsight: vi.fn(), fetchInsightRevisions: vi.fn(), editInsight: vi.fn(),
  confirmInsight: vi.fn(), rejectInsight: vi.fn(), restoreInsight: vi.fn(), supersedeInsight: vi.fn(),
}));

const mockedDetail = vi.mocked(fetchInsight);
const mockedRevisions = vi.mocked(fetchInsightRevisions);
const mockedEdit = vi.mocked(editInsight);
const mockedConfirm = vi.mocked(confirmInsight);

const detail: InsightDetail = {
  ...insightSummary, statement: "Full synthetic statement.", reasoning_basis: "Synthetic local basis.",
  alternative_explanations: ["A different synthetic explanation."], explicit_self_report: true,
  extraction_version: "candidate-extraction-1.0", provider_name: "mock",
  confidence_explanation: "Evidence count and direct self-report support this score.",
  confidence_factors: { evidence_count: 2 }, review_note: null,
  allowed_actions: ["edit", "confirm", "reject", "supersede"],
  evidence: [{ evidence_id: "evidence-1", evidence_type: "supporting", stance: "supports", relevance_score: 0.8,
    is_valid: false, invalidation_reasons: ["source_message_excluded"], invalidated_at: "2026-07-20T01:00:00Z",
    excerpt: "Synthetic evidence excerpt.", message_id: "message-1", conversation_id: "conversation-1",
    message_timestamp: "2026-07-20T00:00:00Z", sender_role: "PROFILE_OWNER", message_excluded_from_analysis: true,
    message_link: "/conversations/conversation-1?message=message-1" }],
};
const revision = { id: "revision-1", insight_id: "insight-1", revision_number: 1, action: "edited",
  actor_type: "local_user" as const, created_at: "2026-07-20T02:00:00Z", expected_previous_revision: 0,
  changed_fields_json: { title: { old: "Old", new: "Synthetic candidate" } }, snapshot_json: { title: "Synthetic candidate" }, note: null };
const revisionPage: RevisionPage = { items: [revision], total: 1, limit: 50, offset: 0 };
const mutationResult: ReviewMutationResponse = { insight: { ...detail, revision_number: 1 }, revision };

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/insights/insight-1"]}><Routes><Route path="/insights/:insightId" element={<InsightDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("InsightDetailPage", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows explanation, anonymized invalid evidence, source link, and revisions", async () => {
    mockedDetail.mockResolvedValue(detail); mockedRevisions.mockResolvedValue(revisionPage);
    renderPage();
    expect(await screen.findByText("Full synthetic statement.")).toBeInTheDocument();
    expect(screen.getByText(/Evidence count and direct/)).toBeInTheDocument();
    expect(screen.getByText("本人")).toBeInTheDocument();
    expect(screen.getByText(/原消息已排除分析/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /查看原消息/ })).toHaveAttribute("href", "/conversations/conversation-1?message=message-1");
    expect(await screen.findByText(/第 1 版 · 已编辑/)).toBeInTheDocument();
    expect(document.querySelector("[dangerouslySetInnerHTML]")).toBeNull();
  });

  it("submits expected revision for edits and invalidates to refresh", async () => {
    mockedDetail.mockResolvedValue(detail); mockedRevisions.mockResolvedValue(revisionPage); mockedEdit.mockResolvedValue(mutationResult);
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "编辑候选" }));
    await userEvent.clear(screen.getByLabelText("标题")); await userEvent.type(screen.getByLabelText("标题"), "Reviewed title");
    await userEvent.click(screen.getByRole("button", { name: "保存修订 1" }));
    await waitFor(() => expect(mockedEdit).toHaveBeenCalledWith("insight-1", expect.objectContaining({ expected_revision: 0, title: "Reviewed title" })));
  });

  it("allows low-confidence confirmation and explains a 409 without overwriting", async () => {
    mockedDetail.mockResolvedValue({ ...detail, confidence: 0.1 }); mockedRevisions.mockResolvedValue(revisionPage);
    mockedConfirm.mockRejectedValue(new APIError(409, { error_code: "insight_revision_conflict", message: "Conflict" }));
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "确认洞察" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("已在其他页面被修改");
    expect(mockedConfirm).toHaveBeenCalledWith("insight-1", { expected_revision: 0 });
  });

  it("labels rejection as retained history rather than deletion", async () => {
    mockedDetail.mockResolvedValue(detail); mockedRevisions.mockResolvedValue(revisionPage);
    vi.spyOn(window, "prompt").mockReturnValue("Synthetic rejection reason.");
    vi.mocked(rejectInsight).mockResolvedValue(mutationResult);
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "驳回" }));
    expect(window.prompt).toHaveBeenCalledWith(expect.stringContaining("不会删除证据"));
    expect(vi.mocked(rejectInsight)).toHaveBeenCalledWith("insight-1", expect.objectContaining({ expected_revision: 0 }));
    expect(vi.mocked(restoreInsight)).not.toHaveBeenCalled();
    expect(vi.mocked(supersedeInsight)).not.toHaveBeenCalled();
  });
});
