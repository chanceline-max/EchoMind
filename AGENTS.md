# AGENTS.md

本文件定义 AI 编码代理在 EchoMind 仓库中的工作规则。

所有代理在修改代码前必须阅读本文件。

## 1. 项目目标

EchoMind 将聊天记录转化为具有证据来源、时间信息和不确定性标记的动态个人认知档案。

核心链路：

聊天记录
→ 导入
→ 标准化
→ 清洗
→ Insight 抽取
→ 证据绑定
→ 用户校正
→ EchoProfile

任何功能都应服务于该链路。

## 2. 当前优先级

优先级从高到低：

1. 数据不丢失
2. 原始内容可追溯
3. 推断有证据
4. 隐私安全
5. 处理过程可测试
6. 输出结果可解释
7. 用户可以修改 AI 判断
8. 界面可用
9. 性能优化
10. 视觉效果

不得为了低优先级目标破坏高优先级目标。

## 3. 禁止事项

禁止：

* 将 AI 推断保存为确定事实
* 删除原始消息正文
* 不保留原始文件哈希
* 在日志中打印聊天正文
* 硬编码 API Key
* 自动上传用户文件
* 默认依赖真实付费模型
* 在测试中调用真实模型 API
* 使用医疗或心理诊断语言
* 用 MBTI 代替完整分析
* 没有证据就生成高置信度人格结论
* 为了“未来可能需要”提前引入微服务
* 创建无法运行的伪实现
* 用 TODO 代替当前任务的核心功能
* 修改无关模块
* 未运行测试就声称功能完成

## 4. 数据原则

所有消息同时保留：

* raw_content
* normalized_content

任何清洗操作不得覆盖 raw_content。

所有 Insight 必须包含：

* insight_type
* statement
* confidence
* status
* extraction_version
* created_at

重要 Insight 至少关联一条 Evidence。

推断应区分：

* fact
* preference
* pattern
* inference
* hypothesis
* contradiction
* change

## 5. 隐私原则

EchoMind 默认 local-first。

敏感内容：

* 不写日志
* 不写测试快照
* 不加入示例数据
* 不提交 Git
* 不进入错误追踪服务

测试样本必须是人工构造或彻底脱敏的数据。

外部模型调用必须：

* 明确由用户启用
* 经过统一 Provider 接口
* 说明会发送哪些内容
* 支持关闭
* 支持 Mock Provider

## 6. 工程边界

默认技术栈：

Backend：

* Python 3.12
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic
* SQLite
* pytest
* Ruff
* mypy

Frontend：

* React
* TypeScript
* Vite
* TanStack Query
* Vitest
* Playwright

不得在没有明确收益时替换技术栈。

## 7. 推荐目录

backend/
app/
api/
core/
db/
models/
schemas/
parsers/
cleaning/
extraction/
profiling/
providers/
services/
tests/

frontend/
src/
api/
components/
features/
pages/
routes/
types/
tests/

docs/
samples/
scripts/

## 8. 开发流程

每次任务执行前：

1. 阅读 README.md
2. 阅读 AGENTS.md
3. 阅读相关 docs
4. 查看 Git 状态
5. 查看相关实现和测试

执行任务时：

1. 确定最小改动范围
2. 先设计输入、输出和失败行为
3. 优先编写或更新测试
4. 完成功能
5. 运行相关测试
6. 运行格式和静态检查
7. 检查是否泄露敏感信息
8. 更新相关文档

执行完成后必须报告：

* 修改文件
* 实现内容
* 测试命令
* 测试结果
* 已知限制
* 未完成事项

## 9. 测试要求

每个 Parser 至少测试：

* 正常输入
* 空文件
* 编码异常
* 字段缺失
* 无效时间
* 重复消息
* 不支持的消息类型
* 大文件的基本行为

每个 Cleaner 至少测试：

* 输入不变性
* raw_content 不被覆盖
* 开关启用和关闭
* 边界条件
* 幂等性

Insight 流程至少测试：

* 无证据时不能生成已确认 Insight
* 相同 Insight 的去重
* 冲突信息保留
* Mock Provider 输出验证
* 失败后的恢复
* 重复执行不会产生无限重复数据

## 10. API 设计原则

API 应：

* 使用明确的请求与响应 Schema
* 提供可理解的错误信息
* 不返回服务器路径
* 不返回密钥
* 分页返回大量数据
* 对导入和抽取任务提供状态
* 支持失败任务重试
* 避免把数据库模型直接作为 API Schema

## 11. 模型调用原则

不得将完整聊天数据库一次性发送给模型。

需要经过：

* 范围选择
* 消息过滤
* 上下文构造
* Token 预算
* 分批处理
* 结构化输出验证
* 失败重试
* 结果版本记录

Provider 输出必须经过 Pydantic Schema 验证。

无效输出不得直接进入正式 Insight 表。

## 12. 置信度原则

模型提供的 confidence 只能作为参考，不能直接视为最终置信度。

最终置信度应结合：

* 信息是否明确自述
* 证据数量
* 重复频率
* 时间跨度
* 场景跨度
* 消息上下文完整度
* 相反证据
* 信息时效性

计算规则必须可解释、可测试、可版本化。

## 13. 文档同步

以下变化必须更新文档：

* 数据模型变化
* API 行为变化
* Parser 格式变化
* Profile Schema 变化
* 隐私边界变化
* 新增外部依赖
* 重大架构决策

重大决策记录到：

docs/DECISIONS.md

## 14. 完成定义

一个任务只有在以下条件满足时才算完成：

* 功能符合任务范围
* 代码能够运行
* 测试通过
* 静态检查通过，或明确记录未通过原因
* 无明显敏感信息泄露
* 文档已同步
* 没有用占位实现冒充完成
* 没有擅自扩大范围

若无法全部完成，必须明确标记为部分完成，不得声称已完成。
