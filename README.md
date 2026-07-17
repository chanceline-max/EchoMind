# EchoMind

> Turn conversations into understanding.

EchoMind 是一个隐私优先、证据优先的本地工具，目标是把长期聊天记录转化为结构化、可追溯、可修订并可持续演化的个人认知档案 `EchoProfile`。

## EchoMind 是什么

- 聊天记录导入、解析、标准化和清洗工具。
- 从有限上下文窗口中提取候选事实、偏好、模式、推断、假设、矛盾和变化的分析系统。
- 让每条重要判断都能回到证据和原始消息的审阅工具。
- 由用户确认、修改、驳回和排除内容的人机协作系统。

## EchoMind 不是什么

- 不是聊天机器人。
- 不是 MBTI 或人格标签生成器。
- 不是医疗、心理诊断或治疗工具。
- 不把模型输出视为事实或不可修改的真相。
- MVP 不包含云账号、移动 App、付费、复杂知识图谱或生产级云部署。

## 当前阶段

当前已完成 **阶段 3：通用聊天记录 Parser 系统**。仓库包含可运行、可测试的 FastAPI/React 基础工程、阶段 2 的核心数据库与迁移，以及与 ORM 解耦的 JSON、CSV、固定纯文本 Parser。Parser 只在内存中生成 Canonical Chat Schema，不写数据库；当前仍没有文件上传、Cleaner、CRUD、模型调用或 Profile 生成业务。历史 `mind-map` 星图原型不属于 EchoMind 正式架构。

## 前置环境

- Python 3.12
- Node.js 当前 LTS（最低支持 20.19）

## 后端安装与启动

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
fastapi dev src/echomind/main.py
```

后端默认运行于 `http://127.0.0.1:8000`，健康检查为：

```text
GET http://127.0.0.1:8000/api/v1/health
```

## 数据库初始化与迁移

数据库默认位于 `backend/data/echomind.db`，该目录和数据库文件均被 Git 忽略。应用导入或启动不会自动建表；首次本地使用时显式运行迁移：

```powershell
cd backend
New-Item -ItemType Directory -Force data | Out-Null
alembic upgrade head
```

查看版本、回滚到迁移前和重新升级：

```powershell
alembic current
alembic downgrade base
alembic upgrade head
```

`downgrade base` 会删除阶段 2 的表，只用于空的开发/测试数据库。不要对包含需要保留数据的数据库执行该命令。测试使用 pytest 提供的独立临时 SQLite 文件，不读取或污染默认开发数据库。

迁移回归不要在 `backend/data/` 创建固定测试数据库。使用现有 pytest 用例，它通过 `tmp_path` 创建隔离数据库，并依次执行 upgrade、downgrade、upgrade 和 metadata drift 检查；测试结束后临时目录自动清理：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_migrations.py -q
```

## 前端安装与启动

另开一个终端：

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

前端默认运行于 `http://127.0.0.1:5173`。

## 本地解析合成聊天文件

当前三种通用格式及完整字段定义见 [导入格式规范](docs/IMPORT_FORMAT.md)。最小 Python 调用如下：

```python
from pathlib import Path

from echomind.parsers import ParserOptions, create_default_registry

result = create_default_registry().parse(
    Path("../samples/synthetic/generic-chat.json"),
    options=ParserOptions(),
)
print(result.statistics)
```

Registry 根据扩展名和轻量内容签名确定性选择 Parser；也可显式传入 `parser_name`。默认 strict 模式遇到坏记录立即失败，lenient 模式仅跳过可恢复的单条坏记录。两种模式都不会吞掉整体结构错误或空结果。

## 测试与静态检查

后端：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
ruff check src tests migrations
ruff format --check src tests migrations
mypy src tests
```

前端：

```powershell
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```

Playwright 首次运行前安装 Chromium。端到端配置会自动启动并关闭本地前后端；需要先完成后端虚拟环境和前端依赖安装。

```powershell
cd frontend
npx playwright install chromium
npm run test:e2e
```

测试不访问外部服务，也不需要 API Key。

## 环境变量

后端从 `backend/.env` 读取配置：

| 变量 | 默认示例 | 用途 |
|---|---|---|
| `APP_NAME` | `EchoMind API` | FastAPI 应用名称 |
| `APP_VERSION` | `0.1.0` | API 和健康响应版本 |
| `API_V1_PREFIX` | `/api/v1` | v1 API 前缀 |
| `ENVIRONMENT` | `development` | 当前运行环境标识 |
| `FRONTEND_ORIGINS` | localhost/127.0.0.1 JSON 数组 | 精确 CORS 允许列表；禁止通配符 |
| `DATABASE_URL` | `sqlite:///./data/echomind.db` | SQLAlchemy/Alembic 数据库地址；不得写入用户绝对路径 |

前端从 `frontend/.env` 读取：

| 变量 | 默认示例 | 用途 |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | 后端基础地址 |

两个 `.env.example` 可以提交；真实 `.env` 已被 Git 忽略。不要在 `VITE_*` 变量中保存密钥，因为它们会进入浏览器构建产物。

## 推荐目录

```text
EchoMind/
├── backend/                 # FastAPI、领域逻辑、数据库、导入与抽取
│   ├── src/echomind/
│   └── tests/
├── frontend/                # React + TypeScript 用户界面
│   ├── src/
│   └── tests/
├── docs/                    # 产品、架构、隐私和格式规范
├── samples/                 # 仅允许脱敏或合成样本
├── scripts/                 # 开发与验证脚本
└── tests/                   # 后续跨端契约测试
```

详细结构见 [架构文档](docs/ARCHITECTURE.md)。

## 隐私说明

阶段 3 Parser 仅在调用方明确提供本地路径时读取文件，不扫描目录、不上传、不访问网络、不写日志正文，也不写数据库。错误只含安全文件名和结构位置，不含完整路径或聊天正文。真实聊天文件、数据库、生成档案和 `.env` 均被 Git 忽略。SQLite 默认并不提供应用级静态加密，这是 MVP 必须明确展示的限制；敏感数据应保存在受保护的设备和账户下。

完整边界见 [隐私设计](docs/PRIVACY.md)。

## 文档索引

- [产品规格](docs/PRODUCT_SPEC.md)
- [系统架构](docs/ARCHITECTURE.md)
- [数据模型](docs/DATA_MODEL.md)
- [隐私设计](docs/PRIVACY.md)
- [开发路线](docs/ROADMAP.md)
- [架构决策](docs/DECISIONS.md)
- [导入格式](docs/IMPORT_FORMAT.md)
- [档案结构](docs/PROFILE_SCHEMA.md)

## 项目状态声明

阶段 3 已实现独立 Canonical Schema、确定性 Registry、通用 JSON/CSV/固定纯文本解析、原始字节 SHA-256、统一验证、统计和安全错误。真实 WeFlow 仍未支持。目前没有实现文件上传、数据库写入、Cleaner、导入任务、CRUD/删除 API、状态传播服务、Provider、Insight 抽取、置信度算法、EchoProfile 生成、账户权限、Docker、CI 或复杂界面。路线文档中的后续“计划”“目标”和“MVP 验收标准”不代表这些功能已经实现。
