# EchoMind frontend

阶段 10 的 React、TypeScript 和 Vite 前端。除导入、会话和 Insight 审核外，提供 `/profiles` 生成/快照列表与 `/profiles/:profileId` 结构化详情。默认 references，excerpts 生成和导出均明确提醒敏感摘录；Markdown 只用 `<pre>` 显示，导出仅在用户点击后请求并释放临时 Object URL。

Profile、Markdown 和 JSON 仅保存在短期内存 Query/组件状态；不写 localStorage、sessionStorage、IndexedDB、Service Worker 或 URL，不使用 `dangerouslySetInnerHTML`，不预取导出文件。current/stale/source unavailable 均同时显示文字，不能只靠颜色理解。

安装、启动和检查命令见仓库根目录的 `README.md`。
