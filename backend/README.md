# EchoMind backend

阶段 6 的 FastAPI、数据库、Parser、Cleaning、同步导入和 LLM Provider 基础工程。除阶段 1–5 能力外，`src/echomind/providers/` 现在提供 EchoMind 自有的同步请求/响应契约、确定性离线 Mock、OpenAI-compatible HTTP 适配器和明确不可用的 Local 骨架。

Parser 支持 `generic-json`、`generic-csv` 和 `generic-text` 1.0，输出严格 Canonical Chat Schema、原始字节 SHA-256、警告和解析统计。`weflow` 仅返回 `sample_required`，未标记为可用。Parser 不导入 SQLAlchemy Session、不写数据库、不访问网络、不记录聊天正文，也不执行 Cleaner。

Cleaning 输入 `ParsedChatFile + CleaningOptions`，输出独立 `CleanedChatFile`。固定顺序为 whitespace、attachment placeholders、system classification、recalled classification、exact duplicates、URL replacement、opt-in redaction、exclusion、analysis units，最后校验派生引用并重算统计。每次都从 raw 初始化 normalized；不修改 Parser 输入、不删/合并 Message、不写数据库、不读取附件、不访问网络。脱敏默认关闭，排除不等于删除，AnalysisUnit 只引用原消息 ID。

Provider 不读取 ORM、数据库、文件或全局聊天数据，不提供 API 路由。默认 `LLM_PROVIDER=mock` 且 `LLM_REMOTE_ENABLED=false`。远程调用必须同时通过服务端总开关和 `LLMRequest.remote_consent`；输入预算、JSON Schema、解压后响应大小、HTTP 状态和 Pydantic 输出均在独立边界校验。测试只使用 `httpx.MockTransport`，不会访问真实网络。

格式契约见仓库根目录的 `docs/IMPORT_FORMAT.md`；专项测试命令为：

```powershell
pytest tests/parsers
pytest tests/cleaning
pytest tests/providers
```

默认数据库地址为 `sqlite:///./data/echomind.db`。应用启动不会自动迁移；在 `backend/` 中先创建 `data` 目录，再运行 `alembic upgrade head`。pytest 数据库测试全部使用各自的临时 SQLite 文件。

当前仍不包含 Provider HTTP API、前端模型配置、候选 Insight、Evidence 创建、Profile、Local 模型运行或远程自动调用。安装、启动、Provider 配置和完整检查命令见仓库根目录的 `README.md`。
