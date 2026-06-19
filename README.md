# AI游戏教练——王者荣耀智

## 项目简介

本项目是一款基于 Agentic AI 思想开发的AI游戏教练系统，面向《王者荣耀》游戏场景，为玩家提供英雄推荐、阵容分析、出装建议、攻略查询以及对局决策辅助等服务。

系统结合 DeepSeek 大语言模型、知识库检索、用户长期记忆和 ReAct 推理机制，实现从用户问题理解、知识获取到智能决策生成的完整闭环，帮助玩家提升游戏理解能力和实战水平。

---

## 方向

方向一：Agentic AI 原生开发

本项目以 AI Agent 为核心，采用 ReAct 推理模式构建电竞教练智能体，实现：

- 智能问答
- 英雄推荐
- 出装推荐
- 阵容分析
- 游戏攻略检索
- 历史对话管理
- 用户偏好记忆
- ReAct 推理过程展示

---

## 技术栈

### AI IDE

- Codex
- ChatGPT
- Cursor

### LLM

- DeepSeek API

### 后端框架

- FastAPI
- Uvicorn
- Pydantic

### Agent能力

- ReAct Reasoning
- Function Calling
- Memory Management

### 数据存储

- JSON Knowledge Base
- Local Memory
- Browser LocalStorage

### 测试工具

- Swagger UI
- Pytest
- Ruff

### 开发语言

- Python 3.11+

---

## 项目结构

```text
src/
└── game_agent/
    ├── api.py
    ├── game_agent.py
    ├── schemas.py
    ├── config.py
    ├── memory.py
    ├── local_memory.py
    ├── tracer.py
    ├── tools.py
    ├── hero_recommend_service.py
    │
    ├── llm/
    │   ├── client.py
    │   └── deepseek_client.py
    │
    ├── knowledge/
    │   ├── heroes.json
    │   ├── game_guides.json
    │   └── equipment.json
    │
    └── data/
```

### 模块职责

#### api.py

FastAPI接口入口，负责接收用户请求并返回结构化结果。

#### game_agent.py

Agent核心执行流程，负责：

- 用户问题处理
- 意图识别
- Prompt构建
- 工具调用
- 结果生成

#### hero_recommend_service.py

英雄推荐服务，实现英雄筛选和推荐逻辑。

#### memory.py

用户长期记忆管理模块。

#### local_memory.py

本地历史会话存储管理。

#### tracer.py

Trace日志记录与运行监控。

#### tools.py

工具调用管理模块。

#### llm/client.py

模型Provider路由。

#### llm/deepseek_client.py

DeepSeek API调用封装。

#### knowledge/

游戏知识库：

- 英雄知识库
- 游戏攻略知识库
- 装备知识库

---

## 环境搭建

### 1. 克隆项目

```bash
git clone <your_repo_url>
cd project
```

### 2. 创建虚拟环境

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

创建：

```text
.env
```

配置：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

⚠️ 请勿将 API Key 写入源码中。

---

## 启动步骤

启动FastAPI服务：

```bash
uvicorn src.game_agent.api:app --reload
```

启动成功后访问：

### 项目主页

```text
http://127.0.0.1:8000
```

### Swagger接口文档

```text
http://127.0.0.1:8000/docs
```

---

## 核心功能展示

### 英雄推荐

示例：

```text
推荐几个适合新手的打野英雄
```

输出：

- 赵云
- 典韦
- 阿古朵

并给出推荐理由。

### 出装推荐

示例：

```text
赵云怎么出装？
```

返回：

- 推荐装备
- 出装顺序
- 铭文搭配

### 阵容分析

示例：

```text
帮我分析这套阵容
```

返回：

- 阵容优点
- 阵容缺点
- 团战思路

### ReAct推理展示

系统支持展示：

```text
Thought
↓
Action
↓
Observation
```

帮助用户理解系统决策过程。

### 用户长期记忆

系统能够记录：

- 常用位置
- 偏好英雄
- 游戏风格

实现个性化推荐。

---

## API接口

### POST /api/chat

请求：

```json
{
  "message": "推荐一个适合新手的打野英雄"
}
```

响应：

```json
{
  "summary": "...",
  "key_points": [],
  "details": "...",
  "recommendations": [],
  "react_trace": {}
}
```

---

## 测试

### Swagger测试

访问：

```text
http://127.0.0.1:8000/docs
```

进行接口测试。

### 自动化测试

运行：

```bash
pytest
```

### 代码规范检查

运行：

```bash
ruff check .
```

---

## 项目状态

- [x] Proposal
- [x] MVP
- [x] Final

