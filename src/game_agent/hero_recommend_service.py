from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


PACKAGE_DIR = Path(__file__).resolve().parent
HEROES_FILE = PACKAGE_DIR / "knowledge" / "heroes.json"

ROLE_ALIASES = {
    "打野": "打野",
    "野区": "打野",
    "刺客打野": "打野",
    "射手": "射手",
    "发育路": "射手",
    "adc": "射手",
    "辅助": "辅助",
    "游走": "辅助",
    "中路": "中路",
    "法师": "中路",
    "中单": "中路",
    "对抗路": "对抗路",
    "上路": "对抗路",
    "战士": "对抗路",
    "坦边": "对抗路",
}

BEGINNER_ROLE_PRIORITY = {
    "打野": ["典韦", "赵云", "铠", "娜可露露", "兰陵王", "孙悟空"],
    "射手": ["后羿", "鲁班七号", "狄仁杰", "孙尚香"],
    "辅助": ["蔡文姬", "张飞", "牛魔", "瑶"],
    "中路": ["妲己", "小乔", "王昭君", "沈梦溪"],
    "对抗路": ["亚瑟", "吕布", "夏侯惇", "铠"],
}


def load_heroes() -> list[dict[str, Any]]:
    """Load the curated Honor of Kings hero knowledge base."""
    if not HEROES_FILE.exists():
        return []
    data = json.loads(HEROES_FILE.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def infer_role(text: str) -> str:
    """Infer a strict lane/role from user wording."""
    lowered = text.lower()
    for alias, role in ROLE_ALIASES.items():
        if alias in text or alias in lowered:
            return role
    return ""


def normalize_role(role: str) -> str:
    """Normalize role aliases into the canonical filter value."""
    if not role:
        return ""
    return ROLE_ALIASES.get(role, ROLE_ALIASES.get(role.lower(), role))


def _role_matches(hero: dict[str, Any], role: str) -> bool:
    """Return True only when the hero is valid for the requested role."""
    if not role:
        return True
    roles = hero.get("roles", [])
    lane = hero.get("lane", "")
    if role == "中路":
        return "中路" in roles or "法师" in roles or lane == "中路"
    if role == "射手":
        return "射手" in roles or "发育路" in roles or lane == "发育路"
    if role == "辅助":
        return "辅助" in roles or lane == "游走"
    if role == "对抗路":
        return "对抗路" in roles or lane == "对抗路"
    return role in roles or lane == role


def _score_hero(hero: dict[str, Any], beginner: Optional[bool], difficulty: Optional[int], play_style: str) -> int:
    """Rank matching heroes while keeping role filtering deterministic."""
    score = 0
    if beginner is True and hero.get("beginner") is True:
        score += 8
    if beginner is False and hero.get("beginner") is False:
        score += 2
    hero_difficulty = int(hero.get("difficulty", 5))
    if difficulty is not None:
        score += max(0, 6 - abs(hero_difficulty - difficulty))
    else:
        score += max(0, 5 - hero_difficulty)

    style_text = play_style.lower()
    tags = [str(tag).lower() for tag in hero.get("tags", [])]
    roles = [str(role).lower() for role in hero.get("roles", [])]
    easy_request = any(word in play_style for word in ["容易上手", "简单", "新手", "入门", "容错"])
    if easy_request:
        if any(tag in {"操作简单", "简单", "新手", "容错高", "稳定"} for tag in hero.get("tags", [])):
            score += 8
        score += max(0, 4 - hero_difficulty)
    for token in [style_text, *style_text.split()]:
        if not token:
            continue
        if any(token in tag or tag in token for tag in tags):
            score += 4
        if any(token in role or role in token for role in roles):
            score += 2
    return score


def _reason_for(hero: dict[str, Any]) -> str:
    """Generate a short non-LLM reason from curated hero fields."""
    tags = hero.get("tags", [])
    tag_text = "、".join(str(tag) for tag in tags[:3])
    if hero.get("beginner"):
        return f"操作门槛低，{tag_text}，容错率更适合稳定上分。"
    return f"{tag_text}能力突出，但需要一定熟练度。"


def recommend_heroes(
    role: str = "",
    beginner: Optional[bool] = None,
    difficulty: Optional[int] = None,
    play_style: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Recommend heroes strictly from heroes.json.

    Role is a hard filter: jungle requests only return jungle heroes, marksman
    requests only return marksmen, support requests only return supports, and so on.
    """
    normalized_role = normalize_role(role)
    heroes = [hero for hero in load_heroes() if _role_matches(hero, normalized_role)]
    if beginner is not None:
        preferred = [hero for hero in heroes if bool(hero.get("beginner")) is beginner]
        if preferred:
            heroes = preferred
    if difficulty is not None:
        easier_or_equal = [hero for hero in heroes if int(hero.get("difficulty", 5)) <= difficulty]
        if easier_or_equal:
            heroes = easier_or_equal

    priority = BEGINNER_ROLE_PRIORITY.get(normalized_role, []) if beginner else []

    def sort_key(hero: dict[str, Any]) -> tuple[int, int, int, str]:
        name = str(hero.get("name", ""))
        priority_score = len(priority) - priority.index(name) if name in priority else 0
        return (
            priority_score,
            _score_hero(hero, beginner=beginner, difficulty=difficulty, play_style=play_style),
            -int(hero.get("difficulty", 5)),
            name,
        )

    ranked = sorted(heroes, key=sort_key, reverse=True)
    return [
        {
            "name": hero.get("name", ""),
            "role": normalized_role or hero.get("lane", ""),
            "lane": hero.get("lane", ""),
            "roles": hero.get("roles", []),
            "difficulty": hero.get("difficulty", 1),
            "beginner": bool(hero.get("beginner")),
            "tags": hero.get("tags", []),
            "reason": _reason_for(hero),
        }
        for hero in ranked[:limit]
    ]
