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

当前已完成 **阶段 4：可组合的数据清洗 Pipeline**。仓库包含可运行、可测试的 FastAPI/React 基础工程、阶段 2 的核心数据库与迁移、阶段 3 的数据库无关 Parser，以及同样独立于 ORM/HTTP/模型的内存清洗模块。当前仍没有文件上传、清洗结果入库、CRUD、模型调用或 Profile 生成业务。历史 `mind-map` 星图原型不属于 EchoMind 正式架构。

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

## 本地清洗 Canonical 结果

阶段 4 的 `clean_chat` 只接受 `ParsedChatFile`，每次从每条消息的 `raw_content` 创建新的 `CleanedChatFile`，不会读取上一次派生的 `normalized_content`，也不会修改 Parser 输入：

```python
from pathlib import Path

from echomind.cleaning import CleaningOptions, clean_chat
from echomind.parsers import ParserOptions, create_default_registry

parsed = create_default_registry().parse(
    Path("../samples/synthetic/generic-chat.json"),
    options=ParserOptions(),
)
cleaned = clean_chat(parsed, CleaningOptions())
print(cleaned.statistics)
```

固定 Pipeline 顺序为：保守空白规范化 → 附件占位 → 系统消息分类 → 撤回分类 → 精确重复标记 → URL 替换 → 可选脱敏 → 排除策略 → AnalysisUnit。随后执行引用、消息数和统计一致性验证。重复检测先于 URL 和脱敏，避免不同原文在占位后被误判为重复。

默认开关：

| 功能 | 默认值 | 说明 |
|---|---:|---|
| 换行、保守空白规范化 | 开 | CRLF/CR 转 LF、移除行尾和整体边界空白，最多保留 2 个连续空行；不做 Unicode 兼容规范化 |
| 空附件占位 | 开 | image/file/audio/video/other 分别使用固定占位符；已有说明不覆盖，system 不处理 |
| 系统/撤回分类 | 开 | 只使用消息类型、显式布尔 metadata、`[SYSTEM]` 和严格完整匹配的中英文撤回占位规则 |
| 精确重复检测 | 开 | 同会话、发送者、类型、空白处理后正文、时间和 reply 目标完全一致；只标记后续消息 |
| HTTP(S) URL 替换 | 开 | 使用 `[URL]`；不请求网络、不识别普通域名 |
| 敏感信息脱敏 | **关** | 调用方显式启用后可处理 email、明确国际格式 phone_like、IPv4 和受限简单自定义规则 |
| 系统/撤回/重复排除 | 开 | 排除只设置原因，不删除消息、raw 或 reply 引用 |
| AnalysisUnit | 开 | 同会话/发送者、相邻、未排除 text 按时间、数量和字符上限分组；不是新 Message |

默认 AnalysisUnit 阈值为 120 秒、8 条消息和 2000 字符。出现发送者变化、非文本/已排除消息、`source_order` 不连续、超限或新的 `reply_to_source_message_id` 时开启新单元；回复后的普通连续消息可继续加入该新单元。ID 由 Pipeline 版本、会话 ID 和有序原消息 ID 使用 SHA-256 确定性派生。

脱敏不是完整 PII 检测，可能误报或漏报；`phone_like` 只识别带 `+` 的明确国际形式，自定义正则限制为最多 10 条、每条最多 200 字符、无分组/回溯引用/无界重复/零长度匹配且有限量词上限为 100。脱敏只修改 `normalized_content`，`raw_content` 永不修改；操作记录和统计只保存规则名、类别、计数和标记，不保存 URL 或被替换原值。

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

阶段 3 Parser 仅在调用方明确提供本地路径时读取文件，不扫描目录、不上传、不访问网络、不写日志正文，也不写数据库。阶段 4 Cleaner 只处理调用方传入的内存对象，不访问网络或附件路径，不创建缓存数据库，也不记录正文。错误只含安全文件名和结构位置，不含完整路径、聊天正文、URL 或脱敏原值。真实聊天文件、数据库、生成档案和 `.env` 均被 Git 忽略。SQLite 默认并不提供应用级静态加密，这是 MVP 必须明确展示的限制；敏感数据应保存在受保护的设备和账户下。

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

阶段 4 已实现独立 Cleaning Schema、固定可配置 Cleaner Pipeline、保守空白/附件/分类/精确重复/URL/可选脱敏/非破坏性排除、确定性 AnalysisUnit、操作追溯、安全错误和可重算统计。真实 WeFlow 仍未支持。目前没有实现文件上传、数据库写入或清洗结果入库、导入任务、CRUD/删除 API、状态传播服务、Provider、Insight 抽取、置信度算法、EchoProfile 生成、账户权限、Docker、CI 或复杂界面。路线文档中的后续“计划”“目标”和“MVP 验收标准”不代表这些功能已经实现。
