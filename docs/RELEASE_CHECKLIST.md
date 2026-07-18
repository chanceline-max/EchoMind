# EchoMind 0.1.0 发布清单

未勾选项目不得被解释为已授权或已完成。Tag、Push、Release 和上传产物必须由项目所有者手动执行。

## 所有者决定

- [x] 许可证选择：Apache-2.0
- [x] 版权持有人：杨锦辰
- [ ] 确认公开仓库地址
- [ ] 确认是否启用 GitHub Private Vulnerability Reporting
- [ ] 确认是否创建 `v0.1.0` tag
- [ ] 确认是否发布 GitHub Release

## 代码验证

- [x] 完整后端 pytest
- [x] Ruff lint 和格式检查
- [x] mypy 严格类型检查
- [x] 前端 Vitest、ESLint、TypeScript 和 Vite build
- [x] Stage 5、9、10 和 11 Playwright 闭环
- [x] Alembic upgrade/downgrade/upgrade、`alembic check` 和 metadata drift
- [x] 删除约束及 Snapshot/Revision 不可变测试
- [x] 工作树和历史六条迁移无意外变化
- [x] 依赖许可证审计无发布阻断项

## 隐私

- [x] 无真实聊天、真实 Profile 或未充分脱敏样本
- [x] 无真实 `.env`、API Key、令牌或数据库 URL
- [x] 无 SQLite、WAL/SHM、上传或导出残留
- [x] 无本机绝对路径、`test-results` 或 `playwright-report`
- [x] 测试不访问真实模型或外部网络
- [x] README/Release Notes 提醒导出和 excerpts 的敏感性

## 法律与元数据

- [x] 根目录包含完整 Apache-2.0 `LICENSE`
- [x] `NOTICE` 包含 EchoMind 和 `Copyright 2026 杨锦辰`
- [x] 后端 wheel/sdist metadata 为 Apache-2.0、作者为杨锦辰
- [x] 前端 `package.json` 标记 Apache-2.0 和作者
- [x] 第三方内嵌材料审查完成
- [x] 直接依赖许可证报告完成，传递依赖无 GPL/AGPL/SSPL/Commons Clause/UNKNOWN 阻断项

## 发布材料

- [x] 0.1.0 版本在包、Health、README、Changelog 和 Release Notes 中一致
- [x] `CHANGELOG.md` 和 `docs/RELEASE_NOTES_0.1.0.md` 已审阅
- [x] wheel、sdist 和前端 dist 在临时目录验证并清理
- [x] 源码归档模拟包含许可与社区文件且不含本地产物
- [x] 构建产物未上传到仓库、PyPI 或 npm

## 项目所有者手动发布

- [ ] 配置并复核远程仓库地址
- [ ] 推送 `main`
- [ ] 创建并推送 `v0.1.0` tag
- [ ] 创建 GitHub Release 并粘贴已审阅的发布说明
- [ ] 按需上传已复核产物
- [ ] 发布后从公开源码执行一次冒烟安装和 Health 检查
