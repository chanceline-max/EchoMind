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

当前已完成 **阶段 7：候选 Insight 抽取、Evidence 绑定与幂等持久化**。阶段 5 的本地导入闭环和阶段 6 Provider 边界保持不变；后端现在可以对调用方明确选择的会话构造有限、匿名化上下文窗口，经统一 Provider 生成严格候选，执行七种 Insight 的最低机械约束，在本地从 `normalized_content` 构造 Evidence，并按精确指纹逐窗口事务提交。默认 Mock 返回空候选且不访问网络。当前仍没有分析 HTTP API、前端 Insight 页面、最终置信度算法或 Profile 生成。

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

`downgrade base` 会删除全部当前表，只用于空的开发/测试数据库。不要对包含需要保留数据的数据库执行该命令。测试使用 pytest 提供的独立临时 SQLite 文件，不读取或污染默认开发数据库。

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

首次使用必须先执行 `alembic upgrade head`，再启动后端。浏览器打开 `/import` 可导入文件；原上传文件只存在于请求级临时目录，成功或失败后都会清理，数据库保留哈希、处理版本、原始消息正文和派生正文。

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

## 结构化 LLM Provider（阶段 6）

Provider 层只接受调用方显式构造的 `LLMRequest` 和 Pydantic 响应模型，不读取数据库、上传原文件或聊天仓库。同步入口为：

```python
from pydantic import BaseModel, ConfigDict

from echomind.core.config import get_settings
from echomind.providers import LLMContent, LLMRequest, create_provider


class SyntheticResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str


provider = create_provider(get_settings())  # 默认 Mock，不访问网络
result = provider.generate_structured(
    LLMRequest(
        system_instruction="Return a synthetic JSON object.",
        user_content=[LLMContent(content="Synthetic input only.")],
        response_schema_name="SyntheticResult",
        provider_name="mock",
        model_name="synthetic-model",
        max_output_tokens=128,
        timeout_seconds=10.0,
    ),
    SyntheticResult,
)
```

Mock 输出由显式 fixture/scenario 配置，完全确定且不读取 API Key。OpenAI-compatible 适配器采用 Chat Completions 风格的非流式 POST，服务端 Settings 决定 endpoint、model 和 Key；只有 `LLM_REMOTE_ENABLED=true` 与当前请求 `remote_consent=true` 同时满足才进入 Transport，不满足时在网络前拒绝。它不自动回退到其他 Provider。

结构化输出必须是纯 JSON；Markdown code fence、附加说明、缺失/额外字段和类型不符都会失败。字符预算是确定性的安全上限，不等于精确 token 计数。408、429、500、502、503、504、超时和临时连接错误可按 0.1/0.2 秒的无抖动退避有限重试；其他 4xx、授权、预算、响应超限和 Schema 错误不重试。响应在本地 JSON 解析前按解压后的字节数检查，默认上限 1 MiB。

Endpoint 默认必须使用 HTTPS；HTTP 只在 `LLM_ALLOW_INSECURE_LOCAL_HTTP=true` 时允许 localhost、127.0.0.1 或 ::1。禁止相对 URL、非 HTTP(S)、URL 用户名/密码和 fragment，并完全拒绝重定向。该基础控制不解决 HTTPS 主机的 DNS 重绑定，部署前仍需网络层审查。Local Provider 当前 `available=False`，不会下载模型、扫描端口或启动进程。

## 候选 Insight 抽取（阶段 7）

阶段 7 仅提供后端内部同步入口 `echomind.extraction.extract_candidates`，不新增 HTTP 路由。`ExtractionRequest` 必须显式给出 1–100 个会话 UUID；会话按去重后的请求顺序处理，可选 `start_at/end_at` 必须带时区。默认 Provider 为 `mock`，`remote_consent=false`，抽取版本固定为 `candidate-extraction-1.0`。窗口默认最多 40 条/12000 字符，单条最多发送 4000 字符，最多重叠 4 条，每窗最多 10 个候选；重叠必须小于窗口消息上限。`stop_on_window_error=true` 时当前窗失败即停止后续窗口，但已成功提交的窗口不会回滚；设为 false 时记录安全错误并继续。

只有未归档且恰好有一个 Profile Owner 的显式所选会话可分析。读取顺序是请求中的会话顺序，再按 `Message.source_order`、`Message.id`；只选择时间范围内、`excluded_from_analysis=false`、未归档、未删除且时间有效的消息。上下文绝不读取 `raw_content`，也不发送数据库/源消息 ID、参与者姓名、文件名、路径、metadata 或 cleaning operations。每窗只含一个会话，消息使用 `m001...` 局部别名，参与者使用 `PROFILE_OWNER`、`OTHER_n`；回复目标仅在同窗时使用局部别名。

单条超限消息仅在 Provider 上下文中采用确定性前缀截断，并在上限内附加 `[TRUNCATED]`；数据库正文不变，标记计入字符预算。固定 Prompt 版本与抽取版本相同，禁止诊断、MBTI、单消息 pattern、窗外 Evidence 和 confirmed 结论。候选只能使用受控类别和 fact/preference/pattern/inference/hypothesis/contradiction/change 七类，模型只返回局部 Evidence 引用，不能提供 excerpt。最低规则包括：所有候选至少引用一条 Owner 消息；fact 要求 Owner supporting 自述；非自述 preference 至少两条 Owner 消息；pattern 至少两条消息和两个时间点；inference/hypothesis 要求推理依据及其他解释；contradiction 同时保留 supporting/contradicting；change 至少两个时间点和完整有效范围。这些是可测试机械下限，不是心理学真实性证明。

Evidence excerpt 由本地完整 `normalized_content` 确定性生成，最多 500 字符并使用同一截断标记；role 映射为本地 evidence type/stance。Evidence 指纹包含消息 ID、类型、excerpt SHA-256 和版本，Insight 指纹包含抽取版本、类型、类别、仅裁边/折叠空白后的 statement 以及有效期。重复运行复用 Insight、Evidence 和关联，不覆盖用户编辑的标题/statement，也不重置 confirmed/rejected/superseded。新候选固定 `status=proposed`、`evidence_state=valid`、`confidence=0.0`、`confidence_version=unscored`；这里的 0.0 表示阶段 8 尚未评分，模型自评单独保存在 `model_confidence`。

Provider 调用发生在数据库事务外；每窗合法候选在一个短事务中整体提交或回滚，每窗最多一次成功提交。`ExtractionReport` 只返回 ID、计数、状态和受控错误，不含正文、excerpt、Prompt 或模型响应。远程 Provider 经服务端开关与逐请求 consent 后会收到当前窗口的 `normalized_content`；EchoMind 不缓存或持久化完整 Prompt/Provider 输出，第三方保留政策仍需用户自行核对。

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
| `IMPORT_MAX_FILE_BYTES` | `26214400` | 单次上传原始字节上限 |
| `IMPORT_MAX_CONVERSATIONS` | `500` | 单文件会话上限 |
| `IMPORT_MAX_PARTICIPANTS` | `10000` | 单文件参与者上限 |
| `IMPORT_MAX_MESSAGES` | `50000` | 单文件消息上限 |
| `IMPORT_MAX_MESSAGE_CHARACTERS` | `100000` | 单条正文字符上限 |
| `IMPORT_MAX_METADATA_BYTES` | `65536` | 单个 metadata JSON 编码字节上限 |
| `LLM_PROVIDER` | `mock` | `mock`、`openai_compatible` 或 `local`；默认离线 |
| `LLM_REMOTE_ENABLED` | `false` | 服务端远程调用总开关；仍需逐请求 consent |
| `LLM_OPENAI_COMPATIBLE_ENDPOINT` | 未设置 | 服务端 OpenAI-compatible 完整 HTTPS endpoint |
| `LLM_OPENAI_COMPATIBLE_API_KEY` | 未设置 | 服务端 SecretStr；真实值只放私有 `.env` |
| `LLM_OPENAI_COMPATIBLE_MODEL` | 未设置 | 服务端选择的模型名 |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `30` | 单次调用配置上限（秒） |
| `LLM_CONNECT_TIMEOUT_SECONDS` | `5` | 连接阶段超时（秒） |
| `LLM_READ_TIMEOUT_SECONDS` | `30` | 读取阶段超时（秒） |
| `LLM_MAX_RETRIES` | `2` | 临时错误最大重试次数，范围 0–5 |
| `LLM_VERIFY_TLS` | `true` | HTTPS TLS 验证；只允许 localhost 显式关闭 |
| `LLM_ALLOW_INSECURE_LOCAL_HTTP` | `false` | 是否允许 localhost HTTP endpoint |
| `LLM_MAX_INPUT_CHARACTERS` | `100000` | system 与 user 内容总字符安全上限 |
| `LLM_MAX_MESSAGES` | `100` | 单请求 user 消息数量上限 |
| `LLM_MAX_MESSAGE_CHARACTERS` | `20000` | 单条 user 内容字符上限 |
| `LLM_MAX_SCHEMA_CHARACTERS` | `50000` | 响应 JSON Schema 序列化字符上限 |
| `LLM_MAX_OUTPUT_TOKENS` | `4096` | 调用方可请求的输出 token 上限 |
| `LLM_MAX_RESPONSE_BYTES` | `1048576` | 解压后远程响应正文上限 |

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

阶段 5 只在用户显式选择文件后上传到本机 API；服务端使用随机临时名、分块读取与哈希，完成或失败后删除临时副本，不自动扫描或长期保留原上传文件。数据库保留不可变 `raw_content` 和可重建的 `normalized_content`。阶段 7 默认 Mock 且完全离线；远程适配器需要服务端开关和逐请求 consent，只发送当前有限窗口的匿名化 `normalized_content` 和安全结构字段，并禁止记录或持久化完整 prompt、响应正文、Key、Authorization 或 endpoint。敏感响应使用 `no-store`，写请求检查精确 Origin，前端不使用浏览器持久化存储或 Service Worker。SQLite 默认不提供应用级静态加密。

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

阶段 7 已实现内部候选抽取、有限窗口、Owner 约束、本地 Evidence、精确指纹和窗口级恢复；阶段 5 导入与前端闭环、阶段 6 Provider 回归保持可用。真实 WeFlow 仍未支持；当前也没有分析/Provider API、模型设置或 Insight 页面、最终置信度算法、跨窗口语义合并、EchoProfile、账户权限、Docker 或 CI。
