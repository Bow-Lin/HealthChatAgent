# HealthChatAgent

```
app/
├── main.py                      # FastAPI 入口（创建应用、注册路由、加载 Flow）
│
├── runtime/                     # Agent 运行时逻辑：节点 + 流程
│   ├── flow.py                  # Flow 编排（定义节点执行顺序）
│   └── nodes/                   # 各 Node 模块（PocketFlow 风格）
│       ├── triage.py            # SafetyTriageNode：分诊判断（紧急/非紧急）（已实现）
│       ├── history.py           # HistoryFetchNode：获取历史就诊摘要
│       ├── deepseek.py          # DeepSeekChatNode：调用 DeepSeek 生成回复（已实现）
│       ├── post.py              # PostprocessNode：解析模型输出、提取追问
│       └── persist.py           # PersistNode：写入消息和审计日志
│
├── services/                    # 外部依赖封装（DB、LLM、缓存、监控等）
│   ├── repo.py                  # 数据访问层：封装数据库 CRUD、事务、审计（已实现）
│   ├── deepseek_client.py       # DeepSeek API 封装（非流式/流式接口）（已实现）
│   └── __init__.py
│
├── schemas/                     # Pydantic 模型（输入输出）
│   ├── chat.py                  # ChatIn / ChatOut，用于 API 层
│   ├── encounter.py             # EncounterCreate / EncounterView
│   ├── patient.py               # PatientCreate / PatientView
│   └── __init__.py
│
├── db/                          # 数据表与数据库会话管理
│   ├── models.py                # ORM 模型定义（Patient、Encounter、Message、AuditLog）（已实现）
│   ├── session.py               # 异步数据库会话、engine、init_db()（已实现）
│   └── __init__.py
│
├── utils/                       # 通用工具与配置
│   ├── logging.py               # 统一日志封装（结构化 + request_id）
│   ├── config.py                # 环境变量加载与配置管理
│   ├── ids.py                   # UUID / ULID 生成工具
│   ├── security.py              # 加密/脱敏工具
│   └── __init__.py
│
└── tests/                       # 测试目录（pytest）
    ├── test_nodes/
    │   ├── test_triage.py       # triage 节点单测（已通过）
    │   └── ...
    ├── test_services/
    │   ├── test_repo.py         # repo 单测（已通过）
    │   └── ...
    ├── test_runtime/
    │   └── test_flow.py         # Flow 级联执行测试
    └── conftest.py              # pytest 全局配置（PYTHONPATH、fixtures）

```