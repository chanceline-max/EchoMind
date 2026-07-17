import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InvalidHealthResponseError, fetchHealth } from "../../src/api/health";
import { HomePage } from "../../src/pages/HomePage";

vi.mock("../../src/api/health", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/health")>();
  return { ...actual, fetchHealth: vi.fn() };
});

const mockedFetchHealth = vi.mocked(fetchHealth);
const renderPage = () => render(<MemoryRouter><HomePage /></MemoryRouter>);

describe("HomePage", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders project information and navigation", () => {
    mockedFetchHealth.mockReturnValue(new Promise(() => undefined));
    renderPage();
    expect(screen.getByRole("heading", { name: "EchoMind" })).toBeInTheDocument();
    expect(screen.getByText("Turn conversations into understanding.")).toBeInTheDocument();
    expect(screen.getByText("MVP Import Workflow")).toBeInTheDocument();
    expect(screen.getByText("正在检查后端状态…")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "导入聊天记录" })).toHaveAttribute("href", "/import");
  });

  it("shows the online state after a valid response", async () => {
    mockedFetchHealth.mockResolvedValue({ status: "ok", service: "echomind-api", version: "0.1.0" });
    renderPage();
    expect(await screen.findByText("后端在线")).toBeInTheDocument();
    expect(screen.getByText("echomind-api · 0.1.0")).toBeInTheDocument();
  });

  it("shows the unavailable state when the request fails", async () => {
    mockedFetchHealth.mockRejectedValue(new Error("synthetic network failure"));
    renderPage();
    expect(await screen.findByText("后端不可用")).toBeInTheDocument();
  });

  it("shows the invalid state when the response schema is wrong", async () => {
    mockedFetchHealth.mockRejectedValue(new InvalidHealthResponseError());
    renderPage();
    expect(await screen.findByText("返回格式无效")).toBeInTheDocument();
  });
});
