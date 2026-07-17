import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { uploadImport, type ImportOptions } from "../../src/api/imports";

class FakeRequest {
  static current: FakeRequest;
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  status = 0;
  responseText = "";
  open = vi.fn();
  setRequestHeader = vi.fn();
  send = vi.fn();
  abort = vi.fn(() => this.onabort?.());
  constructor() { FakeRequest.current = this; }
}

const options: ImportOptions = {
  parserName: "", errorMode: "strict", defaultTimezone: "Asia/Shanghai",
  redactSensitiveData: false, excludeSystemMessages: true,
  excludeRecalledMessages: true, excludeDuplicates: true,
};
const valid = {
  source_file_id: "source-1", filename: "synthetic.json", file_hash: "a".repeat(64),
  file_type: "json", byte_size: 1,
  parser_name: "generic-json", parser_version: "1.0", cleaning_pipeline_version: "1.0",
  imported_at: "2026-07-17T00:00:00Z", conversation_count: 1, participant_count: 1,
  message_count: 1, excluded_message_count: 0, parser_warning_count: 0, cleaning_warning_count: 0,
  analysis_unit_count: 1, warnings: [], links: { self: "/imports/source-1", conversations: "/conversations" },
};

describe("uploadImport", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", "http://test.invalid");
    vi.stubGlobal("XMLHttpRequest", FakeRequest);
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

  it("reports native upload progress and releases handlers after success", async () => {
    const progress = vi.fn();
    const handle = uploadImport(new File(["x"], "synthetic.json"), options, progress);
    FakeRequest.current.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 2 } as ProgressEvent);
    expect(progress).toHaveBeenCalledWith(50);
    FakeRequest.current.status = 201;
    FakeRequest.current.responseText = JSON.stringify(valid);
    FakeRequest.current.onload?.();
    await expect(handle.promise).resolves.toMatchObject({ source_file_id: "source-1" });
    expect(FakeRequest.current.upload.onprogress).toBeNull();
    expect(FakeRequest.current.onload).toBeNull();
  });

  it("parses the safe server error contract", async () => {
    const handle = uploadImport(new File(["x"], "x.json"), options, vi.fn());
    FakeRequest.current.status = 409;
    FakeRequest.current.responseText = JSON.stringify({ error_code: "duplicate_file", message: "Duplicate." });
    FakeRequest.current.onload?.();
    await expect(handle.promise).rejects.toMatchObject({ status: 409, message: "Duplicate." });
  });

  it("supports cancellation without retaining event handlers", async () => {
    const handle = uploadImport(new File(["x"], "x.json"), options, vi.fn());
    handle.cancel();
    await expect(handle.promise).rejects.toMatchObject({ message: "导入已取消。" });
    expect(FakeRequest.current.abort).toHaveBeenCalledOnce();
    expect(FakeRequest.current.onabort).toBeNull();
  });
});
