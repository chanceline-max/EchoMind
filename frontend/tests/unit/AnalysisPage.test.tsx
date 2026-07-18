import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAnalysisCapabilities, startAnalysis } from "../../src/api/analysis";
import { fetchConversations } from "../../src/api/conversations";
import { AnalysisPage } from "../../src/pages/AnalysisPage";

vi.mock("../../src/api/analysis", () => ({ fetchAnalysisCapabilities: vi.fn(), startAnalysis: vi.fn() }));
vi.mock("../../src/api/conversations", () => ({ fetchConversations: vi.fn() }));

const mockedCapabilities = vi.mocked(fetchAnalysisCapabilities);
const mockedAnalysis = vi.mocked(startAnalysis);
const mockedConversations = vi.mocked(fetchConversations);
const localCapabilities = {
  configured_provider: "mock", provider_available: true, remote_provider: false,
  remote_consent_required: false, extraction_version: "candidate-extraction-1.0",
  confidence_version: "confidence-1.0", max_conversations_per_request: 100,
};
const conversationPage = {
  items: [{ id: "conversation-1", source_file_id: "source-1", platform: "synthetic",
    title: "Synthetic conversation", started_at: "2026-07-18T00:00:00Z",
    ended_at: "2026-07-18T01:00:00Z", participant_count: 1, message_count: 2,
    excluded_message_count: 0 }], total: 1, limit: 20, offset: 0,
};
const response = {
  request_id: "request-1", provider_name: "mock", conversation_count: 1,
  selected_message_count: 2, window_count: 1, successful_window_count: 1,
  failed_window_count: 0, candidates_received: 1, candidates_accepted: 1,
  insights_created: 1, insights_reused: 0, insight_ids: ["insight-1"],
  confidence_scored_count: 1, confidence_failed_count: 0, stopped_early: false,
  errors: [], insights_link: "/insights",
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><AnalysisPage /></MemoryRouter></QueryClientProvider>);
}

describe("AnalysisPage", () => {
  afterEach(() => vi.resetAllMocks());

  it("selects a conversation and displays completed scoring counts", async () => {
    mockedCapabilities.mockResolvedValue(localCapabilities);
    mockedConversations.mockResolvedValue(conversationPage);
    mockedAnalysis.mockResolvedValue(response);
    renderPage();
    await userEvent.click(await screen.findByRole("checkbox", { name: /Synthetic conversation/ }));
    await userEvent.click(screen.getByRole("button", { name: "开始分析" }));
    await waitFor(() => expect(mockedAnalysis.mock.calls[0]?.[0]).toEqual({ conversationIds: ["conversation-1"], remoteConsent: false }));
    expect(await screen.findByRole("heading", { name: "分析完成" })).toBeInTheDocument();
    expect(document.querySelector(".analysis-metrics")).toHaveTextContent("1 新 Insight");
    expect(screen.getByRole("link", { name: "查看生成的 Insights" })).toHaveAttribute("href", "/insights");
  });

  it("shows the exact synchronous processing state without fake progress", async () => {
    mockedCapabilities.mockResolvedValue(localCapabilities);
    mockedConversations.mockResolvedValue(conversationPage);
    mockedAnalysis.mockImplementation(() => new Promise(() => undefined));
    renderPage();
    await userEvent.click(await screen.findByRole("checkbox", { name: /Synthetic conversation/ }));
    await userEvent.click(screen.getByRole("button", { name: "开始分析" }));
    expect(await screen.findByRole("status")).toHaveTextContent("正在分析所选会话。");
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("explains an empty result and disables an unavailable provider", async () => {
    mockedCapabilities.mockResolvedValue({ ...localCapabilities, provider_available: false });
    mockedConversations.mockResolvedValue(conversationPage);
    renderPage();
    await userEvent.click(await screen.findByRole("checkbox", { name: /Synthetic conversation/ }));
    expect(screen.getByRole("button", { name: "开始分析" })).toBeDisabled();
    expect(screen.getByText(/未配置或不可用/)).toBeInTheDocument();
  });

  it("requires explicit remote consent and states what is sent", async () => {
    mockedCapabilities.mockResolvedValue({ ...localCapabilities, configured_provider: "openai_compatible", remote_provider: true, remote_consent_required: true });
    mockedConversations.mockResolvedValue(conversationPage);
    mockedAnalysis.mockResolvedValue({ ...response, provider_name: "openai_compatible", insight_ids: [], insights_created: 0, candidates_received: 0, candidates_accepted: 0, confidence_scored_count: 0 });
    renderPage();
    await userEvent.click(await screen.findByRole("checkbox", { name: /Synthetic conversation/ }));
    expect(screen.getByText(/会发送当前所选会话窗口的 normalized_content/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始分析" })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: /我同意/ }));
    expect(screen.getByRole("button", { name: "开始分析" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "开始分析" }));
    expect(await screen.findByText("本次没有生成候选 Insight。")).toBeInTheDocument();
  });
});
