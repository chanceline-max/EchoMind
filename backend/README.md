# EchoMind backend

阶段 3 的 FastAPI、数据库与 Parser 基础工程。当前包含 `/api/v1/health`、八个核心 SQLAlchemy 模型、独立数据库 Pydantic Schema、同步 SQLite Session 工厂、Alembic 初始迁移，以及位于 `src/echomind/parsers/` 的数据库无关 Parser 系统。

Parser 支持 `generic-json`、`generic-csv` 和 `generic-text` 1.0，输出严格 Canonical Chat Schema、原始字节 SHA-256、警告和解析统计。`weflow` 仅返回 `sample_required`，未标记为可用。Parser 不导入 SQLAlchemy Session、不写数据库、不访问网络、不记录聊天正文，也不执行 Cleaner。

格式契约见仓库根目录的 `docs/IMPORT_FORMAT.md`；专项测试命令为：

```powershell
pytest tests/parsers
```

默认数据库地址为 `sqlite:///./data/echomind.db`。应用启动不会自动迁移；在 `backend/` 中先创建 `data` 目录，再运行 `alembic upgrade head`。pytest 数据库测试全部使用各自的临时 SQLite 文件。

当前仍不包含 CRUD API、文件上传、导入任务、Cleaner、状态传播或模型调用。安装、启动和完整检查命令见仓库根目录的 `README.md`。
