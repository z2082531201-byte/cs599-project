from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.game_agent.hero_recommend_service import infer_role, recommend_heroes


PACKAGE_DIR = Path(__file__).resolve().parents[1]
CHARACTERS_FILE = PACKAGE_DIR / "knowledge" / "characters.json"
EQUIPMENTS_FILE = PACKAGE_DIR / "knowledge" / "equipments.json"


def _load_json(path: Path) -> list[dict[str, Any]]:
    """Load a JSON list from the companion knowledge base."""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def build_recommend(
    game: str,
    play_style: str = "",
    progress: str = "",
    favorite_character: str = "",
    current_goal: str = "",
) -> dict[str, Any]:
    """Recommend characters, builds, or lineups from local examples."""
    characters = _load_json(CHARACTERS_FILE)
    equipments = _load_json(EQUIPMENTS_FILE)
    query_text = f"{game} {play_style} {progress} {favorite_character} {current_goal}".lower()
    role = infer_role(f"{play_style} {favorite_character} {current_goal}")
    beginner = True if any(word in f"{play_style} {current_goal}" for word in ["新手", "容易上手", "简单", "入门"]) else None
    difficulty = 2 if beginner else None

    def score(item: dict[str, Any]) -> int:
        text = " ".join(str(value) for value in item.values()).lower()
        token_score = sum(1 for token in query_text.split() if token and token in text)
        char_score = sum(1 for char in query_text if "\u4e00" <= char <= "\u9fff" and char in text)
        game_bonus = 3 if game and game in item.get("game", "") else 0
        return token_score + char_score + game_bonus

    hero_hits = recommend_heroes(role=role, beginner=beginner, difficulty=difficulty, play_style=play_style, limit=3)
    character_hits = hero_hits or [item for item in sorted(characters, key=score, reverse=True) if score(item) > 0][:4]
    equipment_hits = [item for item in sorted(equipments, key=score, reverse=True) if score(item) > 0][:4]
    context_items = character_hits + equipment_hits
    if play_style and not any(item.get("style") == play_style for item in context_items):
        context_items.insert(
            0,
            {
                "game": game,
                "style": play_style,
                "content": f"围绕{play_style}玩法选择角色、装备或阵容，优先满足当前目标：{current_goal or '稳定提升'}。",
            },
        )
    return {
        "tool": "build_recommend_tool",
        "game": game,
        "play_style": play_style,
        "progress": progress,
        "favorite_character": favorite_character,
        "current_goal": current_goal,
        "role": role,
        "context_items": context_items[:4],
        "heroes": hero_hits,
        "characters": character_hits,
        "equipments": equipment_hits,
    }


def equipment_tool(
    game: str,
    play_style: str = "",
    progress: str = "",
    favorite_character: str = "",
    current_goal: str = "",
) -> dict[str, Any]:
    """Alias used by the agent when the intent is build_recommend."""
    result = build_recommend(
        game=game,
        play_style=play_style,
        progress=progress,
        favorite_character=favorite_character,
        current_goal=current_goal,
    )
    result["intent"] = "build_recommend"
    return result
