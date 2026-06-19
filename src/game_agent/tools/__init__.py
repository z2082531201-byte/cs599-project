from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from .build_recommend_tool import build_recommend, equipment_tool
from .guide_search_tool import guide_search, strategy_tool
from .memory_tool import memory_tool, read_player_memory, save_player_memory
from .task_plan_tool import task_plan_tool


__all__ = [
    "beginner_guide_tool",
    "build_recommend",
    "equipment_tool",
    "guide_search",
    "memory_tool",
    "rank_plan_tool",
    "read_player_memory",
    "resource_plan",
    "resource_tool",
    "save_player_memory",
    "story_simulate",
    "story_tool",
    "strategy_tool",
    "task_plan_tool",
    "tool_invoke",
]


def resource_plan(target: str, available_minutes: int = 60, history: str = "") -> dict[str, Any]:
    """Legacy-compatible resource planner built on the new task planning style."""
    return {
        "tool": "resource_plan",
        "target": target,
        "available_minutes": available_minutes,
        "history_considered": bool(history),
        "suggested_route": [
            {"name": "高优先级材料/资源", "minutes": min(30, available_minutes), "yield": "优先满足当前目标"},
            {"name": "日常任务与体力消耗", "minutes": max(0, available_minutes - 30), "yield": "稳定积累通用资源"},
        ],
        "remaining_minutes": 0,
    }


def resource_tool(target: str, available_minutes: int = 60, history: str = "") -> dict[str, Any]:
    """Agent-facing alias for resource planning."""
    result = resource_plan(target=target, available_minutes=available_minutes, history=history)
    result["intent"] = "task_planning"
    return result


def story_simulate(game: str, choice: str, goal: str = "获得稳定收益") -> dict[str, Any]:
    """Legacy-compatible story choice simulator."""
    conservative = any(word in choice for word in ["帮助", "合作", "保守", "存档", "观察"])
    return {
        "tool": "story_simulate",
        "game": game,
        "choice": choice,
        "goal": goal,
        "risk_level": "低" if conservative else "中",
        "decision_context": "剧情选择可能影响阵营好感、奖励顺序或后续分支，建议先完成可逆内容再推进不可逆节点。",
    }


def story_tool(game: str, choice: str, goal: str = "获得稳定收益") -> dict[str, Any]:
    """Agent-facing alias for story decision analysis."""
    result = story_simulate(game=game, choice=choice, goal=goal)
    result["intent"] = "game_guide"
    return result


def rank_plan_tool(
    game: str,
    play_style: str = "",
    favorite_character: str = "",
    current_goal: str = "",
    game_stage: str = "",
) -> dict[str, Any]:
    """Generate a ranking plan context for competitive games."""
    return task_plan_tool(
        goal=current_goal or "稳定上分",
        game=game,
        play_style=play_style or favorite_character or game_stage,
        available_minutes=90,
    )


def beginner_guide_tool(game: str, game_stage: str = "", current_goal: str = "") -> dict[str, Any]:
    """Generate beginner onboarding steps for a selected game."""
    return {
        "tool": "beginner_guide_tool",
        "game": game,
        "game_stage": game_stage,
        "current_goal": current_goal,
        "steps": [
            "先理解核心循环和胜负条件。",
            "选择低门槛角色或路线建立正反馈。",
            "把资源优先投入主线、基础装备和常用角色。",
            "每次游玩只设定一个可以完成的小目标。",
        ],
    }


TOOL_FUNCTIONS = {
    "guide_search": guide_search,
    "strategy_tool": strategy_tool,
    "build_recommend": build_recommend,
    "equipment_tool": equipment_tool,
    "resource_plan": resource_plan,
    "resource_tool": resource_tool,
    "story_simulate": story_simulate,
    "story_tool": story_tool,
    "rank_plan_tool": rank_plan_tool,
    "beginner_guide_tool": beginner_guide_tool,
    "task_plan_tool": task_plan_tool,
    "memory_tool": memory_tool,
}


TOOLS = [
    StructuredTool.from_function(func=func, name=name, description=f"Game companion tool: {name}")
    for name, func in TOOL_FUNCTIONS.items()
]
TOOL_REGISTRY = {tool.name: tool for tool in TOOLS}


def tool_invoke(tool_name: str, tool_params: dict[str, Any]) -> Any:
    """Invoke a registered game companion tool by name."""
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOL_REGISTRY[tool_name].invoke(tool_params)
