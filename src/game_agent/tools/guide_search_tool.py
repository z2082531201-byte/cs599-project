from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = PACKAGE_DIR / "knowledge" / "game_guides.json"


def _load_guides() -> list[dict[str, Any]]:
    """Load local guide documents from the expandable JSON knowledge base."""
    if not KNOWLEDGE_FILE.exists():
        return []
    return json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))


def guide_search(query: str, game: str = "", top_k: int = 3) -> dict[str, Any]:
    """Search local game guide snippets with simple keyword scoring."""
    guides = _load_guides()
    query_text = f"{game} {query}".lower()

    def score(item: dict[str, Any]) -> int:
        text = f"{item.get('game', '')} {item.get('topic', '')} {item.get('content', '')}".lower()
        token_score = sum(1 for token in query_text.split() if token and token in text)
        char_score = sum(1 for char in query_text if "\u4e00" <= char <= "\u9fff" and char in text)
        game_bonus = 3 if game and game in item.get("game", "") else 0
        return token_score + char_score + game_bonus

    ranked = [item for item in sorted(guides, key=score, reverse=True) if score(item) > 0]
    return {
        "tool": "guide_search_tool",
        "context_items": ranked[:top_k],
        "note": "本地攻略知识库结果仅作参考，最终建议需要结合玩家上下文生成。",
    }


def strategy_tool(query: str, game: str = "", top_k: int = 3) -> dict[str, Any]:
    """Alias used by the agent when the intent is game_guide."""
    result = guide_search(query=query, game=game, top_k=top_k)
    result["intent"] = "game_guide"
    return result
