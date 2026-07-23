# Changelog

本项目的重要用户可见变化记录在此。版本号遵循语义化版本格式；0.1.x 仍可能调整 API 和数据结构。

## [Unreleased]

### Changed

- Insight、Evidence、审核修订和 EchoProfile 的受控状态在前端统一显示为简体中文，内部 API/数据库枚举保持不变。
- 候选抽取升级为 `candidate-extraction-1.1`，要求面向用户的模型自由文本使用简体中文；历史 1.0 Insight 不自动翻译或覆盖。
- 洞察审核增加显式高置信批量确认：仅限 `>50%`、证据有效的 fact/preference/pattern/change；风险类型仍逐条审核，后端整批重验并保留逐条修订历史。

## [0.1.0] - 2026-07-18

### Added

- 通用 JSON、CSV 和纯文本聊天 Parser，以及可组合、非破坏性的 Cleaning Pipeline。
- 同步本地导入、消息查看、分析排除与文件哈希去重。
- 统一 LLM Provider 抽象、确定性离线 Mock 和受控 OpenAI-compatible Provider。
- 候选 Insight、可追溯 Evidence、确定性 Confidence 和人工审核 Revision。
- confirmed-only EchoProfile 不可变快照及 Markdown/JSON 导出。
- 普通用户可达的同步分析入口和完整本地 MVP 闭环。

### Security

- 写请求使用精确 Origin 校验，敏感响应使用 `Cache-Control: no-store`。
- 上传使用请求级临时目录并在成功或失败后清理。
- ProfileSnapshot 和 InsightRevision 使用不可变约束；核心证据链禁止无提示级联删除。
- API Key 只从服务端环境读取，不进入浏览器、数据库、日志或错误响应。

### Privacy

- 默认 Mock Provider 完全离线，不发送聊天内容。
- 远程 Provider 同时要求服务端启用和逐请求授权，并只接收所选窗口的 `normalized_content` 与受控结构字段。
- 浏览器不把聊天、Insight、Evidence 或 Profile 写入持久化存储。
- 示例、测试和 E2E 只使用人工合成数据。

### Known limitations

- 分析同步执行，默认 Mock 不产生真实 Insight。
- WeFlow、PDF/Word、云分享、多用户权限和应用层数据库加密尚未支持。
- Windows 11 已完成完整验证；Linux/macOS 尚未完成同等级验证。
- 真实远程 Provider 尚未完成广泛互操作测试；本版本不代表生产级安全或隐私合规认证。
