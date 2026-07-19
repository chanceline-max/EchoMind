import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchInsights } from "../../src/api/insights";
import { InsightsPage } from "../../src/pages/InsightsPage";
import type { InsightPage, InsightSummary } from "../../src/types/insights";
import { insightSummary } from "../fixtures/insights";

vi.mock("../../src/api/insights", () => ({ fetchInsights: vi.fn() }));
const mockedFetch = vi.mocked(fetchInsights);

const page = (items: InsightSummary[] = [insightSummary]): InsightPage => ({ items, total: items.length, limit: 20, offset: 0 });

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><InsightsPage /></MemoryRouter></QueryClientProvider>);
}

describe("InsightsPage", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders final and model confidence separately and applies filters", async () => {
    mockedFetch.mockResolvedValue(page());
    renderPage();
    expect(await screen.findByText("Synthetic candidate")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.queryByText("88%")).not.toBeInTheDocument();
    expect(screen.getAllByText("待审核").length).toBeGreaterThan(0);
    expect(screen.getAllByText("偏好").length).toBeGreaterThan(0);
    expect(screen.getAllByText("有效").length).toBeGreaterThan(1);
    await userEvent.selectOptions(screen.getByLabelText("状态"), "proposed");
    await waitFor(() => expect(mockedFetch).toHaveBeenLastCalledWith(expect.objectContaining({ status: "proposed", offset: 0 })));
    await userEvent.selectOptions(screen.getByLabelText("排序"), "confidence_asc");
    await waitFor(() => expect(mockedFetch).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "confidence_asc" })));
  });

  it("shows an empty state", async () => {
    mockedFetch.mockResolvedValue(page([]));
    renderPage();
    expect(await screen.findByText("没有符合当前条件的洞察。")).toBeInTheDocument();
  });

  it("shows API and runtime validation failures without real network access", async () => {
    mockedFetch.mockRejectedValue(new Error("invalid response"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("服务器返回格式无效");
  });
});
