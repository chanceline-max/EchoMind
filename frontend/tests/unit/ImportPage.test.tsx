import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { uploadImport, type ImportOptions } from "../../src/api/imports";
import { ImportPage } from "../../src/pages/ImportPage";
import { APIError, type ImportDetail } from "../../src/types/api";

vi.mock("../../src/api/imports", () => ({ uploadImport: vi.fn() }));
const mockedUpload = vi.mocked(uploadImport);

const result = {
  source_file_id: "source-1", filename: "synthetic.json", file_hash: "a".repeat(64),
  file_type: "json", byte_size: 10,
  parser_name: "generic-json", parser_version: "1.0", cleaning_pipeline_version: "1.0",
  imported_at: "2026-07-17T00:00:00Z", conversation_count: 1, participant_count: 2,
  message_count: 2, excluded_message_count: 0, parser_warning_count: 0, cleaning_warning_count: 0,
  analysis_unit_count: 1, warnings: [], links: { self: "/imports/source-1", conversations: "/conversations" },
} satisfies ImportDetail;

function renderPage() {
  return render(<MemoryRouter initialEntries={["/import"]}><Routes><Route path="/import" element={<ImportPage />} /><Route path="/imports/:id" element={<p>导入成功</p>} /></Routes></MemoryRouter>);
}

describe("ImportPage", () => {
  afterEach(() => vi.resetAllMocks());

  it("selects a file and submits safe default options", async () => {
    let captured: ImportOptions | undefined;
    mockedUpload.mockImplementation((_file, options) => {
      captured = options;
      return { promise: Promise.resolve(result), cancel: vi.fn() };
    });
    renderPage();
    const file = new File(["synthetic"], "synthetic.json", { type: "application/json" });
    await userEvent.upload(screen.getByLabelText(/选择文件/), file);
    expect(screen.getByText("synthetic.json")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "开始导入" }));
    expect(await screen.findByText("导入成功")).toBeInTheDocument();
    expect(captured).toMatchObject({
      parserName: "", errorMode: "strict", redactSensitiveData: false,
      excludeSystemMessages: true, excludeRecalledMessages: true, excludeDuplicates: true,
    });
  });

  it("shows upload percentage then server processing without fake stage progress", async () => {
    let progress: ((value: number) => void) | undefined;
    mockedUpload.mockImplementation((_file, _options, callback) => {
      progress = callback;
      return { promise: new Promise(() => undefined), cancel: vi.fn() };
    });
    renderPage();
    await userEvent.upload(screen.getByLabelText(/选择文件/), new File(["x"], "x.txt"));
    await userEvent.click(screen.getByRole("button", { name: "开始导入" }));
    progress?.(42);
    expect(await screen.findByText("42%")).toBeInTheDocument();
    progress?.(100);
    expect(await screen.findByText("文件已上传，正在解析并保存。")).toBeInTheDocument();
    expect(screen.queryByText(/Parser.*%/)).not.toBeInTheDocument();
  });

  it.each([
    ["duplicate_file", "This file has already been imported."],
    ["import_limit_exceeded", "The parsed chat exceeds a configured import limit."],
    ["parser_error", "The record is invalid."],
  ])("shows a safe %s error", async (code, message) => {
    mockedUpload.mockImplementation(() => ({ promise: Promise.reject(new APIError(422, { error_code: code, message })), cancel: vi.fn() }));
    renderPage();
    await userEvent.upload(screen.getByLabelText(/选择文件/), new File(["x"], "x.json"));
    await userEvent.click(screen.getByRole("button", { name: "开始导入" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });
});
