# EchoMind backend

阶段 2 的 FastAPI 与数据库基础工程。当前包含 `/api/v1/health`、八个核心 SQLAlchemy 模型、独立 Pydantic Schema、同步 SQLite Session 工厂和 Alembic 初始迁移，但不包含 CRUD API、导入、解析、状态传播或模型调用。

默认数据库地址为 `sqlite:///./data/echomind.db`。应用启动不会自动迁移；在 `backend/` 中先创建 `data` 目录，再运行 `alembic upgrade head`。pytest 数据库测试全部使用各自的临时 SQLite 文件。

安装、启动和检查命令见仓库根目录的 `README.md`。
