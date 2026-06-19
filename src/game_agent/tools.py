from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


DATA_DIR = Path(__file__).resolve().parent / "data" / "knowledge"


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


class GuideSearchArgs(BaseModel):
    query: str = Field(..., description="玩家问题、游戏名称或攻略主题")
    game: str = Field(default="", description="可选游戏名称")
    top_k: int = Field(default=3, ge=1, le=5, description="返回条数")


def guide_search(query: str, game: str = "", top_k: int = 3) -> dict[str, Any]:
    """Retrieve local guide snippets as grounding context for the LLM."""
    guides = _load_json(DATA_DIR / "guides.json")
    if game:
        scoped = [item for item in guides if game in item.get("game", "") or item.get("game", "") in game]
        if scoped:
            guides = scoped

    query_text = f"{game} {query}".lower()

    def score(item: dict[str, Any]) -> int:
        text = f"{item.get('game', '')} {item.get('topic', '')} {item.get('content', '')}".lower()
        token_score = sum(1 for token in query_text.split() if token and token in text)
        char_score = sum(1 for char in query_text if "\u4e00" <= char <= "\u9fff" and char in text)
        return token_score + char_score

    ranked = [item for item in sorted(guides, key=score, reverse=True) if score(item) > 0][:top_k]
    return {
        "context_items": ranked,
        "note": "这些内容只是本地知识库参考，最终回答必须由本地大模型结合问题自然生成。",
    }


def strategy_tool(query: str, game: str = "", top_k: int = 3) -> dict[str, Any]:
    result = guide_search(query=query, game=game, top_k=top_k)
    result["tool_role"] = "攻略检索"
    return result


class BuildRecommendArgs(BaseModel):
    game: str = Field(..., description="游戏名称")
    play_style: str = Field(..., description="用户偏好的玩法，例如近战、远程、采集、速通")
    progress: str = Field(default="未知", description="当前游戏进度")


def build_recommend(game: str, play_style: str, progress: str = "未知") -> dict[str, Any]:
    builds = _load_json(DATA_DIR / "builds.json")
    candidates = [
        item
        for item in builds
        if game in item.get("game", "") or item.get("game", "") in game or play_style in item.get("style", "")
    ]
    return {
        "game": game,
        "play_style": play_style,
        "progress": progress,
        "context_items": candidates[:3],
        "note": "如本地模板为空或版本不匹配，请让大模型基于常识说明不确定性。",
    }


def equipment_tool(
    game: str,
    play_style: str = "",
    progress: str = "未知",
    favorite_character: str = "",
    current_goal: str = "",
) -> dict[str, Any]:
    result = build_recommend(game=game, play_style=play_style or "综合", progress=progress)
    result.update(
        {
            "tool_role": "配装推荐",
            "favorite_character": favorite_character,
            "current_goal": current_goal,
        }
    )
    return result


class ResourcePlanArgs(BaseModel):
    target: str = Field(..., description="目标资源或培养目标")
    available_minutes: int = Field(default=60, ge=10, le=300, description="可用时间")
    history: str = Field(default="", description="历史采集记录或用户偏好")


def resource_plan(target: str, available_minutes: int = 60, history: str = "") -> dict[str, Any]:
    resources = _load_json(DATA_DIR / "resources.json")
    scored = []
    for item in resources:
        name = item.get("name", "")
        score = 2 if name and (name in target or target in name) else 1
        scored.append((score, item))

    route = []
    used = 0
    total_yield = 0
    for _, item in sorted(
        scored,
        key=lambda pair: (
            pair[0],
            pair[1].get("yield", 0) / max(pair[1].get("minutes", 1), 1),
        ),
        reverse=True,
    ):
        minutes = int(item.get("minutes", 0))
        if minutes and used + minutes <= available_minutes:
            route.append(item)
            used += minutes
            total_yield += int(item.get("yield", 0))

    return {
        "target": target,
        "available_minutes": available_minutes,
        "history_considered": bool(history),
        "suggested_route": route,
        "estimated_yield": total_yield,
        "remaining_minutes": available_minutes - used,
        "note": "路线来自本地示例知识库，版本或地图变化时需要在回答中说明不确定性。",
    }


def resource_tool(target: str, available_minutes: int = 60, history: str = "") -> dict[str, Any]:
    result = resource_plan(target=target, available_minutes=available_minutes, history=history)
    result["tool_role"] = "资源规划"
    return result


class StorySimulateArgs(BaseModel):
    game: str = Field(..., description="游戏名称")
    choice: str = Field(..., description="剧情分支选择")
    goal: str = Field(default="获得稳定收益", description="玩家目标")


def story_simulate(game: str, choice: str, goal: str = "获得稳定收益") -> dict[str, Any]:
    conservative = any(word in choice for word in ["帮助", "合作", "保守", "存档", "观察"])
    return {
        "game": game,
        "choice": choice,
        "goal": goal,
        "risk_level": "低" if conservative else "中",
        "decision_context": "剧情选择可能影响阵营好感、奖励顺序或后续分支。建议先完成可逆支线，再推进不可逆主线节点。",
    }


def story_tool(game: str, choice: str, goal: str = "获得稳定收益") -> dict[str, Any]:
    result = story_simulate(game=game, choice=choice, goal=goal)
    result["tool_role"] = "剧情选择"
    return result


def rank_plan_tool(
    game: str,
    play_style: str = "",
    favorite_character: str = "",
    current_goal: str = "",
    game_stage: str = "",
) -> dict[str, Any]:
    return {
        "tool_role": "上分计划",
        "game": game,
        "play_style": play_style,
        "favorite_character": favorite_character,
        "current_goal": current_goal,
        "game_stage": game_stage,
        "plan_frame": [
            "确认主玩位置和2个备选位置，减少补位损耗。",
            "用3到5个高熟练英雄组成稳定英雄池。",
            "按复盘、练习、排位三个环节安排每日节奏。",
            "连败时停止排位，转为训练或复盘。",
        ],
        "risk_points": ["版本强势变化", "心态波动", "阵容缺控制或前排", "英雄熟练度不足"],
    }


def beginner_guide_tool(game: str, game_stage: str = "", current_goal: str = "") -> dict[str, Any]:
    return {
        "tool_role": "新手入门",
        "game": game,
        "game_stage": game_stage,
        "current_goal": current_goal,
        "steps": [
            "先理解核心循环和胜负条件。",
            "选择低门槛角色或路线建立正反馈。",
            "把资源优先投入到主线、基础装备和常用角色。",
            "每次游玩只设定一个可完成的小目标。",
        ],
        "avoid": ["过早追求高难配装", "平均培养过多角色", "跳过基础机制教学"],
    }


TOOLS = [
    StructuredTool.from_function(
        func=strategy_tool,
        name="strategy_tool",
        description="按任务类型检索攻略、机制、地图、道具和流程知识。",
    ),
    StructuredTool.from_function(
        func=equipment_tool,
        name="equipment_tool",
        description="按任务类型提供配装、出装、队伍或养成方向上下文。",
    ),
    StructuredTool.from_function(
        func=resource_tool,
        name="resource_tool",
        description="按任务类型规划资源采集、体力消耗、材料刷取路线。",
    ),
    StructuredTool.from_function(
        func=story_tool,
        name="story_tool",
        description="按任务类型分析剧情选择的收益、风险和后续影响。",
    ),
    StructuredTool.from_function(
        func=rank_plan_tool,
        name="rank_plan_tool",
        description="按玩家偏好、目标和阶段生成上分计划上下文。",
    ),
    StructuredTool.from_function(
        func=beginner_guide_tool,
        name="beginner_guide_tool",
        description="为新手入门任务生成基础步骤和避坑建议。",
    ),
    StructuredTool.from_function(
        func=guide_search,
        name="guide_search",
        description="检索游戏规则、道具、地图、任务流程和攻略知识库。",
        args_schema=GuideSearchArgs,
    ),
    StructuredTool.from_function(
        func=build_recommend,
        name="build_recommend",
        description="根据游戏、进度和玩法偏好提供配装上下文。",
        args_schema=BuildRecommendArgs,
    ),
    StructuredTool.from_function(
        func=resource_plan,
        name="resource_plan",
        description="规划资源采集路线、时间分配和预估收益。",
        args_schema=ResourcePlanArgs,
    ),
    StructuredTool.from_function(
        func=story_simulate,
        name="story_simulate",
        description="推演剧情分支风险、收益和行动顺序。",
        args_schema=StorySimulateArgs,
    ),
]

TOOL_REGISTRY = {tool.name: tool for tool in TOOLS}


def tool_invoke(tool_name: str, tool_params: dict[str, Any]) -> Any:
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOL_REGISTRY[tool_name].invoke(tool_params)
