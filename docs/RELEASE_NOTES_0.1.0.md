# EchoMind 0.1.0 发布说明

发布日期：2026-07-18

EchoMind 0.1.0 是首个本地优先、证据优先的 MVP 正式版本。它帮助单个本地用户把受支持的聊天导出转换为可追溯、可人工审核的 Insight，并生成不可变 EchoProfile 快照。它不是医疗或心理诊断工具，也不承诺生产级稳定性、科学人格测量或完全准确的推断。

## 核心工作流

1. 导入通用 JSON、CSV 或 TXT 聊天文件。
2. 使用确定性 Parser 和 Cleaning Pipeline 标准化数据，同时保留 `raw_content`。
3. 查看消息并排除不希望分析的内容。
4. 对明确选择的会话触发有限窗口分析。
5. 查看候选 Insight、Evidence 和机械 Confidence 支撑强度。
6. 编辑、确认、驳回或恢复 Insight，并查看 Revision 历史。
7. 从 confirmed Insight 生成不可变 ProfileSnapshot，显式导出 Markdown 或 JSON。

## 安装要求

- Python 3.12
- Node.js 20.19 或更高版本；推荐 Node 24
- 首次安装依赖通常需要访问 Python 和 npm 软件包仓库

完整命令见根目录 `README.md`。Windows 11 已完成完整安装、迁移、测试、构建和 E2E 验证；Linux/macOS 尚未完成同等级验证。“本地优先”描述默认运行和数据边界，不表示首次安装依赖可以完全离线。

## 默认离线行为

默认 `LLM_PROVIDER=mock` 且 `LLM_REMOTE_ENABLED=false`。Mock Provider 不访问网络、不读取 API Key，也不会根据聊天正文生成真实 Insight；默认分析结果可以是空候选。测试和演示可注入固定的合成候选。

## 远程 Provider

要获得真实模型候选，用户需要在后端私有 `.env` 中配置兼容 Provider、HTTPS endpoint、模型名和 API Key，并设置 `LLM_REMOTE_ENABLED=true`。浏览器分析页面还要求当前请求逐次确认，不能在前端输入或保存 Key、endpoint、Prompt 或模型参数。

远程 Provider 会收到当前所选会话窗口的 `normalized_content`、匿名角色、时间、类型和受控上下文结构。它不会收到完整聊天数据库、`raw_content`、参与者姓名、文件路径或数据库凭据。第三方 Provider 可能保留请求，用户必须自行核对其政策；当前 OpenAI-compatible 适配器尚未完成广泛供应商互操作验证。

## 支持格式

- `echomind-generic-chat` JSON 1.0
- 固定表头的 EchoMind Generic CSV 1.0
- EchoMind Generic Text 1.0

WeFlow 当前明确返回未支持，不会猜测真实格式。

## 隐私与敏感数据提醒

- 原上传文件仅存在于请求级临时目录，处理结束后清理；数据库保留哈希、不可变原文和派生正文。
- SQLite 数据库目前没有应用层静态加密，请保护操作系统账户并考虑整盘加密。
- 浏览器不持久化聊天、Evidence、Insight 或 Profile。
- 导出的 Profile 可能包含高度敏感的派生信息；`excerpts` 模式还会包含 Evidence 摘录，请妥善保管。
- 不要把真实聊天、数据库、`.env`、API Key 或 Profile 提交到 GitHub Issue 或 Pull Request。

## 升级说明

0.1.0 是首个公开 MVP 候选。首次使用先在 `backend/` 创建 `data` 目录并执行 `alembic upgrade head`。现有开发数据库升级前应备份；不要对含有需要保留数据的数据库执行 `alembic downgrade base`。

API、数据结构和导出 Schema 在后续 0.x 版本仍可能变化。项目没有提供自动云迁移、跨设备同步或长期兼容承诺。

## 主要限制与已知问题

- 同步分析没有后台任务恢复或真实进度百分比。
- SQLite 面向本地单用户，不适合多进程或多用户部署。
- 默认 Mock 返回空候选；真实模型候选需要显式配置远程兼容 Provider。
- 真实远程 Provider 尚未完成正式互操作和数据保留审计。
- WeFlow、PDF/Word、云分享、移动 App、多用户权限和应用层数据库加密未实现。
- 完整无障碍、生产安全和正式隐私合规认证尚未完成。

## 许可证

EchoMind 0.1.0 使用 Apache License 2.0。Copyright 2026 杨锦辰。参见根目录 `LICENSE` 和 `NOTICE`；第三方依赖保留各自许可证，汇总见 `docs/THIRD_PARTY_LICENSES.md`。
