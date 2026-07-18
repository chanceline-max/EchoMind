# EchoMind frontend

阶段 9 的 React、TypeScript 和 Vite 前端。除导入和会话路由外，提供 `/insights` 审核列表与 `/insights/:insightId` 证据审核页；原消息链接使用 `?message={id}` 定位、滚动和高亮。审核请求携带 `expected_revision`，409 时要求重新加载，不静默覆盖。请求缓存仅存在内存，不使用浏览器持久化存储。

安装、启动和检查命令见仓库根目录的 `README.md`。
