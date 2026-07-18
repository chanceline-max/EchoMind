# EchoMind 产品规格

## 1. 产品愿景

EchoMind 将长期聊天记录转化为一份持续演化的个人认知模型。它的核心价值不是“给人贴标签”，而是帮助用户在时间、关系和情境中理解自己，并让每个结论都有证据、类型、置信度、替代解释和修订入口。

## 2. 目标用户与场景

### MVP 主要用户

愿意在自己的电脑上导入个人聊天记录，并主动审阅系统判断的单个档案所有者。

### 核心场景

1. 用户导入一份受支持的聊天导出文件。
2. 系统识别格式、解析并标准化消息，展示处理统计和错误。
3. 用户浏览会话与消息，排除不希望分析的内容。
4. 系统以有限上下文窗口生成候选 Insight，并绑定证据。
5. 用户查看证据，确认、编辑或驳回 Insight。
6. 系统仅使用允许状态的 Insight 生成 Markdown 和 JSON EchoProfile。

## 3. 核心概念与 Insight 判定边界

- **Message**：同时保存不可被清洗覆盖的 `raw_content` 和可重建的 `normalized_content`。
- **Evidence**：某条 Message 中支持、反驳或补充上下文的具体片段，必须能回到 SourceFile。
- **Insight**：带类型、状态、时间范围、置信度、推理依据和 Evidence 的候选认知单元。
- **EchoProfile**：由符合生成策略的 Insight 组织而成的版本化快照，不是永久真相。

### 3.1 类型定义

| insight_type | 可测试定义 | 最低证据条件 |
|---|---|---|
| fact | 用户明确陈述，可直接从消息得到，不依赖跨消息推理 | 至少一条明确自述 Evidence；陈述不得超出原文语义 |
| preference | 用户明确表达，或在多个选择场景中稳定表现出的偏好 | 一条明确偏好自述，或至少两个独立选择事件 |
| pattern | 至少两个相互独立的事件或时间点中重复出现的可观察结构 | 至少两组独立 Evidence；不能由同一消息拆分或重复转发构造 |
| inference | 基于 fact、preference 或 pattern 进一步推导的解释，原文未直接表述 | 记录依赖的 Evidence/Insight、推理依据及至少一个其他可能解释 |
| hypothesis | 有解释力但证据不足、等待验证的暂定推断 | 至少一条相关 Evidence；保持 proposed，置信度上限由算法版本规定 |
| contradiction | 在相同适用条件和重叠有效期内当前无法同时成立，或存在明显冲突的信息 | 同时保留冲突双方 Evidence；不同时间/情境导致的差异不得误标 |
| change | 同一主题在不同时间点发生可识别变化 | 至少两个不同时间点的 Evidence，并明确 before/after 或变化方向 |

“独立事件”指不同 source message 组或不同时间点的真实事件，不包括同一消息的复制、引用、转发或连续拆句。

### 3.2 硬性约束

- 单条消息不能直接生成 pattern。
- 没有明确自述 Evidence 不能生成 fact。
- inference 必须记录推理依据和其他可能解释。
- hypothesis 的置信度必须受版本化上限约束，且模型不能将其直接设为 confirmed。
- change 至少需要两个不同时间点。
- contradiction 必须保留双方 Evidence，不得选择性删除不利证据。
- AI 生成的 Insight 没有有效 Evidence 时不得持久化为正式 Insight。
- 用户手工草稿若暂时没有 Evidence，只能保持 proposed/hypothesis，不能确认或进入正式 Profile。

## 4. MVP 范围

### 必须完成

- 导入通用 JSON、CSV、纯文本；提供 WeFlow Parser 接口框架和脱敏示例。
- 文件哈希去重、解析验证、标准化与可组合清洗 Pipeline。
- 文件、任务、会话和消息查看；消息可排除或恢复分析。
- 使用 MockLLMProvider 完成候选 Insight 抽取闭环。
- Evidence 绑定、Insight 去重、冲突标记及可解释置信度计算。
- Insight 筛选、查看证据、确认、编辑、驳回。
- 生成等价的 `EchoProfile.md` 和 `EchoProfile.json` 快照。
- 默认本地运行，无真实 API Key 也能完成演示和测试。

### 明确不做

- 医学或心理诊断、风险预测、MBTI 自动判定。
- 多用户协作、云账号、移动 App、付费或推荐系统。
- 复杂社交网络、向量数据库集群、图数据库、微服务。
- 生产云部署和花哨的 3D 可视化。

### MVP 运行边界

- 一个本地 workspace 只维护一个 profile owner；Participant 仍可表示多个聊天对象。
- 单用户、单机、单应用进程；不提供身份认证、局域网共享或并发协作。
- 默认 MockLLMProvider，完整闭环不需要 API Key、付费模型或互联网。
- OpenAI-compatible Provider 是用户显式启用的可选路径，不是 MVP 验收前提。
- WeFlow 仅提供适配器接口和明确的“不支持”结果，直到获得授权脱敏样本。
- 文件大小和消息数上限由阶段 3/5 的性能与安全测试确定，MVP 不承诺无限规模。

## 5. 功能需求

### 导入

- 用户能预览选中文件、格式识别结果及将保存到本地的内容。
- 不支持或不合法的格式必须返回可理解、可定位的错误。
- 同一文件重复导入必须可识别；默认不重复创建消息。
- 阶段 5 导入是同步请求：前端只显示真实上传进度和服务端处理中状态，成功后保存 SourceFile；失败整体回滚并由用户重新提交。当前不创建持久化 ImportJob 或伪造阶段进度。

### 消息审阅

- 按会话、参与者、时间范围查看标准化消息。
- 可查看 raw 与 normalized 差异，但默认避免无意义重复显示。
- 可按数据库 Message ID 排除/恢复单条消息；排除原因保留并影响后续抽取。审计时间和完整修订记录留到出现真实审计用例后实现。

### Insight 审阅

- 支持类型、状态、置信度和时间筛选。
- 详情页显示陈述、类别、计算组成、支持/反对证据和替代解释。
- 用户编辑后保留修订来源；拒绝的 Insight 不进入 Profile。
- 矛盾不被自动抹平，应以明确关系展示。

### Profile

- Profile 明确生成时间、覆盖范围、数据数量、版本和限制。
- Markdown 与 JSON 在章节、Insight 和 Evidence 引用上语义等价。
- 每次生成都创建不可变快照；旧快照可查看但不自动覆盖。
- 正式生成和导出只包含 confirmed Insight；proposed、rejected、superseded 不进入阶段 10 Profile，confidence 不作为纳入门槛。
- partial Insight 默认保留并明确警告；invalid Insight 只能进入“证据已失效”区域，不能作为当前有效结论。
- Markdown 与 JSON 来自同一个 `EchoProfileDocument`，相同来源/选项由 generation fingerprint 复用不可变 Snapshot。
- 历史 Snapshot 只在读取时动态显示 current/stale/source unavailable，不因来源变化被回写。

## 6. 非功能需求

- **隐私**：本地优先、无默认遥测、无默认外发、日志无聊天正文。
- **可追溯**：Profile → Insight → Evidence → Message → SourceFile。
- **可恢复**：阶段 5 同步导入失败整体回滚并可重新提交；后续长时抽取任务按真实需求设计检查点。
- **幂等**：相同输入、解析器版本和抽取版本重复运行不会无限复制数据。
- **可移植**：SQLite MVP，可迁移到 PostgreSQL；导出格式版本化。
- **可测试**：核心闭环不依赖网络或真实模型。

## 7. 可解释置信度

MVP 的置信度是排序与审阅辅助分数，不是统计概率。初始公式建议：

```text
score = clamp(0.05, 0.95,
  0.10
  + 0.30 * explicit_self_report
  + 0.15 * repetition
  + 0.10 * temporal_span
  + 0.10 * relationship_diversity
  + 0.15 * evidence_quality
  + 0.10 * recency
  - 0.25 * contradiction_strength
)
```

各因子归一化到 0..1，并连同原始统计保存。公式和权重必须版本化，UI 显示“为什么得到这个分数”。用户调整置信度时保留系统分数与用户覆盖值，不能覆盖计算依据。

## 8. 风险与不确定性登记

| 风险/未知项 | 影响 | MVP 缓解方式 | 剩余风险 |
|---|---|---|---|
| 模型生成看似合理但错误的推断 | 用户误解自己或他人 | 类型区分、Evidence 强制、proposed 默认、用户确认 | 证据存在仍不代表解释唯一正确 |
| 置信度被误读为概率 | 产生虚假精确感 | 显示计算因子、公式版本和“启发式分数”说明 | 权重仍需通过真实审阅反馈校准 |
| 聊天中含第三方隐私 | 非预期处理他人敏感数据 | 本地默认、排除、最小化、无遥测、删除 | 用户是否有权处理数据依司法辖区和场景而异 |
| Parser 对平台格式猜测错误 | 丢消息、错时间、错发送者 | 格式验证、版本化、样本契约；WeFlow 不虚假承诺 | 平台导出格式可能无通知变化 |
| 分段窗口丢失长距离上下文 | Insight 片面或矛盾 | 重叠窗口、跨批次合并、冲突保留 | 不使用全量上下文时无法完全消除 |
| 大文件导致 SQLite 锁和内存压力 | 导入慢或失败 | 分块上传、解析前资源上限、单事务回滚 | 当前同步 MVP 不支持超过限制的大文件后台恢复 |
| 归档后备份仍含数据 | 用户误以为归档等于擦除 | MVP 明确不提供物理删除，展示备份/SSD 限制 | 未来删除功能仍无法保证物理安全擦除 |
| 本地设备或账户被攻破 | 全部档案泄露 | localhost、最小权限、建议整盘加密 | MVP 暂无应用层静态加密 |
| 远程 Provider 政策不透明 | 外发数据被保留或训练 | opt-in、窗口化、范围提示、Provider 配置 | 仍依赖第三方实际政策和执行 |
| 用户编辑覆盖系统历史 | 失去可追溯性 | InsightRevision、乐观锁、系统分数与覆盖值并存 | 修订历史本身也是敏感数据 |

## 9. MVP 自动化验收矩阵

当且仅当以下条款全部通过并记录真实命令结果，MVP 才算完成。测试统一使用人工合成数据；隐私审查项不能被“测试通过”替代。

| ID | 可验证条款 | 验证方式 |
|---|---|---|
| MVP-A01 | 全新环境按 README 安装后，后端健康接口返回版本化 schema，前端成功显示后端状态，前后端均可构建 | API 集成测试、前端测试、Playwright、构建命令 |
| MVP-A02 | 清除 API Key 并阻断测试进程外网后，合成样本可完成导入→清洗→Mock 抽取→审核→Profile 闭环 | Playwright 端到端测试、网络禁用测试夹具 |
| MVP-A03 | JSON、CSV、纯文本各有有效、空、字段缺失、无效时间和不支持类型用例，输出符合 canonical schema | Parser 单元测试、契约测试 |
| MVP-A04 | WeFlow 输入返回稳定的 `unsupported_format`/未支持结果，不产生 Conversation 或 Message | Parser 单元测试、API 集成测试 |
| MVP-A05 | 同一文件、parser version 和配置重复导入两次，SourceFile/Conversation/Message 数量不增加 | API 集成测试、数据库断言 |
| MVP-A06 | 每个 Cleaner 可启停且幂等；运行前后 `raw_content` 和源文件 hash 完全不变；统计不包含正文 | Cleaner 单元/性质测试、数据库集成测试 |
| MVP-A07 | 类型规则夹具证明：单消息不能生成 pattern、非自述不能生成 fact、change 有两个时间点、contradiction 有双方 Evidence、hypothesis 不超过上限 | Insight/置信度单元测试、数据库约束测试 |
| MVP-A08 | AI 候选只能 proposed；无 Evidence、无效 message ID 或窗口外引用不会生成正式 Insight | 抽取 Pipeline 单元测试、Provider 契约测试 |
| MVP-A09 | 用户确认、编辑、驳回和排除消息后，API/UI 状态一致；被排除证据使相关结论失效或降级，不能继续作为有效结论导出 | API 集成测试、前端测试、Playwright |
| MVP-A10 | 对同一冻结输入生成的 Markdown/JSON 通过 schema，并具有相同 Insight/Evidence ID 集合；排除 snapshot ID、生成时间和版本号后，重复生成的规范化内容稳定 | Profile 单元测试、schema/契约测试 |
| MVP-A11 | 从每个 Profile 结论可沿 Insight→Evidence→Message→SourceFile 返回；断链条目被标记 `evidence_status=invalid` 且不作为有效结论 | 数据库集成测试、Playwright |
| MVP-A12 | SourceFile、Conversation、Message、Evidence 和 Insight 不存在物理删除 API 或无提示数据库级联；归档/排除不删除 raw，并正确传播 Evidence/Insight/Profile 有效性 | API 集成测试、数据库迁移测试、Service 集成测试 |
| MVP-A13 | 上传类型/大小/路径、错误脱敏、精确 CORS、浏览器非持久存储和远程 Provider opt-in 行为符合隐私文档 | API 安全测试、前端测试、Playwright、手动隐私审查 |
| MVP-A14 | 后端 pytest/Ruff/mypy，前端 Vitest/类型检查/构建，关键 Playwright 和 Alembic 空库升级/回滚全部通过 | 静态检查、测试命令、数据库迁移测试 |
| MVP-A15 | 仓库和测试产物不含密钥、真实聊天、数据库、Profile、敏感快照或绝对用户路径 | 静态扫描、Git 文件清单检查、手动隐私审查 |

## 10. 成功指标（MVP 验证指标）

- 导入闭环成功率和格式错误可解释率。
- Insight 证据覆盖率必须为 100%。
- 用户确认、编辑、驳回的比例，用于判断候选质量；不作为人格正确性的证明。
- 从 Profile 条目返回原始消息的路径成功率必须为 100%。
- 离线测试可重复通过。
