import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { uploadImport, type ImportOptions, type UploadHandle } from "../api/imports";
import { APIError } from "../types/api";

const initialOptions: ImportOptions = {
  parserName: "",
  errorMode: "strict",
  defaultTimezone: "Asia/Shanghai",
  redactSensitiveData: false,
  excludeSystemMessages: true,
  excludeRecalledMessages: true,
  excludeDuplicates: true,
};

export function ImportPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const handleRef = useRef<UploadHandle | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [options, setOptions] = useState(initialOptions);
  const [progress, setProgress] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!file) return;
    setError(null);
    setProgress(0);
    setBusy(true);
    const handle = uploadImport(file, options, (value) => {
      setProgress(value);
      if (value === 100) setProcessing(true);
    });
    handleRef.current = handle;
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
    try {
      const result = await handle.promise;
      void navigate(`/imports/${result.source_file_id}`);
    } catch (caught) {
      setError(caught instanceof APIError ? caught.message : "导入失败，请重试。");
    } finally {
      handleRef.current = null;
      setProcessing(false);
      setBusy(false);
    }
  };

  const setBoolean = (key: keyof ImportOptions, checked: boolean) =>
    setOptions((current) => ({ ...current, [key]: checked }));

  return (
    <main className="content-page narrow-page">
      <p className="eyebrow">LOCAL-FIRST IMPORT</p>
      <h1>导入聊天记录</h1>
      <p className="lede">支持 EchoMind 通用 JSON、CSV 和 TXT。原文件仅在本次请求中临时处理，不会长期保存。</p>
      <form className="panel form-grid" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        <label className="file-field">选择文件
          <input ref={inputRef} type="file" accept=".json,.csv,.txt" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <span>{file?.name ?? "尚未选择文件"}</span>
        </label>
        <p className="hint">WeFlow 导入当前尚未支持。</p>
        <label>Parser
          <select value={options.parserName} onChange={(event) => setOptions({ ...options, parserName: event.target.value })}>
            <option value="">自动识别</option>
            <option value="generic-json">JSON</option>
            <option value="generic-csv">CSV</option>
            <option value="generic-text">Text</option>
          </select>
        </label>
        <label>错误模式
          <select value={options.errorMode} onChange={(event) => setOptions({ ...options, errorMode: event.target.value as "strict" | "lenient" })}>
            <option value="strict">strict（遇错停止）</option>
            <option value="lenient">lenient（跳过可恢复记录）</option>
          </select>
        </label>
        <label>默认时区
          <input value={options.defaultTimezone} onChange={(event) => setOptions({ ...options, defaultTimezone: event.target.value })} />
        </label>
        <fieldset><legend>清洗选项</legend>
          {([
            ["redactSensitiveData", "脱敏（默认关闭）"],
            ["excludeSystemMessages", "排除系统消息"],
            ["excludeRecalledMessages", "排除撤回消息"],
            ["excludeDuplicates", "排除重复消息"],
          ] as const).map(([key, label]) => (
            <label className="check-row" key={key}>
              <input type="checkbox" checked={options[key]} onChange={(event) => setBoolean(key, event.target.checked)} />{label}
            </label>
          ))}
        </fieldset>
        {(progress > 0 || processing) && (
          <div className="progress-wrap" role="status">
            <progress max="100" value={progress} /><span>{progress}%</span>
            <p>{processing ? "文件已上传，正在解析并保存。" : "正在上传文件…"}</p>
          </div>
        )}
        {error && <p className="error-box" role="alert">{error}</p>}
        <div className="form-actions">
          <button className="primary-button" type="submit" disabled={!file || busy}>开始导入</button>
          {busy && <button type="button" onClick={() => handleRef.current?.cancel()}>取消</button>}
        </div>
      </form>
    </main>
  );
}
