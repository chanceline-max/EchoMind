# EchoMind backend

阶段 7 的 FastAPI、数据库、Parser、Cleaning、同步导入、LLM Provider 和候选 Insight 抽取工程。除阶段 1–6 能力外，`src/echomind/extraction/` 现在提供严格内部请求、数据库上下文选择、确定性窗口、固定 Prompt、候选验证、本地 Evidence、精确指纹、窗口级事务和安全报告。

Parser 支持 `generic-json`、`generic-csv` 和 `generic-text` 1.0，输出严格 Canonical Chat Schema、原始字节 SHA-256、警告和解析统计。`weflow` 仅返回 `sample_required`，未标记为可用。Parser 不导入 SQLAlchemy Session、不写数据库、不访问网络、不记录聊天正文，也不执行 Cleaner。

Cleaning 输入 `ParsedChatFile + CleaningOptions`，输出独立 `CleanedChatFile`。固定顺序为 whitespace、attachment placeholders、system classification、recalled classification、exact duplicates、URL replacement、opt-in redaction、exclusion、analysis units，最后校验派生引用并重算统计。每次都从 raw 初始化 normalized；不修改 Parser 输入、不删/合并 Message、不写数据库、不读取附件、不访问网络。脱敏默认关闭，排除不等于删除，AnalysisUnit 只引用原消息 ID。

Provider 不读取 ORM、数据库、文件或全局聊天数据，不提供 API 路由。默认 `LLM_PROVIDER=mock` 且 `LLM_REMOTE_ENABLED=false`。远程调用必须同时通过服务端总开关和 `LLMRequest.remote_consent`；输入预算、JSON Schema、解压后响应大小、HTTP 状态和 Pydantic 输出均在独立边界校验。测试只使用 `httpx.MockTransport`，不会访问真实网络。

Extraction 调用方必须明确给出会话 UUID；空集合绝不代表整个数据库。每个会话要求恰好一个 Profile Owner，只选择时间范围内未排除、未归档、未删除消息，并只把匿名角色、窗口局部消息别名、时间、类型和截断后的 `normalized_content` 放入 Provider 请求。默认窗口为 40 条/12000 字符、单条 4000 字符、重叠 4 条、最多 10 个候选；每窗一个会话。远程调用确实会发送当前窗口的 `normalized_content`，仍受阶段 6 双重授权约束。

模型只返回严格候选和局部 Evidence 引用。excerpt 由本地 `normalized_content` 生成（最多 500 字符），不接受模型正文。新 Insight 使用 `confidence=0.0` 与 `confidence_version=unscored` 表示尚未执行阶段 8，模型自评保存在 `model_confidence`。Insight/Evidence 使用 SHA-256 精确指纹；重复运行不新增对象、不覆盖用户编辑或重置用户状态。Provider 调用期间没有数据库写事务，每窗所有合法候选在一个短事务中提交。

格式契约见仓库根目录的 `docs/IMPORT_FORMAT.md`；专项测试命令为：

```powershell
pytest tests/parsers
pytest tests/cleaning
pytest tests/providers
```

默认数据库地址为 `sqlite:///./data/echomind.db`。应用启动不会自动迁移；在 `backend/` 中先创建 `data` 目录，再运行 `alembic upgrade head`。pytest 数据库测试全部使用各自的临时 SQLite 文件。

当前仍不包含分析或 Provider HTTP API、前端模型/Insight 页面、最终置信度算法、Profile、Local 模型运行或远程自动调用。安装、启动、Provider 配置和完整检查命令见仓库根目录的 `README.md`。
