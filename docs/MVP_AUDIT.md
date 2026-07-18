# EchoMind MVP 验收审计

## 1. 执行摘要

- 审计基线提交：`ead6bf6`（阶段 10）；阶段 11 完整验收后，阶段 12 仅同步许可证与发布准备状态。
- 审计日期：2026-07-18（Asia/Shanghai）。
- 审计环境：Windows 11 家庭中文版；Python 3.12.13；Node.js 24.14.0；npm 11.9.0；Git 2.53.0.windows.3；FastAPI 0.139.2；SQLAlchemy 2.0.51；Pydantic 2.13.4。
- 最终结论：**PASS_WITH_LIMITATIONS**。剩余限制是同步分析、平台覆盖、远程互操作、静态加密和完整无障碍/安全审计，不再包含许可证未决。
- 用户可达核心闭环：满足。新的空库 E2E 不预置 Insight、Confidence、Revision 或 Profile，只注入明确的离线 Mock Provider 候选。
- 未解决 BLOCKER：0；未解决 HIGH：0。
- OWNER_DECISION_REQUIRED：0；Apache-2.0 与 `Copyright 2026 杨锦辰` 已由项目所有者确认。

结论不是生产可用声明。Windows 本地开发者 MVP 已被实际验证；Linux、macOS、真实远程 Provider、真实敏感聊天数据治理和生产部署未被本轮证明。

## 2. MVP 范围

已包含：JSON/CSV/Text 导入、无损 Parser、可组合 Cleaner、SQLite 证据链、离线 Mock/受控 OpenAI-compatible Provider、候选 Insight、Evidence、机械置信度、人工审核与 Revision、消息排除传播、confirmed-only EchoProfile、Markdown/JSON 导出、动态 stale，以及用户可达的同步分析入口。

明确不包含：真实 WeFlow 映射、本地模型运行时、后台任务、队列、流式进度、跨窗口语义合并、用户自定义评分、Profile 编辑/删除、账号权限、云同步、移动 App、PDF/Word、Docker、CI 和生产部署。

阶段 11 只修复核心闭环 BLOCKER，增加审计测试、负载脚本和文档；没有进入阶段 12，没有新增模型类型、评分算法、数据库模型或迁移。

## 3. 系统组件清单

| 组件 | 状态 | 核心边界 |
|---|---|---|
| Parser | 已实现 | Generic JSON/CSV/Text；strict/lenient；WeFlow `available=False` |
| Cleaning | 已实现 | 独立、可组合、幂等；不覆盖 `raw_content` |
| Import | 已实现 | 同步上传、临时文件、全事务入库、重复哈希保护 |
| Provider | 已实现 | 默认 Mock；远程双重授权；Local unavailable |
| Extraction | 已实现 | 明确会话、有限窗口、Evidence 本地绑定、窗口事务 |
| Confidence | 已实现 | `confidence-1.0`、content-free 特征、单 Insight 事务 |
| Review | 已实现 | 乐观并发、追加 Revision、confirm/reject/restore/supersede |
| Profile | 已实现 | confirmed-only、单一文档、确定性双渲染、不可变快照 |
| Frontend | 已实现 | 导入、会话、分析、审核、Profile；查询仅内存 |
| 数据库迁移 | 已实现 | 六条 Alembic revision；upgrade/downgrade/upgrade 已验证 |

## 4. 用户可达功能矩阵

| # | 用户操作 | API | UI | 自动化证据 | 结果 |
|---:|---|---|---|---|---|
| 1 | 导入 JSON | `POST /api/v1/imports` | `/import` | Stage 5/11 E2E | PASS |
| 2 | 导入 CSV | 同上 | 同上 | `test_csv_import` 参数化 API 测试 | PASS |
| 3 | 导入 TXT | 同上 | 同上 | `test_text_import` 参数化 API 测试 | PASS |
| 4 | 重复导入提示 | 同上 | 导入错误状态 | Stage 5/11 E2E | PASS |
| 5 | Parser strict/lenient | 导入表单字段 | `/import` | Parser 68+ 场景与 Import API | PASS |
| 6 | Cleaning | 导入选项 | `/import` | Cleaning 专项测试 | PASS |
| 7 | 查看会话 | Conversation GET | `/conversations` | Stage 5/11 E2E | PASS |
| 8 | 查看 raw/normalized | Messages GET | 会话详情 | Stage 5/11 E2E | PASS |
| 9 | 排除/恢复消息 | Message PATCH | MessageCard | Stage 5/9/11 E2E | PASS |
| 10 | 触发 Insight 抽取 | `POST /analysis` | `/analysis` | Stage 11 E2E、Analysis API 测试 | PASS |
| 11 | 触发 Confidence | 由 `POST /analysis` 对本次 ID 调用 | `/analysis` 统计 | Stage 11 E2E/API | PASS |
| 12 | 查看 Insight | Insight GET | `/insights` | Stage 9/11 E2E | PASS |
| 13 | Evidence 追溯 | Insight detail | 证据卡 | Stage 11 E2E、追溯审计测试 | PASS |
| 14 | 编辑 Insight | Insight PATCH | Insight editor | Stage 9/11 E2E | PASS |
| 15 | confirm/reject/restore/supersede | 显式 POST | 审核动作 | Review API/服务测试 | PASS |
| 16 | Revision 历史 | Revisions GET | 时间线 | Stage 9/11 E2E | PASS |
| 17 | 生成 Profile | `POST /profiles` | `/profiles` | Stage 10/11 E2E | PASS |
| 18 | 查看 stale Profile | Profile GET | Profile detail | Stage 10/11 E2E | PASS |
| 19 | 导出 Markdown | Profile markdown GET | 显式按钮 | Stage 10/11 E2E | PASS |
| 20 | 导出 JSON | Profile JSON GET | 显式按钮 | Stage 10/11 E2E | PASS |
| 21 | Profile Evidence 跳原消息 | Message location/GET | 本地链接 | Stage 10/11 E2E | PASS |

## 5. A01–A15 验收矩阵

| ID | 原始要求摘要 | 实现位置 | 自动化/手动证据 | 结果 | 发现 |
|---|---|---|---|---|---|
| MVP-A01 | 干净安装、健康、前端状态、构建 | README、health、HomePage | 干净副本；Health/Vitest/Playwright/build | PASS | — |
| MVP-A02 | 无 Key、断外网的合成完整闭环 | 默认 Mock、Stage 11 配置 | 空库 Stage 11 E2E 监听非 localhost 请求 | PASS | BLOCKER-001 已修复 |
| MVP-A03 | JSON/CSV/Text Parser 契约 | `parsers/` | Parser 专项测试，正常/异常/大文件 | PASS | — |
| MVP-A04 | WeFlow 不支持且不写库 | WeFlow Parser/Registry | WeFlow 测试、范围扫描 | PASS | — |
| MVP-A05 | 重复导入不增长计数 | Import hash 唯一性 | Import API、Stage 5/11 E2E | PASS | — |
| MVP-A06 | Cleaner 开关、幂等、raw/hash 不变、统计无正文 | `cleaning/` | Cleaning 专项与隐私测试 | PASS | — |
| MVP-A07 | Insight 七类机械边界 | candidate validation | Extraction schema/semantic tests | PASS | — |
| MVP-A08 | AI 候选 proposed、Evidence/窗口规则 | Extraction | Extraction 专项、Analysis API | PASS | — |
| MVP-A09 | 审核/排除传播且无无效导出 | Review/Profile | Review tests、Stage 9/10/11 E2E | PASS | — |
| MVP-A10 | Markdown/JSON 等价且稳定 | Profiling renderers | Profile contract/core tests | PASS | — |
| MVP-A11 | Profile→Insight→Evidence→Message→SourceFile | Profile document/relations | `test_profile_insight_traces...`、Stage 11 E2E | PASS | — |
| MVP-A12 | 无物理删/级联、raw 保留、状态传播 | RESTRICT FK/服务 | deletion constraints、propagation、route contract | PASS | — |
| MVP-A13 | 上传/CORS/缓存/远程 opt-in 隐私 | middleware/settings/UI | Import/provider/analysis tests、源码扫描、E2E | PASS | — |
| MVP-A14 | 全测试、静态、构建、E2E、迁移 | 工程配置 | 阶段 12 当前工作区 663 pytest、38 Vitest、5 Playwright、Ruff/mypy/ESLint/TS/build、迁移循环 | PASS | — |
| MVP-A15 | 无密钥/真实聊天/DB/路径/产物 | `.gitignore`/合成 samples | Git 跟踪文件与 `rg` 扫描 | PASS | — |

## 6. 完整闭环证据

- 文件：`frontend/tests/e2e/stage-eleven.spec.ts`
- 测试：`completes the user-reachable MVP loop from an empty database`
- 启动：`playwright.stage11.config.ts` 删除临时 DB、迁移到 head、启动正式 FastAPI/Vite；唯一测试特例是应用工厂注入固定离线 Mock 候选。
- 关键步骤：打开首页；导入合成 JSON；查看 raw/normalized；选择 Conversation；从 `/analysis` 抽取并评分；查看 Evidence、原消息与 confidence；编辑、确认、Revision；生成/查看/导出 Profile；排除 Evidence 消息并验证 invalid/confidence/stale；生成失效 Profile；恢复消息与 Evidence；再次生成；重复导入安全失败；重复 Profile 复用。
- 结果：PASS，约 3.1 秒测试体（本机单次）；数据库、下载元数据、`test-results` 和报告目录由 runner 清理。
- 网络/浏览器断言：非 localhost 请求为 0；localStorage/sessionStorage/IndexedDB/Service Worker/Cache Storage 均为 0；trace/screenshot/video 均关闭。

## 7. 数据追溯证据

`backend/tests/audit/test_profile_traceability.py` 从实际生成的 `ProfileInsightItem` 逐项验证：I 引用的 Insight 存在且 revision 一致；每个 E 引用对应 Evidence；`InsightEvidence` 关系存在；Evidence 指向 Message；Message 指向正确 Conversation；Conversation 指向带 64 位文件哈希的 SourceFile。既有 Profile 测试另外验证 excerpt 来自 normalized 内容、source manifest、document hash、raw 不进入 Profile；Stage 11 E2E 验证 Evidence 链接定位并高亮原消息。

结果：PASS。没有通过删除或补空引用“修复”断链；外键为 RESTRICT，失效通过状态表达。

## 8. 隐私与网络审计

- 默认：`LLM_PROVIDER=mock`、`LLM_REMOTE_ENABLED=false`。Mock Factory 创建不探网，即使环境存在 Key 也忽略；测试见 Provider config/factory tests。
- Profile、Confidence、Review 不导入或调用 Provider；Extraction 只在明确分析时调用 Provider。
- Stage 11 浏览器监听只观察 localhost:5173/8000，外部请求 0；没有修改防火墙、代理或系统策略。
- 浏览器源码扫描：`frontend/src` 中 localStorage、sessionStorage、IndexedDB、Service Worker、Cache API 命中 0；无 query persistence、`dangerouslySetInnerHTML` 或正文 console 输出。
- 敏感 API/导出使用 `Cache-Control: no-store`；导出只由按钮触发。Playwright 不保留包含 Evidence 的截图、trace 或 video。
- 上传临时目录使用 `TemporaryDirectory`；成功与已测试失败路径均清理。模型请求不缓存。
- 远程模式明确说明发送所选窗口的 `normalized_content`，同时要求服务端 enable 和逐请求 consent；未验证真实远程供应商的数据保留政策。

## 9. 数据完整性与事务

| 失败 | 事务边界/失败注入 | 自动化证据 | 结果 |
|---|---|---|---|
| 上传超限 | 读取前/流式临时文件；降低测试上限 | `test_upload_limit_cleans_temporary_directory` | PASS，0 入库/临时残留 |
| Parser 失败 | 入库事务前 | `test_invalid_uploads_are_safe_and_do_not_persist` | PASS |
| Cleaner 失败 | 入库事务前，返回无部分结果 | `test_unexpected_cleaner_error_is_safe_and_returns_no_partial_result` | PASS |
| Import DB 中途失败 | 单导入事务，注入 flush/持久化失败 | `test_unexpected_persistence_failure_rolls_back_every_table` | PASS，所有表 0 |
| Extraction Provider 失败 | Provider 在事务外；前窗已提交、当前窗无写 | `test_window_failure_stop_policy_preserves_prior_commits` | PASS |
| Extraction 窗口持久化失败 | 每窗短事务；替换 `persist_window` | `test_extraction_persistence_failure_leaves_no_partial_window` | PASS，I/E/link 均 0 |
| Confidence 持久化失败 | 单 Insight 短事务；注入 SQLAlchemyError | `test_confidence_persistence_failure_retains_unscored_insight` | PASS，保持 unscored |
| Revision 写失败 | claim+Revision 同事务；注入 `_add_revision` 失败 | `test_revision_insert_failure_rolls_back_claimed_revision_and_status` | PASS，revision/status 回滚 |
| 消息排除传播失败 | Message/Evidence/Insight/Revision 同事务 | `test_confidence_failure_rolls_back_message_evidence_and_revision` | PASS |
| Profile JSON/Markdown 渲染失败 | 双渲染完成后才持久化 | `test_renderer_failure_does_not_save_partial_snapshot` 及 renderer tests | PASS，快照 0 |
| Profile 来源变化 | 读取时动态 stale，不回写历史 | `test_staleness_change_matrix` | PASS |
| Profile 唯一约束竞争 | 唯一指纹，冲突后安全重读 | `test_concurrent_unique_conflict_safely_reuses_existing_snapshot` | PASS，快照 1 |

## 10. 确定性与幂等

| 层 | 已验证事实 | 证据 |
|---|---|---|
| Parser | 相同原始字节 SHA-256/Canonical 稳定；validate 幂等 | hashing/validation tests |
| Cleaning | 相同输入配置序列化稳定；不修改 ParsedChatFile/raw | pipeline/cleaner tests |
| Mock | 显式场景、相同输入稳定；无正文关键词规则 | mock/factory tests、实现审查 |
| Extraction | 指纹复用 Insight/Evidence/link，不覆盖用户状态 | `test_repeat_run_is_idempotent...`、Analysis API 二次调用 |
| Confidence | 相同 as_of/输入不 UPDATE；模型自评和 title/statement 不影响 | confidence persistence tests |
| Review | 旧 revision 409，不静默覆盖；Revision 追加式 | review actions/API tests |
| Profile | 同来源/配置复用；JSON/Markdown 稳定；快照不回写；stale 动态 | profile core/service tests、E2E |

## 11. 迁移与升级

六条冻结 revision：`20260716_0001`、`20260717_0002`、`20260718_0003`、`20260719_0004`、`20260720_0005`、`20260721_0006`。

实际空临时数据库执行 upgrade head → downgrade base → upgrade head，全链 PASS，文件随后删除。`tests/test_migrations.py` 还验证重要历史 revision 升 head、代表性旧数据保留、metadata/head 一致；连接启用 SQLite foreign_keys。删除约束测试确认 RESTRICT、无 delete-orphan/`cascade="all, delete"`、ProfileSnapshot 和 InsightRevision ORM 不可更新/删除。Git 跟踪 SQLite 为 0。

## 12. 干净环境复现

使用 `git ls-files` 复制当前已暂存的跟踪文件到 `TemporaryDirectory`，不复制 `.venv`、node_modules、`.env`、数据库、缓存或构建产物。

- 后端：新建 Python 3.12 venv；`pip install -e .[dev]`（约 30 秒工具墙钟，含下载）；应用导入；Alembic upgrade；Health；完整 pytest 658/658、24.57 秒。PASS。
- 前端：Node 24.14.0；`npm ci` 13 秒；Vitest 38/38；ESLint；TypeScript；Vite build。PASS。
- README 启动命令：`fastapi dev src/echomind/main.py` 的 Health 返回 200/版本化 schema；`npm run dev` 首页返回 200。随后以 Ctrl+C 正常 shutdown，8000/5173 listener 均为 0。
- 依赖安装使用包索引；“运行时默认离线”不等于“首次依赖安装无需网络”。
- 未测试：Linux、macOS、Node 20.19–23、Python 3.12 的其他 patch 版本。

## 13. 性能与资源边界

资源上限通过测试 Settings 降低阈值验证：文件、会话、参与者、消息数、单消息字符、Profile Insight/Evidence、Profile JSON/Markdown 字节及 Provider 输入/响应限制均有自动化边界测试。

代表性负载命令：`python scripts/audit_representative_load.py`。人工合成 10 个会话、20 个参与者、5,000 条消息；输入 775,128 bytes。Windows 本机单次结果：Parser 0.493s，Cleaning 0.792s，完整 Import 5.477s，默认空候选 Mock 分析 1.282s/140 窗口/0 失败，SQLite 3,555,328 bytes，`tracemalloc` 峰值 62.67 MiB，数据库消息 5,000。分页行为由 Conversation/Message API 测试验证。

这些数字仅是本机一次审计测量，不是 SLA，也不外推到远程模型或其他硬件。

## 14. API 和安全表面

OpenAPI 自动枚举 24 条 API method/path，9 条写路由。完整列表：

- GET：health；analysis capabilities；imports list/detail；conversations list/detail/messages；message location；insights list/detail/revisions；profiles list/detail/markdown/json。
- PATCH：Insight edit；Message analysis exclusion。
- POST：imports；analysis；Insight confirm/reject/restore/supersede；profiles。

写路由均经过精确 Origin 保护；CORS 无 `*`。敏感成功/受控错误响应为 `no-store`。没有 DELETE、Profile PATCH、Evidence/Revision 编辑、Provider Key、endpoint 或 Prompt API。AnalysisRequest OpenAPI 只含 conversation IDs、remote consent、时间范围和 stop policy；契约测试防止意外扩展。404/409/413/415/422/已处理 500 使用安全结构，不返回 SQL、正文、Key 或路径。

## 15. 前端与可访问性

- 关键上传、筛选、审核、Profile 和分析控件有 label/可读名称；错误使用文字和 `role=alert`，状态不只靠颜色。
- Stage 11 在 390×844 viewport 检查首页无阻断性横向溢出；Tab 可到达可见主要控件。
- 聊天长文本可展开；Insight/Profile 文本使用换行/overflow 规则；无 HTML 注入 API。
- 同步分析只显示“正在分析所选会话。”，没有伪进度。
- 限制：未引入 axe，未完整验证屏幕阅读器、所有 dialog 焦点返回和全部页面的 WCAG；列为 LOW，不阻断本地 MVP。

## 16. 发现列表

### AUDIT-BLOCKER-001（已修复）

- 严重度：BLOCKER。
- 标题：普通用户无法触发 Insight 抽取与 Confidence。
- 证据：审计基线只有内部服务；Stage 9/10 E2E 通过 seed script 预置 Insight。
- 影响：导入→分析→审核→Profile 的核心 MVP 链断裂。
- 处理：新增最小 analysis capabilities/POST API、`/analysis` UI、Provider Factory 测试注入和空库完整 E2E。
- 修复文件：`api/v1/analysis.py`、`services/analysis_service.py`、analysis schemas/frontend/tests。
- 回归：Analysis API/页面单元测试、Stage 11 E2E、完整后端/前端回归。
- 剩余风险：同步大请求可能耗时；没有后台恢复。

### AUDIT-MEDIUM-001（未修复，已接受限制）

- 严重度：MEDIUM。
- 标题：同步分析没有后台恢复或持久任务状态。
- 证据：ADR-025；没有 AnalysisRun/worker。
- 影响：远程或较大会话可能遇到 HTTP 超时，用户需重试；指纹保证重试不无限重复。
- 处理：阶段 11 禁止引入后台任务，保留同步受限入口。
- 剩余风险：远程模型时延未实测。

### AUDIT-LOW-001（未修复）

- 严重度：LOW。
- 标题：可访问性仅做基础自动化检查。
- 影响：复杂辅助技术体验未证实。
- 处理：记录到阶段 12/后续，不引入大型依赖。

### AUDIT-LOW-002（阶段 12 已修复）

- 严重度：LOW。
- 标题：缺少 CONTRIBUTING、SECURITY、CODE_OF_CONDUCT、CHANGELOG 和 GitHub 模板。
- 影响：公开协作流程不完整，但不破坏本地 MVP 数据链。
- 处理：阶段 12 已新增 CONTRIBUTING、SECURITY、CODE_OF_CONDUCT、CHANGELOG、Release 文档和 GitHub 模板。

### AUDIT-OWNER-001（阶段 12 已解决）

- 原问题：仓库没有 LICENSE，复制、修改和分发授权不明确。
- 所有者决定：Apache License 2.0；SPDX `Apache-2.0`；`Copyright 2026 杨锦辰`。
- 处理：根目录 `LICENSE`/`NOTICE`、后端/前端包元数据、README、贡献许可和发布材料已统一；第三方依赖仍适用各自许可证。

## 17. 已修复问题与失败过程

产品修复只有 AUDIT-BLOCKER-001。实现过程中保留以下真实失败记录：

1. 初次 mypy：Settings Provider 字符串不满足 Literal；增加受控 cast 后通过。
2. 初次 Analysis API 专项：3 个测试因测试上传目录未创建失败；显式创建 tmp upload root 后 5/5 通过。
3. 初次前端目标测试命令写了多余 `frontend/` 前缀，Vitest 报 no files；改用相对路径。
4. 前端目标测试随后 3 项失败：未 stub `VITE_API_BASE_URL`，以及 TanStack mutation mock 多一个上下文参数；修复测试环境/断言后 6/6 通过。
5. 首次 Stage 11 E2E：Profiles 链接 strict locator 匹配两个元素；改为 exact 后通过。
6. 首次完整旧 E2E 回归误把 Stage 11 空库测试放进 Stage 10 seed 配置，导致 Stage 11 空候选及 Stage 5 重复导入两项失败；默认配置显式 ignore Stage 11，独立空库配置运行它，复测旧 4/4、Stage 11 1/1。
7. 增加 DOM 类型后旧 Stage 10 E2E 的 `response.json()` 触发 2 个 ESLint unsafe；标注为 `unknown` 后 lint 通过。
8. 代表性负载第一次增强测量引用了不存在的 Cleaning 统计字段，并因异常前 Engine 未释放造成临时 DB 占用；改为 `output_message_count`、释放并安全删除该单一临时目录，复测通过且无残留。
9. 新审计测试初次 Ruff check 有 2 个 import-order 错误；`ruff --fix` 后通过。最终专项测试 10/10 已通过。
10. 干净副本首次 Alembic 命令因未先创建被 Git 忽略的 `backend/data` 目录而失败；README 已明确要求 `New-Item ... data`。按 README 补执行后 upgrade 与 658 个测试通过，不需代码修复。
11. PowerShell 递归删除干净副本的首个命令被执行策略拒绝，未发生删除；改用 Python `pathlib` 验证目标严格位于 TEMP 且名称匹配后，用 `shutil.rmtree` 删除，复核目录不存在。
12. 最终专项复测命令在进入 `backend` 后错误地把回退解释器拼为 `../python`，因此尚未执行测试即失败；改用 `Resolve-Path backend/.venv/Scripts/python.exe` 得到绝对解释器路径，复测专项 10/10、完整后端 659/659、Ruff、格式和 mypy 全部通过。

## 18. 已知限制

- 默认 Mock 合法但返回空候选；它不是基于正文的伪 AI。产生实际候选需要用户明确配置可用 Provider，或测试注入。
- Local Provider `available=False`；真实 WeFlow 未支持。
- 分析同步执行；无任务恢复、后台进度和跨窗口语义合并。
- Confidence 是版本化机械支撑强度，不是科学概率、诊断或人格真值。
- 远程 Provider 会收到所选窗口 normalized 内容；第三方政策不由 EchoMind 控制。
- SQLite/本地文件未做应用层静态加密；主机账号和磁盘安全仍是边界。
- 没有物理删除 UI；证据链优先使用归档、排除和状态。
- 仅 Windows 实测；没有生产 SLA、安全认证或合规认证。

## 19. 发布建议

发布后状态（2026-07-18）：[EchoMind v0.1.0](https://github.com/chanceline-max/EchoMind/releases/tag/v0.1.0) 已在公开仓库 [chanceline-max/EchoMind](https://github.com/chanceline-max/EchoMind) 正式发布，GitHub 已识别 Apache-2.0，Private Vulnerability Reporting 已启用。本状态更新不改变本审计的 **PASS_WITH_LIMITATIONS** 结论和技术限制。

| 用途 | 建议 |
|---|---|
| 本地开发者 MVP 使用 | 可以；仅在理解限制并备份数据后使用 |
| 公开发布源码 | 已按 Apache-2.0 正式发布；继续保留 MVP 限制、隐私警告和非生产就绪声明 |
| 接受外部贡献 | 可以按 CONTRIBUTING 和 Apache-2.0 贡献许可审查；不得接收真实聊天或无权提交的材料 |
| 处理真实敏感聊天 | 谨慎且不建议作为默认承诺；先做备份、磁盘/账号保护、远程 Provider 政策审查 |
| 生产或多用户部署 | 不建议；未审计认证、权限、加密、运维和多租户 |

## 20. 可复现命令

```powershell
# 后端
cd backend
.\.venv\Scripts\python.exe -m pytest tests/audit
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m mypy src tests
.\.venv\Scripts\python.exe -c "from echomind.main import app"

# 前端（使用满足 engines 的 Node）
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:e2e:mvp

# 代表性负载
cd ..
.\backend\.venv\Scripts\python.exe scripts\audit_representative_load.py

# 仓库
git diff --check
git status --short
git ls-files
```

迁移回环和干净副本命令使用系统临时目录，执行后立即删除数据库/副本；具体结果记录在第 11、12 节。首次依赖安装需要可用包源，默认应用运行和 Mock 闭环不需要外部模型网络。
