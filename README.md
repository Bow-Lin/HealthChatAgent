# HealthChatAgent

```
app/
├── main.py                # FastAPI 入口
├── runtime/               # Agent runtime：流程与节点
│   ├── flow.py            # Flow 编排（定义节点执行顺序）
│   └── nodes/             # 各节点的实现（PocketFlow Node）
│       ├── triage.py
│       ├── history.py
│       ├── deepseek.py
│       ├── post.py
│       └── persist.py
├── services/              # 外部依赖（数据库、LLM 客户端）
│   ├── repo.py
│   ├── deepseek_client.py
│   └── ...
├── schemas/               # Pydantic 数据模型
│   ├── chat.py
│   ├── encounter.py
│   └── patient.py
├── db/                    # 数据表与会话
│   ├── models.py
│   └── session.py
└── utils/                 # 通用工具（日志、加密、配置）
```