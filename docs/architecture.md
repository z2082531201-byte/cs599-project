# Architecture Spec

## 1. 系统定位

本项目是面向《王者荣耀》玩家的 AI 游戏助手。目标不是普通聊天机器人，而是具备游戏教练、陪玩建议、英雄推荐、出装铭文建议、任务规划和对局复盘能力的 Agent 系统。

系统采用“确定性工具 + LLM 解释”的混合架构。涉及事实、英雄名单、位置筛选和推荐约束等高风险内容时，优先由本地知识库和工具服务给出结果；LLM 负责总结、解释和生成自然语言建议。

## 2. 分层架构

```text
用户层
  ↓
FastAPI Web UI / API
  ↓
Game Companion Agent
  ↓
工具服务层
  ├── 英雄推荐服务 hero_recommend_service.py
  ├── 攻略检索 guide_search_tool.py
  ├── 出装推荐 build_recommend_tool.py
  ├── 任务规划 task_plan_tool.py
  └── 记忆工具 memory_tool.py
  ↓
数据层
  ├── src/game_agent/knowledge/heroes.json
  ├── src/game_agent/knowledge/game_guides.json
  ├── src/game_agent/knowledge/equipments.json
  ├── player_memory.json
  ├── ChromaDB
  └── logs/
```

## 3. 核心模块

### 3.1 前端与接口层

`src/game_agent/api.py` 同时承担 FastAPI API 服务和内嵌 Web UI 页面输出。页面提供对话区、英雄推荐、热门出装、实用工具和快捷问题。

核心接口包括：

- `POST /api/chat`
- `GET /api/memory`
- `POST /api/memory`
- `GET /api/guides`
- `POST /api/plan`
- `POST /api/recommend`

### 3.2 Agent 核心

`src/game_agent/game_agent.py` 是当前王者荣耀助手的核心模块，负责：

- 固定王者荣耀上下文
- 识别用户意图
- 调用本地工具
- 读取玩家记忆
- 调用 DeepSeek API，保留 Ollama 本地模型备用
- 将回答整理为结构化 JSON

结构化返回字段：

```json
{
  "summary": "本次回答总结",
  "key_points": [
    {
      "tag": "英雄选择",
      "content": "优先选择版本强势且适合自己熟练度的英雄"
    }
  ],
  "details": "详细建议内容",
  "follow_up_questions": [],
  "recommendations": {
    "heroes": [],
    "builds": []
  }
}
```

### 3.3 英雄推荐硬过滤

`src/game_agent/hero_recommend_service.py` 是防止 LLM 幻觉的关键模块，读取 `src/game_agent/knowledge/heroes.json` 中的英雄数据。

推荐流程：

```text
用户问题
  ↓
infer_role 识别位置
  ↓
读取 src/game_agent/knowledge/heroes.json
  ↓
按 role / beginner / difficulty / play_style 筛选
  ↓
返回英雄列表
  ↓
LLM 只解释原因，不决定英雄名
```

约束规则：

- 打野问题只返回打野英雄
- 射手问题只返回射手英雄
- 辅助问题只返回辅助英雄
- 中路问题只返回中路或法师英雄
- 对抗路问题只返回对抗路或战士英雄

### 3.4 LLM 调用

LLM 调用位于 `src/game_agent/llm/`。

默认配置：

```env
LLM_PROVIDER=deepseek
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b

DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

系统默认使用 DeepSeek OpenAI Compatible API 调用云端模型；如需离线运行，可将 `LLM_PROVIDER` 改为 `ollama` 并启动本地 Ollama 服务。

## 4. 数据模型

### 4.1 英雄知识库

`src/game_agent/knowledge/heroes.json` 字段：

```json
{
  "name": "",
  "roles": [],
  "difficulty": 1,
  "beginner": true,
  "lane": "",
  "tags": []
}
```

### 4.2 玩家记忆

玩家记忆由 `player_memory.json` 和 Chroma 长期记忆共同支持：

- JSON 记忆：保存常用偏好、常玩角色、风格和目标
- Chroma 记忆：兼容旧版长期语义记忆检索

## 5. 可观测性

系统通过 `trace_id` 记录每次请求，日志保存在 `logs/` 中，可追踪：

- 意图识别结果
- 工具调用情况
- 记忆读取与写入
- LLM Provider
- 响应耗时

## 6. 测试策略

测试位于 `tests/`：

- API 测试：`tests/test_api.py`
- 工具测试：`tests/test_tools.py`
- 英雄推荐服务测试：`tests/test_hero_recommend_service.py`

重点测试用例：

- 打野推荐不能出现非打野英雄
- LLM 幻觉英雄名会被后端过滤
- `/api/chat` 必须返回结构化字段
- 旧接口保持兼容

## 7. GitHub 提交约束

仓库应保留课程要求的标准结构：

- `docs/`：项目报告和架构文档
- `src/`：项目源代码
- `README.md`：项目入口说明
- `.gitignore`：忽略缓存、日志、环境变量、虚拟环境和构建产物
- `LICENSE`：Public 仓库必须包含开源协议

不应提交 `.env`、`logs/`、`game_memory/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`、`.venv/` 等本地运行产物。
