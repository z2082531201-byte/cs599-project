# Architecture Spec

## 1. 系统定位

本项目是面向《王者荣耀》玩家开发的 AI 游戏教练系统，旨在为玩家提供智能问答、英雄推荐、出装建议、阵容分析以及游戏攻略辅助服务。

系统并非通用聊天机器人，而是围绕《王者荣耀》游戏场景构建的垂直领域 Agent 应用。系统采用“知识库 + 工具服务 + 大语言模型”的混合架构，通过本地知识库提供可靠游戏知识，通过工具模块完成规则约束和推荐筛选，再结合 DeepSeek 大模型生成自然语言解释和个性化建议，从而降低模型幻觉带来的影响，提高回答质量和可信度。

---

## 2. 分层架构

```text
用户层
  ↓
Web UI / FastAPI API
  ↓
Game Agent
  ↓
工具服务层
  ├── hero_recommend_service.py
  ├── tools.py
  ├── memory.py
  ├── local_memory.py
  └── tracer.py
  ↓
模型层
  ├── llm/client.py
  └── llm/deepseek_client.py
  ↓
数据层
  ├── knowledge/heroes.json
  ├── knowledge/game_guides.json
  ├── knowledge/equipment.json
  ├── player_memory.json
  └── logs/
```

系统采用模块化设计，各层职责明确。用户请求首先进入 FastAPI 接口层，然后由 Agent 核心进行处理，必要时调用工具模块和知识库数据，最终通过 DeepSeek 模型生成结构化结果并返回前端展示。

---

## 3. 核心模块

### 3.1 前端与接口层

`src/game_agent/api.py` 是系统接口入口，同时负责 FastAPI 服务和 Web UI 页面交互。

主要功能包括：

* 接收用户问题
* 调用 Agent 服务
* 返回结构化结果
* 提供 Swagger 接口测试
* 管理历史会话数据

核心接口：

* `POST /api/chat`
* `GET /docs`
* `GET /health`

其中 `/api/chat` 是系统核心业务接口。

---

### 3.2 Agent 核心

`src/game_agent/game_agent.py` 是整个系统的核心模块。

主要职责包括：

* 构建王者荣耀游戏上下文
* 用户问题分析
* 意图识别
* 用户记忆读取
* 知识库检索
* 工具调用
* DeepSeek API 调用
* ReAct 推理过程生成
* 结构化结果输出

系统返回统一 JSON 格式：

```json
{
  "summary": "本次回答总结",
  "key_points": [],
  "details": "详细建议内容",
  "follow_up_questions": [],
  "recommendations": {
    "heroes": [],
    "builds": []
  },
  "react_trace": {}
}
```

其中 react_trace 用于记录系统推理过程，提升回答可解释性。

---

### 3.3 英雄推荐服务

`src/game_agent/hero_recommend_service.py` 是系统中最重要的规则约束模块。

主要作用：

* 防止模型幻觉
* 保证推荐英雄真实存在
* 根据位置和难度筛选英雄

推荐流程如下：

```text
用户问题
   ↓
意图识别
   ↓
识别位置（打野/射手/辅助/中路/对抗路）
   ↓
读取 heroes.json
   ↓
按角色属性筛选
   ↓
返回候选英雄
   ↓
DeepSeek 生成解释说明
```

约束规则：

* 打野问题仅推荐打野英雄
* 射手问题仅推荐射手英雄
* 辅助问题仅推荐辅助英雄
* 中路问题仅推荐法师英雄
* 对抗路问题仅推荐战士英雄

---

### 3.4 LLM 调用模块

模型调用位于：

```text
src/game_agent/llm/
```

包含：

```text
client.py
deepseek_client.py
```

默认配置：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

系统采用 DeepSeek OpenAI Compatible API 进行调用，实现自然语言生成和游戏决策解释功能。

---

## 4. 数据模型

### 4.1 英雄知识库

英雄知识库存储于：

```text
src/game_agent/knowledge/heroes.json
```

主要字段：

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

用于英雄推荐和阵容分析。

---

### 4.2 游戏知识库

系统维护以下知识文件：

```text
knowledge/
├── heroes.json
├── game_guides.json
└── equipment.json
```

分别用于：

* 英雄信息查询
* 游戏攻略检索
* 出装推荐生成

---

### 4.3 玩家记忆

玩家长期偏好保存在：

```text
player_memory.json
```

主要记录：

* 常用位置
* 偏好英雄
* 游戏风格
* 历史偏好

用于个性化推荐和连续对话支持。

---

## 5. 可观测性

系统通过 `trace_id` 对每次请求进行唯一标识。

日志信息保存在：

```text
logs/
```

记录内容包括：

* 用户请求
* 意图识别结果
* 工具调用过程
* DeepSeek 响应
* ReAct 推理链
* 接口执行耗时

通过日志机制可实现问题追踪和性能分析。

---

## 6. 测试策略

系统测试位于：

```text
tests/
```

主要包括：

* API接口测试
* Agent功能测试
* 英雄推荐测试
* 工具调用测试
* ReAct输出测试

重点验证内容：

* 英雄推荐结果正确性
* 知识库检索准确性
* DeepSeek接口调用成功率
* ReAct推理链输出完整性
* /api/chat接口结构化响应正确性

---


