from __future__ import annotations

import json
import uuid
from collections import defaultdict, deque
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .config import get_settings
from .llm import LLMError, generate_answer
from .memory import MemoryStore
from .schemas import ChatResponse
from .tools import tool_invoke
from .tracer import AgentTrace, TraceStore


SYSTEM_PROMPT = """你是一个专业的 AI 游玩决策助手。
你不是普通聊天机器人。
你需要结合游戏名称、玩家阶段、玩法偏好、常用角色、当前目标和历史记忆，为用户提供具体、可执行的游戏决策建议。
回答结构尽量使用：
1. 结论
2. 原因
3. 具体步骤
4. 注意事项
5. 后续建议

如果用户的问题不是游戏相关，也可以正常回答，但优先保持游戏助手身份。
不要把工具返回的 JSON、Python dict、matches、summary 或调试字段原样展示给用户。
如果用户请求外挂、作弊、破坏公平竞技或账号风险操作，要拒绝并给出合规替代建议。"""


MEMORY_TRIGGERS = ["记住", "我的偏好是", "我喜欢", "我常用", "以后推荐"]

TASK_TOOL_MAP = {
    "攻略检索": "strategy_tool",
    "配装推荐": "equipment_tool",
    "资源规划": "resource_tool",
    "剧情选择": "story_tool",
    "上分计划": "rank_plan_tool",
    "新手入门": "beginner_guide_tool",
}

SHORT_TERM_MEMORY: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=8))


class AgentState(TypedDict):
    user_query: str
    user_id: str
    game_name: str
    task_type: str
    game_stage: str
    play_style: str
    favorite_character: str
    current_goal: str
    trace_id: str
    short_memory: list[dict[str, str]]
    long_memory: list[str]
    tool_results: list[dict[str, Any]]
    final_answer: str
    memory_saved: bool
    trace: AgentTrace


def _should_save_memory(text: str) -> bool:
    return any(keyword in text for keyword in MEMORY_TRIGGERS)


def _tool_params(state: AgentState, tool_name: str) -> dict[str, Any]:
    game = state["game_name"] or "自定义游戏"
    if tool_name == "strategy_tool":
        return {"query": state["user_query"], "game": game, "top_k": 3}
    if tool_name == "equipment_tool":
        return {
            "game": game,
            "play_style": state["play_style"] or "综合",
            "progress": state["game_stage"] or "未知",
            "favorite_character": state["favorite_character"],
            "current_goal": state["current_goal"],
        }
    if tool_name == "resource_tool":
        target = state["current_goal"] or state["user_query"]
        return {"target": target, "available_minutes": 60, "history": "\n".join(state["long_memory"])}
    if tool_name == "story_tool":
        return {"game": game, "choice": state["user_query"], "goal": state["current_goal"] or "获得稳定收益"}
    if tool_name == "rank_plan_tool":
        return {
            "game": game,
            "play_style": state["play_style"],
            "favorite_character": state["favorite_character"],
            "current_goal": state["current_goal"],
            "game_stage": state["game_stage"],
        }
    if tool_name == "beginner_guide_tool":
        return {"game": game, "game_stage": state["game_stage"], "current_goal": state["current_goal"]}
    return {}


def load_memory_node(state: AgentState) -> dict[str, Any]:
    short_memory = list(SHORT_TERM_MEMORY[state["user_id"]])
    memory_query = "\n".join(
        part
        for part in [
            state["game_name"],
            state["task_type"],
            state["game_stage"],
            state["play_style"],
            state["favorite_character"],
            state["current_goal"],
            state["user_query"],
        ]
        if part
    )
    long_memory = MemoryStore().query(state["user_id"], memory_query, limit=5)
    state["trace"].add(
        "load_memory",
        {"short_count": len(short_memory), "long_count": len(long_memory), "memory_used": bool(long_memory)},
    )
    return {"short_memory": short_memory, "long_memory": long_memory}


def call_tools_node(state: AgentState) -> dict[str, Any]:
    tool_name = TASK_TOOL_MAP.get(state["task_type"])
    tool_results: list[dict[str, Any]] = []

    if not tool_name:
        state["trace"].add("tool_skip", {"reason": "普通问答不需要工具", "task_type": state["task_type"]})
        return {"tool_results": tool_results}

    params = _tool_params(state, tool_name)
    try:
        result = tool_invoke(tool_name, params)
        item = {"tool_name": tool_name, "tool_params": params, "result": result}
        tool_results.append(item)
        state["trace"].add("tool_call", item)
    except Exception as exc:
        item = {"tool_name": tool_name, "tool_params": params, "error": str(exc)}
        tool_results.append(item)
        state["trace"].add("tool_error", item)

    return {"tool_results": tool_results}


def _profile_context(state: AgentState) -> str:
    return "\n".join(
        [
            f"当前游戏：{state['game_name'] or '未指定'}",
            f"任务类型：{state['task_type'] or '普通问答'}",
            f"用户ID：{state['user_id']}",
            f"游戏阶段：{state['game_stage'] or '未填写'}",
            f"偏好玩法：{state['play_style'] or '未填写'}",
            f"常用角色/英雄：{state['favorite_character'] or '未填写'}",
            f"当前目标：{state['current_goal'] or '未填写'}",
        ]
    )


def _build_messages(state: AgentState) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({"role": "system", "content": "玩家档案与任务上下文：\n" + _profile_context(state)})

    if state["long_memory"]:
        messages.append(
            {
                "role": "system",
                "content": "以下是该用户的长期记忆，仅在相关时参考，不要机械复述：\n"
                + "\n".join(f"- {item}" for item in state["long_memory"]),
            }
        )

    if state["tool_results"]:
        messages.append(
            {
                "role": "system",
                "content": "以下是本地游戏工具提供的参考资料。请吸收为自然语言建议，不要输出 JSON：\n"
                + json.dumps(state["tool_results"], ensure_ascii=False, indent=2),
            }
        )

    messages.extend(state["short_memory"])
    messages.append({"role": "user", "content": state["user_query"]})
    return messages


def generate_answer_node(state: AgentState) -> dict[str, Any]:
    try:
        answer = generate_answer(_build_messages(state))
        state["trace"].add("llm_answer", {"status": "ok", "chars": len(answer)})
    except LLMError as exc:
        answer = str(exc)
        state["trace"].add("llm_error", {"error": answer})
    except Exception as exc:
        answer = f"系统处理失败：{exc}"
        state["trace"].add("unexpected_error", {"error": answer})
    return {"final_answer": answer}


def save_memory_node(state: AgentState) -> dict[str, Any]:
    SHORT_TERM_MEMORY[state["user_id"]].append({"role": "user", "content": state["user_query"]})
    SHORT_TERM_MEMORY[state["user_id"]].append({"role": "assistant", "content": state["final_answer"]})

    memory_saved = False
    if _should_save_memory(state["user_query"]):
        MemoryStore().add(
            state["user_id"],
            "\n".join(
                [
                    f"游戏：{state['game_name'] or '未指定'}",
                    f"阶段：{state['game_stage'] or '未填写'}",
                    f"偏好玩法：{state['play_style'] or '未填写'}",
                    f"常用角色/英雄：{state['favorite_character'] or '未填写'}",
                    f"当前目标：{state['current_goal'] or '未填写'}",
                    f"用户记忆内容：{state['user_query']}",
                ]
            ),
            memory_type="preference",
        )
        memory_saved = True

    state["trace"].add("save_memory", {"user_id": state["user_id"], "memory_saved": memory_saved})
    TraceStore().save(state["trace"])
    return {"trace": state["trace"], "memory_saved": memory_saved}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("load_memory", load_memory_node)
    graph.add_node("call_tools", call_tools_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("save_memory", save_memory_node)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "call_tools")
    graph.add_edge("call_tools", "generate_answer")
    graph.add_edge("generate_answer", "save_memory")
    graph.add_edge("save_memory", END)
    return graph.compile()


AGENT_WORKFLOW = build_graph()


def user_chat(
    user_query: str,
    user_id: str = "demo_user",
    game_name: str = "",
    task_type: str = "普通问答",
    game_stage: str = "",
    play_style: str = "",
    favorite_character: str = "",
    current_goal: str = "",
) -> ChatResponse:
    trace_id = uuid.uuid4().hex
    trace = AgentTrace(trace_id=trace_id)
    initial: AgentState = {
        "user_query": user_query,
        "user_id": user_id,
        "game_name": game_name,
        "task_type": task_type or "普通问答",
        "game_stage": game_stage,
        "play_style": play_style,
        "favorite_character": favorite_character,
        "current_goal": current_goal,
        "trace_id": trace_id,
        "short_memory": [],
        "long_memory": [],
        "tool_results": [],
        "final_answer": "",
        "memory_saved": False,
        "trace": trace,
    }
    result = AGENT_WORKFLOW.invoke(initial)
    tool_results = result.get("tool_results", [])
    tool_names = [item.get("tool_name", "") for item in tool_results if item.get("tool_name")]
    long_memory = result.get("long_memory", [])
    return ChatResponse(
        answer=result["final_answer"],
        trace_id=trace_id,
        tool_used=bool(tool_results),
        tool_name=", ".join(tool_names),
        memory_used=bool(long_memory),
        memory_saved=bool(result.get("memory_saved", False)),
        llm_provider=get_settings().llm_provider.strip().lower() or "ollama",
    )
