from __future__ import annotations

from typing import Any


def task_plan_tool(
    goal: str,
    game: str = "",
    play_style: str = "",
    available_minutes: int = 60,
) -> dict[str, Any]:
    """Break a player goal into clear companion-style task steps."""
    base_steps = [
        {"step": "确认目标", "detail": f"把目标锁定为：{goal or '提升当前游戏进度'}。"},
        {"step": "检查资源", "detail": "查看体力、金币、材料、英雄/角色练度和今日可用时间。"},
        {"step": "优先主线", "detail": "先做对目标收益最高、时间最稳定的任务。"},
        {"step": "补足短板", "detail": "把剩余时间用于练习操作、刷材料或整理装备。"},
        {"step": "复盘调整", "detail": "结束前记录卡点，下次优先处理最影响进度的问题。"},
    ]
    if "上分" in goal or "排位" in goal:
        base_steps = [
            {"step": "热身", "detail": "先打一局匹配或训练营，确认手感和网络状态。"},
            {"step": "英雄池", "detail": "围绕主玩位置准备2到3个稳定英雄，避免临场乱选。"},
            {"step": "排位节奏", "detail": "每2局做一次短复盘，连败2局就暂停排位。"},
            {"step": "关键复盘", "detail": "重点看死亡原因、资源交换和团战站位。"},
        ]
    return {
        "tool": "task_plan_tool",
        "game": game,
        "goal": goal,
        "play_style": play_style,
        "available_minutes": available_minutes,
        "steps": base_steps,
    }
