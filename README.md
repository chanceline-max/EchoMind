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

当前已完成 **阶段 0：设计文档审查**，等待执行阶段 1。本仓库现阶段只包含文档和基础目录，不包含可运行的业务功能。历史 `mind-map` 星图原型不属于 EchoMind 正式架构。

## 计划中的本地启动方式

以下命令是目标开发体验，需在阶段 1 工程骨架完成后才可使用；当前不宣称已经可运行。

```powershell
# 后端（计划）
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
fastapi dev src/echomind/main.py

# 前端（计划）
cd frontend
npm install
npm run dev
```

## 计划中的测试方式

```powershell
cd backend
pytest
ruff check .
mypy src

cd ..\frontend
npm test
npm run typecheck
npm run test:e2e
```

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
└── tests/                   # 跨端契约和端到端测试
```

详细结构见 [架构文档](docs/ARCHITECTURE.md)。

## 隐私说明

EchoMind 默认仅绑定本机、使用本地 SQLite、关闭遥测，并且不会默认把聊天记录发送给任何第三方。真实聊天文件、数据库、生成档案和 `.env` 均被 Git 忽略。SQLite 默认并不提供应用级静态加密，这是 MVP 必须明确展示的限制；敏感数据应保存在受保护的设备和账户下。

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

项目处于早期设计阶段。文档中的“计划”“目标”和“验收标准”不代表功能已经实现或测试通过。
