# EchoMind backend

阶段 9 的 FastAPI、数据库、Parser、Cleaning、同步导入、LLM Provider、候选 Insight、确定性置信度和本地审核工程。`src/echomind/services/insight_review_service.py` 提供受限编辑、状态转换、乐观并发和追加式历史；`evidence_validity_service.py` 负责消息排除到 Evidence/Insight/Confidence 的同事务传播。

Parser 支持 `generic-json`、`generic-csv` 和 `generic-text` 1.0，输出严格 Canonical Chat Schema、原始字节 SHA-256、警告和解析统计。`weflow` 仅返回 `sample_required`，未标记为可用。Parser 不导入 SQLAlchemy Session、不写数据库、不访问网络、不记录聊天正文，也不执行 Cleaner。

Cleaning 输入 `ParsedChatFile + CleaningOptions`，输出独立 `CleanedChatFile`。固定顺序为 whitespace、attachment placeholders、system classification、recalled classification、exact duplicates、URL replacement、opt-in redaction、exclusion、analysis units，最后校验派生引用并重算统计。每次都从 raw 初始化 normalized；不修改 Parser 输入、不删/合并 Message、不写数据库、不读取附件、不访问网络。脱敏默认关闭，排除不等于删除，AnalysisUnit 只引用原消息 ID。

Provider 不读取 ORM、数据库、文件或全局聊天数据，不提供 API 路由。默认 `LLM_PROVIDER=mock` 且 `LLM_REMOTE_ENABLED=false`。远程调用必须同时通过服务端总开关和 `LLMRequest.remote_consent`；输入预算、JSON Schema、解压后响应大小、HTTP 状态和 Pydantic 输出均在独立边界校验。测试只使用 `httpx.MockTransport`，不会访问真实网络。

Extraction 调用方必须明确给出会话 UUID；空集合绝不代表整个数据库。每个会话要求恰好一个 Profile Owner，只选择时间范围内未排除、未归档、未删除消息，并只把匿名角色、窗口局部消息别名、时间、类型和截断后的 `normalized_content` 放入 Provider 请求。默认窗口为 40 条/12000 字符、单条 4000 字符、重叠 4 条、最多 10 个候选；每窗一个会话。远程调用确实会发送当前窗口的 `normalized_content`，仍受阶段 6 双重授权约束。

模型只返回严格候选和局部 Evidence 引用。excerpt 由本地 `normalized_content` 生成（最多 500 字符），不接受模型正文。新 Insight 使用 `confidence=0.0` 与 `confidence_version=unscored` 表示尚未评分，并持久化 Candidate 的 `explicit_self_report`；模型自评单独保存在 `model_confidence`。

`confidence-1.0` 不调用 Provider、HTTP、Parser、Cleaner 或上传服务。它只使用 Evidence 有效性/role/相关度及 Message 的时间、会话、sender 和 Owner 标记；不读取正文、excerpt、title、statement、姓名或路径。六个正向因子为 explicitness、evidence quantity、temporal span、跨会话分布、evidence quality 和 recency；普通类型应用相反证据惩罚，contradiction 改用 bilateral balance。类型最低规则失败或没有有效 Evidence 时分数为 0，status 不变。模型自评不进入公式或指纹。

格式契约见仓库根目录的 `docs/IMPORT_FORMAT.md`；专项测试命令为：

```powershell
pytest tests/parsers
pytest tests/cleaning
pytest tests/providers
pytest tests/review
```

默认数据库地址为 `sqlite:///./data/echomind.db`。应用启动不会自动迁移；在 `backend/` 中先创建 `data` 目录，再运行 `alembic upgrade head`。pytest 数据库测试全部使用各自的临时 SQLite 文件。

当前提供 Insight 只读/审核 API，但仍不包含 Extraction、Provider 或独立置信度 HTTP API、用户置信度 override、Profile、Local 模型运行或远程自动调用。安装、启动、公式、Provider 配置和完整检查命令见仓库根目录的 `README.md`。
