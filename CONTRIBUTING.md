# 为 EchoMind 贡献

感谢你帮助改进 EchoMind。项目优先保证数据不丢失、证据可追溯和隐私安全；功能数量和视觉效果不能凌驾于这些原则之上。

## 项目范围

EchoMind 是单用户、本地优先的聊天记录理解与个人认知档案工具。贡献应服务于导入、标准化、清洗、Insight/Evidence、人工审核和 EchoProfile 链路。它不是心理诊断、人格测评或云端多用户产品。

开始前请阅读 `AGENTS.md`、根目录 `README.md` 以及与改动相关的 `docs/` 文档。先建立 Issue 讨论会改变数据模型、隐私边界、Provider 行为或 Profile Schema 的大改动。

## 开发环境

- Python 3.12
- Node.js 20.19 或更高版本；推荐 Node 24
- Git
- Playwright Chromium（仅 E2E 需要）

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
New-Item -ItemType Directory -Force data | Out-Null
alembic upgrade head
```

macOS/Linux 使用 `source .venv/bin/activate`，其余命令相同。

### 前端

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

## 数据库迁移规则

- 六条已发布的历史迁移不可修改、重命名或重排。
- 数据模型变化必须创建新的 Alembic revision，并同步数据模型和架构文档。
- 新迁移必须在隔离的临时数据库执行 `upgrade head → downgrade base → upgrade head`，并运行 `tests/test_migrations.py`。
- 不得让迁移测试读取或删除开发数据库，也不得引入无提示级联删除。

## 测试和代码风格

后端改动至少运行相关测试，并在提交前运行：

```powershell
cd backend
pytest
ruff check src tests migrations
ruff format --check src tests migrations
mypy src tests
```

前端改动至少运行：

```powershell
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```

影响用户闭环时还要运行 `npm run test:e2e` 和 `npm run test:e2e:mvp`。测试不得访问真实模型 API 或其他外部网络。

## 数据、Evidence 与审核原则

- 所有消息必须保留 `raw_content`，清洗只能生成或更新派生的 `normalized_content`。
- 重要 Insight 必须绑定 Evidence；AI 候选默认只能是 `proposed`。
- `status` 与 `confidence` 是独立概念，低分不能自动驳回，高分不能绕过人工审核。
- 不得绕过用户确认把模型判断作为确定事实或直接纳入正式 Profile。
- Evidence 失效必须传播到 Insight/Profile；不得通过删除引用或清空关系隐藏断链。
- 新算法和规则必须可解释、可测试并版本化。

## 隐私要求

- 测试和截图只能使用人工合成数据。
- 禁止提交真实聊天、真实数据库、真实 Profile、API Key、访问令牌、`.env` 或本机绝对路径。
- 禁止在日志、测试快照、错误、截图或崩溃报告中放入聊天正文、Evidence excerpt、Prompt 或模型响应。
- 远程网络行为必须显式、受控、有测试，并说明发送内容；默认 Mock 路径必须保持离线。
- Pull Request 截图必须只包含合成数据。

## Pull Request

请保持改动范围小而明确，并填写 PR 模板。PR 描述应说明：问题、实现边界、测试命令与结果、迁移生命周期、隐私/网络影响、Evidence/Confidence/Profile 影响、文档变化和已知限制。不要把无关重构混入功能修复。

建议使用简洁的祈使式提交信息，例如 `document provider privacy boundary`。项目没有启用 DCO，也没有单独的 CLA。

## 贡献许可

提交贡献即表示你有权提交相关内容，并同意该贡献按照本项目的 Apache License 2.0 进行许可。详情见 `LICENSE` 和 `NOTICE`。
