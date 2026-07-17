# EchoMind backend

阶段 4 的 FastAPI、数据库、Parser 与 Cleaning 基础工程。当前包含 `/api/v1/health`、八个核心 SQLAlchemy 模型、独立数据库 Pydantic Schema、同步 SQLite Session 工厂、Alembic 初始迁移、位于 `src/echomind/parsers/` 的数据库无关 Parser，以及位于 `src/echomind/cleaning/` 的纯内存清洗 Pipeline。

Parser 支持 `generic-json`、`generic-csv` 和 `generic-text` 1.0，输出严格 Canonical Chat Schema、原始字节 SHA-256、警告和解析统计。`weflow` 仅返回 `sample_required`，未标记为可用。Parser 不导入 SQLAlchemy Session、不写数据库、不访问网络、不记录聊天正文，也不执行 Cleaner。

Cleaning 输入 `ParsedChatFile + CleaningOptions`，输出独立 `CleanedChatFile`。固定顺序为 whitespace、attachment placeholders、system classification、recalled classification、exact duplicates、URL replacement、opt-in redaction、exclusion、analysis units，最后校验派生引用并重算统计。每次都从 raw 初始化 normalized；不修改 Parser 输入、不删/合并 Message、不写数据库、不读取附件、不访问网络。脱敏默认关闭，排除不等于删除，AnalysisUnit 只引用原消息 ID。

格式契约见仓库根目录的 `docs/IMPORT_FORMAT.md`；专项测试命令为：

```powershell
pytest tests/parsers
pytest tests/cleaning
```

默认数据库地址为 `sqlite:///./data/echomind.db`。应用启动不会自动迁移；在 `backend/` 中先创建 `data` 目录，再运行 `alembic upgrade head`。pytest 数据库测试全部使用各自的临时 SQLite 文件。

当前仍不包含 CRUD API、文件上传、导入任务、Cleaning 数据库写入、状态传播或模型调用。安装、启动和完整检查命令见仓库根目录的 `README.md`。
