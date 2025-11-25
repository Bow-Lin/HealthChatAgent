# HealthChatAgent 项目开发文档

## 项目概述

HealthChatAgent 是一个基于 AI 的健康咨询对话系统，采用 FastAPI 后端 + React 前端架构。项目通过多节点流程编排实现智能分诊、历史记录查询、AI 回复生成等功能，为用户提供医疗健康咨询服务。

## 架构设计

### 项目结构

```
HealthChatAgent/
├── app/                    # 后端应用
│   ├── main.py            # FastAPI 应用入口
│   ├── api/               # API 路由定义
│   ├── runtime/           # Agent 运行时逻辑
│   │   ├── flow.py        # 流程编排
│   │   └── nodes/         # 各功能节点
│   ├── services/          # 外部服务封装
│   ├── schemas/           # 数据模型定义
│   ├── db/                # 数据库相关
│   └── utils/             # 通用工具
├── frontend/              # 前端应用 (React + TypeScript)
└── test/                  # 测试代码
```

### 核心架构

- **Flow 引擎**: 基于 PocketFlow 实现的异步流程编排系统
- **Node 节点**: 功能模块化设计，包括分诊、历史查询、AI 调用等节点
- **API 层**: FastAPI 实现 RESTful API 接口
- **数据层**: SQLAlchemy + SQLModel 实现异步数据库操作
- **前端**: React + TypeScript 实现用户界面

## 节点设计

### 节点类型

1. **SafetyTriageNode (分诊节点)**
   - 功能: 评估咨询内容的安全性，判断紧急/非紧急情况
   - 路由: 根据评估结果路由到不同处理路径

2. **HistoryLookupNode (历史查询节点)**
   - 功能: 查询患者历史就诊记录
   - 路由: 根据是否有历史记录进行路由

3. **DeepSeekChatNode / QwenChatNode (AI 回复节点)**
   - 功能: 调用 DeepSeek 或 Qwen 模型生成回复
   - 支持: 非紧急情况的智能回复生成

4. **ReplyExtractNode (回复解析节点)**
   - 功能: 解析模型输出，提取追问和警告信息

5. **UrgentAdviceNode (紧急建议节点)**
   - 功能: 处理紧急情况，提供紧急医疗建议

6. **PersistNode (持久化节点)**
   - 功能: 保存消息记录和审计日志

### 流程编排

**临床对话流程 (make_clinical_flow_qwen)**:
```
triage → (urgent → urgent_advice → persist)
        → (ok → history_lookup → qwen → reply_extract → persist)
```

**紧急情况处理流程**:
- 分诊 → 紧急 → 紧急建议 → 持久化

**正常情况处理流程**:
- 分诊 → 正常 → 历史查询 → Qwen → 回复解析 → 持久化

## API 接口

### 用户管理

- `GET /api/users` - 获取用户列表/按名称搜索
- `POST /api/users` - 创建新用户

### 对话功能

- `GET /api/chat/history` - 获取用户对话历史
- `POST /api/chat` - 发送消息并获取 AI 回复

## 技术栈

### 后端技术

- **Python 3.12+**
- **FastAPI**: Web 框架
- **SQLModel + SQLAlchemy**: ORM 和数据库操作
- **PocketFlow**: 流程编排引擎
- **uv**: Python 项目管理工具

### 前端技术

- **React 19+**: 用户界面框架
- **TypeScript**: 类型安全
- **Vite**: 构建工具
- **Tailwind CSS**: 样式框架

### 数据库

- **SQLite**: 使用 aiosqlite 作为异步驱动

## 依赖管理

### 后端依赖 (pyproject.toml)

```toml
dependencies = [
    "aiosqlite>=0.21.0",
    "fastapi>=0.120.3",
    "httpx>=0.28.1",
    "pocketflow>=0.0.3",
    "pytest>=8.4.2",
    "sqlalchemy>=2.0.44",
    "sqlmodel>=0.0.27",
    "uvicorn[standard]>=0.38.0",
]
```

### 前端依赖 (package.json)

```json
"dependencies": {
  "react": "^19.1.1",
  "react-dom": "^19.1.1"
},
"devDependencies": {
  "@types/react": "^19.1.16",
  "@types/react-dom": "^19.1.9",
  "typescript": "~5.9.3",
  "vite": "^7.1.7",
  "tailwindcss": "^4.1.17"
}
```

## 开发命令

### 环境设置

```bash
# 安装 uv (如果未安装)
pip install uv

# 安装依赖
uv sync
```

### 数据库初始化

```bash
uv run python -c "import asyncio; from app.db.session import init_db; asyncio.run(init_db())"
```

### 启动服务

```bash
# 后端服务
uv run uvicorn app.main:app --reload --port 9000

# 前端服务 (在 frontend/ 目录下)
cd frontend
bun run dev
```

### 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest test/test_nodes/
```

## 开发实践

### 代码规范

- 使用类型提示 (Type Hints)
- 遵循 PEP 8 代码风格
- 使用 Pydantic 验证数据模型
- 异步编程模式

### 数据库设计

- 使用 SQLModel 定义 ORM 模型
- 支持多租户架构 (tenant_id)
- 异步数据库会话管理

### API 设计

- RESTful API 设计原则
- Pydantic 模型进行输入输出验证
- 统一的错误处理机制

### 测试策略

- 单元测试覆盖各个节点
- 集成测试验证流程编排
- 使用 pytest 和 pytest-asyncio

## 部署配置

### 后端

- 使用 Uvicorn 作为 ASGI 服务器
- 支持热重载开发模式
- 异步数据库连接池

### 前端

- Vite 构建工具
- 支持开发和生产构建
- TypeScript 类型检查

## 项目特点

1. **模块化架构**: 节点化设计，易于扩展和维护
2. **安全性**: 包含紧急情况处理和安全分诊机制
3. **可扩展性**: 支持多种 LLM 服务 (DeepSeek, Qwen)
4. **多租户**: 支持多租户数据隔离
5. **审计日志**: 完整的消息和操作记录
6. **异步处理**: 高性能异步架构

## 新增功能

- **iFlow 客户端**: 新增 `iflow_client.py`，支持调用心流 API 服务
- **英文注释**: 所有代码注释已改为英文，符合国际化开发标准