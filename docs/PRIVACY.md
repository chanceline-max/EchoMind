# EchoMind 隐私与安全设计

## 1. 数据敏感性

聊天记录不仅包含档案所有者，也包含聊天对象的个人信息。系统生成的价值观、关系、情绪和行为推断可能比原文更敏感。EchoMind 因此把原始文件、消息、Evidence、Insight、Profile、模型请求和模型响应都视为高敏感数据。

本文件是产品工程约束，不构成法律意见，也不声称项目自动符合任何司法辖区的法律。

## 2. 默认承诺

- 默认绑定 `127.0.0.1`，不开放公网或局域网。
- 默认 SQLite 和本地文件目录；默认关闭遥测、崩溃上报和外部分析。
- 默认不配置远程模型；Mock 和纯规则模式可完成测试。
- 远程模型调用必须同时由服务端显式启用和当前请求显式 consent；阶段 7 的内部请求明确 Provider、会话/时间范围和窗口参数。当前尚无分析 UI，调用方必须在外层提供发送范围说明和用户确认。
- 不加载远程字体、追踪像素或第三方前端资源。
- 真实聊天、数据库、档案、密钥和 `.env` 不进入 Git。
- MVP 不提供证据链数据的不可逆物理删除；归档和排除必须保留原始内容并传播 Evidence 失效状态。

## 3. 数据最小化与目的限制

只收集完成导入、审阅、抽取和 Profile 生成所需的数据。导入前展示用途，排除内容不参与后续分析。该原则参考 GDPR Article 5 的目的限制和数据最小化要求，但项目当前不作合规认证。

参考：[EUR-Lex GDPR Article 5](https://eur-lex.europa.eu/eli/reg/2016/679/art_5/oj)。

## 4. 本地存储

```text
data/
├── exports/      # 用户显式生成的档案
└── echomind.db   # SQLite
```

- 阶段 5 上传临时文件使用操作系统或显式配置的私有临时目录，请求结束后清理；数据库 `storage_path` 默认为 null。
- MVP 的 SQLite 和文件默认不做应用层加密；UI 和 README 必须直说这一点。
- 建议用户启用 Windows BitLocker 或等价的整盘加密，并保护操作系统账户。
- 临时文件在成功或失败后清理；清理失败必须显示安全错误，不静默忽略。

## 5. 隐私路径默认策略

| 路径 | MVP 默认 | 允许条件/控制 |
|---|---|---|
| 浏览器 HTTP 缓存 | 禁止缓存消息、Evidence、Insight、Profile 和导出响应 | 敏感 API 返回 `Cache-Control: no-store`；仅静态构建资源可缓存 |
| 前端本地存储 | 禁止把敏感数据写入 localStorage、sessionStorage、IndexedDB、Service Worker cache 或持久化 Query cache | 只允许保存无敏感内容的 UI 偏好，例如主题；TanStack Query 默认仅内存缓存并在页面关闭后消失 |
| CORS | 禁止 `*` 和任意 origin | 开发模式只允许配置中的精确 localhost/127.0.0.1 origin；局域网 origin 必须由用户显式配置 |
| 上传临时文件 | 只写入随机命名的请求级私有临时目录，不使用客户端路径 | 分块限制大小并计算 hash；成功或失败退出作用域时清理，不长期移动；日志不写绝对路径 |
| 导出文件 | 不自动生成、不自动同步、不自动打开外部应用 | 用户显式点击导出并选择本地位置；导出前提示其包含高敏感数据；响应 `no-store` |
| 错误日志 | 默认只允许字段白名单 | 仅 request/job ID、阶段、计数、错误代码；异常和验证错误先安全化，不记录请求/响应 body |
| 测试快照 | 禁止真实或脱敏不足的正文进入快照和测试报告 | 只允许完全合成数据；失败输出需截断并清除 payload |
| 崩溃报告 | 默认关闭所有外部崩溃报告 | 未来如启用，必须用户显式同意、展示接收方和字段，并经过正文/密钥过滤测试 |
| 模型请求缓存 | 本地和 Provider 适配层默认不缓存 prompt/响应 | 用户显式启用远程 Provider 前必须提示第三方可能存在的保留/缓存政策；EchoMind 不替用户假设“零保留” |

前端构建不得嵌入 API Key。开发代理、浏览器控制台、React 错误边界和网络调试输出同样受“无敏感正文”约束。

## 6. 远程模型调用

远程 Provider 是 opt-in 功能，必须满足：

1. 设置页显示目标端点和 Provider。
2. 用户选择是否脱敏；默认启用可识别信息脱敏。
3. 发送前显示消息数量、时间范围和内容类别，不默认展示/记录完整 prompt。
4. 每次调用只发送有限上下文窗口，不发送完整聊天库。
5. API Key 只从环境变量或操作系统密钥存储读取，不写数据库和日志。
6. 请求失败不回退到另一个远程 Provider。
7. 用户可完全禁用模型，只运行导入、清洗和规则处理。

### 阶段 6 Provider 边界

- `mock` 是默认 Provider，不读环境 Key、不访问网络、不根据正文隐藏关键词改变行为。失败场景只能由测试/显式构造参数选择。
- OpenAI-compatible 调用只有 `LLM_REMOTE_ENABLED=true` 和当前 `LLMRequest.remote_consent=true` 同时成立才进入 Transport；拒绝不会触发网络，且失败不会回退其他 Provider。
- Provider 只发送当前 `LLMRequest` 的 system instruction、user messages、响应 Schema 和生成参数。Provider 包不导入 ORM/Repository；阶段 7 Extraction Service 在 Provider 外选择明确会话并构造有限窗口，不读取上传原文件、排除消息或 `raw_content`。
- Key 使用服务端 `SecretStr`，不进入浏览器、数据库、结果、错误或日志。Transport 只向目标请求加入 Bearer Authorization，返回时只保留受限 `x-request-id`、API 版本和 Content-Type，不保留完整 Header。
- endpoint 只来自服务端 Settings；默认 HTTPS，禁止 URL 凭据、fragment、重定向和非 HTTP(S)。显式本地 HTTP 只允许 localhost/127.0.0.1/::1。基础校验不防御 HTTPS DNS 重绑定，不能替代网络出口控制。
- prompt、响应正文和模型请求不缓存、不记录；安全错误不含被拒绝输入、完整路径、Key、Authorization、数据库 URL 或环境变量。最大响应字节、输入字符、单消息、消息数、Schema 和输出上限均在集中配置中限制。
- 自动测试仅使用合成 marker 和 `httpx.MockTransport`。即使开发环境存在真实 Key，默认 Mock 与授权拒绝测试也不会访问网络。

远程服务的数据保留和训练政策由用户选择的 Provider 决定，EchoMind 必须提示用户自行核对。

### 阶段 7 Extraction 隐私边界

- ExtractionRequest 不允许空会话集合或隐式全库选择；只读取明确会话、可选带时区时间范围和当前可分析消息。已排除、归档、删除或无有效时间消息不进入窗口。
- Provider 上下文只包含当前窗口的 `normalized_content`、局部消息/回复别名、匿名角色、时间、类型和截断标记。它不含 `raw_content`、数据库/源消息 ID、参与者姓名、文件名、路径、metadata、cleaning operations、Key 或数据库 URL。
- 单条 Provider 内容最多发送请求上限，默认 4000 字符，采用确定性前缀和 `[TRUNCATED]`；每窗默认最多 40 条/12000 字符且不跨会话。远程调用经双重授权后**会发送这些窗口内的 normalized_content**，不能声称完全不外发聊天内容。
- 模型只返回候选字段与局部 Evidence 引用。Evidence excerpt 在本地从完整 `normalized_content` 生成，不接受模型 excerpt；Prompt 和完整 Provider 输出不写数据库、不缓存、不写日志。
- Insight/Evidence 指纹在数据库只保存 SHA-256，不把正文作为唯一键。ExtractionReport、WindowResult 和 ExtractionError 仅含受控 ID、计数、规则和状态，不含正文、excerpt、Prompt、响应、参与者姓名或路径。
- 自动测试使用完全合成内容、离线 Mock 或 MockTransport；没有真实网络。当前没有分析 HTTP API、浏览器 Insight 缓存或前端 Insight 页面。

### 阶段 8 Confidence 隐私边界

- Confidence 请求只能列出明确 Insight ID 和 aware `as_of`，不能用空列表选择全库。模块不导入 Provider Factory、HTTP Client、FastAPI Request、Parser、Cleaner 或上传服务，也不访问网络。
- 数学输入只含 Insight 类型/状态/自述标记/有效期/版本，Evidence 的 ID/fingerprint/role/相关度/有效性，以及 Message 的 ID/sender/conversation/timestamp 和 Owner 布尔值。加载和公式均不读取 raw/normalized content、excerpt、title、statement、参与者姓名、文件名、路径、Prompt 或模型响应。
- `model_confidence` 仍保留用于审计，但不进入公式和输入指纹。修改模型自评不会触发重算，也不会改变最终支撑强度。
- `confidence_factors_json` 只保存数值、计数、UTC 时间、版本和安全规则码；`confidence_explanation` 由固定模板生成，不包含 Message/Evidence ID 或正文。Report/Error 只返回 ID、状态、计数和白名单 details，不返回 SQL、traceback 或路径。
- 输入指纹是结构化字段的 SHA-256。Evidence fingerprint 的变化会间接触发重算，但正文或 excerpt 不被直接复制到评分指纹、报告、解释或日志。
- Confidence 没有 HTTP API、浏览器缓存、前端页面、模型请求缓存、遥测或 ConfidenceHistory。每个 Insight 的短事务只更新评分字段和 evidence_state，不修改 Evidence、聊天正文或用户编辑内容。
- 文档和解释统一称“当前证据在机械规则下的支撑强度”，明确不是科学概率、诊断可信度或用户可信程度；低分不构成对用户的价值评价。

### 阶段 9 审核隐私边界

- Insight/Evidence/Revision 和消息定位响应统一 `Cache-Control: no-store`；错误沿用安全结构，不返回 SQL、traceback、Key、环境变量或本机路径。存在 Origin 的写请求必须精确命中 allowlist；无 Origin 的本地 CLI 维持既有策略。
- 前端仅使用内存 TanStack Query，不写 localStorage、sessionStorage、IndexedDB、Service Worker 或持久化 Query cache。运行时验证拒绝缺字段、错误 sender role 和畸形 revision 响应；正文使用 React 文本渲染，不使用 `dangerouslySetInnerHTML`。
- Evidence 详情只公开匿名角色 PROFILE_OWNER/OTHER，不返回参与者姓名、raw_content、Prompt 或 Provider 响应。Revision snapshot 会保存 Insight title/statement 等敏感派生文本，必须按聊天正文同级保护；它不复制消息正文或 Evidence excerpt。
- 审核不会调用 Provider 或网络模型；E2E 数据由正式本地 Import、离线 Mock Extraction 和 Confidence Service 创建，测试完成后数据库、上传临时目录和 Playwright 结果自动清理。
- rejected、superseded、消息排除和 Evidence 失效都不是删除。恢复消息只移除用户排除及其派生的 `source_message_excluded`，其他自动或人工原因继续保留。

### 阶段 10 Profile 隐私边界

- Profile 生成完全离线，不导入 Provider、HTTP client 或模型 Factory；只读取 confirmed Insight 和本地 Evidence 结构。
- references 是默认模式，不复制 Evidence excerpt；excerpts 必须由用户显式选择并二次确认，只复制既有 excerpt，不读取 raw_content 或重新从 Message 生成。
- Profile 不含 Participant 姓名、SourceFile filename、路径、source_message_id/source_location、cleaning operations、Prompt、Provider 响应、API Key、review note 或 Revision 历史。
- Source manifest 不保存 title、statement、reasoning 或 excerpt；这些内容只参与单向 SHA-256 组件计算。Profile 本身及 Snapshot 仍是高敏感派生数据。
- Profile API 与导出统一 `no-store/no-cache`；导出使用通用 UTC 日期文件名和 `nosniff`，不含姓名、会话标题或文件名。
- 前端只使用短期内存 Query；不预取导出、不把 Document/Markdown/JSON 写入 localStorage、sessionStorage、IndexedDB、Service Worker、URL 或 console。Markdown 只在用户点击后用 `<pre>` 显示。
- Snapshot 不可更新或删除；来源变化只动态显示 stale/source unavailable，历史正文不被静默修改。当前无云分享、公开链接、PDF/Word、遥测或崩溃上报。

### 阶段 4 清洗边界

- Cleaning 只处理调用方已传入的 `ParsedChatFile` 内存对象；不扫描目录、不读取附件、不访问 URL、不调用网络、不创建缓存数据库。
- `raw_content` 永久保留且不被 Cleaner 赋值；`normalized_content`、分类、重复、排除和 AnalysisUnit 都是可重建派生数据。排除与重复标记不删除消息或 reply 引用。
- 脱敏默认关闭，显式开启也只覆盖少量确定性模式，不能替代人工隐私审查。phone_like 仅覆盖带 `+` 的明确国际形式；email/IPv4/custom 均可能误报或漏报。
- 操作追溯、统计、CleaningError 和 CleaningWarning 不保存聊天正文、URL、匹配值或本机路径。AnalysisUnit 的 `combined_content` 是敏感派生正文，保护级别与消息正文相同，不得写日志、快照或浏览器持久存储。

## 7. 日志政策

允许记录：request/job ID、阶段、消息计数、耗时、状态、解析器版本、安全错误代码。

禁止记录：聊天正文、Evidence excerpt、文件内容、完整本地路径、参与者姓名、prompt/响应正文、访问令牌、API Key、数据库连接串。

错误对象在进入日志前经过统一安全化。该约束参考 OWASP 对敏感个人数据、令牌、密钥和连接串的日志排除建议。

参考：[OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)。

## 8. 用户控制

- 排除或恢复消息参与分析。
- 查看、修改、确认、驳回、恢复或 supersede Insight；这些操作都不物理删除 Evidence 或历史。
- 归档 SourceFile/Conversation/Message，排除或恢复 Message 参与分析，并查看受影响 Evidence/Insight/Profile。
- MVP 不在界面提供不可逆物理删除；未来物理删除必须先显示完整影响范围并二次确认。
- 导出结构化档案。
- 查看远程模型配置和最近调用的安全统计。
- 在调用前关闭远程模型或脱敏步骤。

## 9. 威胁模型（MVP）

| 风险 | MVP 控制 |
|---|---|
| 仓库误提交真实数据 | `.gitignore`、合成样本、提交前扫描 |
| 日志泄露正文/密钥 | 中央安全日志适配器、字段白名单测试 |
| 恶意导入文件 | 大小限制、格式验证、文本处理、不执行内容 |
| 路径穿越 | 生成服务端文件名、校验解析后路径位于 data 根目录 |
| XSS | 原文按文本渲染，不渲染导入 HTML |
| 浏览器持久化泄露 | 敏感响应 no-store；禁止敏感 localStorage/IndexedDB/Service Worker cache |
| 宽松 CORS 暴露本地 API | 精确 origin allowlist；禁止通配 CORS |
| 临时/导出文件遗留 | 请求级临时目录作用域清理、用户显式导出和敏感提示 |
| CSV 公式注入 | 导出 CSV 时转义危险前缀；MVP Profile 不默认导出 CSV |
| 未授权局域网访问 | 默认只监听 localhost；开放网络必须显式配置 |
| 远程模型过度外发 | 服务端开关 + 逐请求 consent；阶段 7 已实现明确范围、匿名角色、有限单会话窗口和排除过滤，发送前 UI 预览仍属后续任务 |
| 错误人格推断造成伤害 | 非诊断声明、证据链、类型区分、用户确认和驳回 |
| 派生档案比原文更敏感 | 与原文同级保护、可归档/排除、无默认分享；MVP 不声称物理安全擦除 |

## 10. AI 风险治理

EchoMind 使用“治理、映射、测量、管理”的持续风险思路，记录 Provider、抽取版本、置信度版本、用户修订和已知局限。此做法参考 NIST AI RMF 的透明、可解释、隐私增强和生命周期风险管理原则。

参考：[NIST AI RMF 1.0](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10)、[NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)。

## 11. 可验证隐私检查

- API 安全测试断言敏感响应包含 `Cache-Control: no-store`，错误不含绝对路径和正文。
- CORS 集成测试断言允许列表 origin 成功，未知 origin 和通配配置失败。
- 前端测试注入 localStorage/IndexedDB spy，断言敏感实体不被写入。
- 上传集成测试断言请求级临时目录在成功和失败后无孤儿文件。
- 日志测试使用合成 canary 字符串，断言日志和测试报告中不存在该字符串。
- Provider 测试只注入 MockTransport 并断言默认 Mock；远程 Provider 只有服务端开关与逐请求 consent 同时成立才可进入 Transport。
- 仓库/产物扫描检查 `.env`、数据库、Profile、真实样本、绝对用户路径和常见密钥模式。
- 发布前仍执行手动隐私审查，因为第三方政策、操作系统备份和浏览器行为不能完全由单元测试证明。

## 12. 尚未解决

- 应用层静态加密及跨平台密钥恢复。
- 第三方聊天参与者的授权、通知与不同司法辖区要求。
- 备份与安全擦除的用户体验。
- 远程 Provider 的数据保留政策如何机器可读地展示。
- 项目面向公开发行前需要独立安全和隐私审查。
