from __future__ import annotations

import json
import re
import uuid
from typing import Any

from .config import get_settings
from .llm import LLMError, generate_answer
from .local_memory import LocalPlayerMemory
from .hero_recommend_service import infer_role, recommend_heroes
from .tools import build_recommend, guide_search, memory_tool, task_plan_tool


KING_GAME = "王者荣耀"

SYSTEM_PROMPT = """你是“AI游戏助手 👑 王者荣耀”，只服务王者荣耀。
你的身份是王者荣耀陪玩/教练：说话自然、简洁、有重点，像靠谱队友一样给建议。

回答要求：
1. 永远围绕王者荣耀回答，不要切换到其他游戏。
2. 不要长篇废话，优先给玩家能马上执行的建议。
3. 每次回答必须总结重点。
4. 每次回答必须给 3-5 个下一步追问建议。
5. 可以讲英雄、分路、打野节奏、Gank、资源控制、出装铭文、阵容搭配、逆风处理、对局复盘。
6. 不确定版本信息时必须提醒：具体以当前游戏版本为准。
7. 英雄推荐名单必须以系统工具给出的 heroes 为准，禁止自由编造英雄名。
8. 不要原样输出工具 JSON。遇到外挂、作弊、代练、破坏公平竞技或账号风险操作时，要拒绝并给出合规替代建议。
"""


DEFAULT_FOLLOW_UPS = [
    "推荐几个当前版本强势英雄",
    "怎么提升打野意识？",
    "如何提高Gank成功率？",
    "逆风局应该怎么办？",
    "帮我推荐出装铭文",
]

DEFAULT_HEROES = recommend_heroes(role="打野", beginner=True, difficulty=2, play_style="容易上手", limit=3)

DEFAULT_BUILDS = [
    {"hero": "澜", "build": "追击刀锋、抵抗之靴、暗影战斧、宗师之力、破军、名刀司命"},
    {"hero": "赵云", "build": "巨人之握、抵抗之靴、暗影战斧、冰痕之握、魔女斗篷、血魔之怒"},
    {"hero": "娜可露露", "build": "追击刀锋、抵抗之靴、暗影战斧、破军、碎星锤、名刀司命"},
]

MEMORY_TRIGGERS = ["记住", "我的偏好是", "我喜欢", "我常用", "以后推荐"]


def detect_intent(message: str, requested_intent: str = "") -> str:
    """Classify a 王者荣耀 player request into one companion-agent intent."""
    if requested_intent:
        return requested_intent
    text = message.lower()
    if any(word in message for word in ["复盘", "这一局", "输在哪里", "失误", "对局", "战绩"]):
        return "match_review"
    if any(word in message for word in ["装备", "出装", "铭文", "配装", "阵容", "英雄推荐", "练什么"]):
        return "build_recommend"
    if any(word in message for word in ["规划", "路线", "今日任务", "计划", "上分", "目标"]):
        return "task_planning"
    if any(word in message for word in ["攻略", "怎么打", "机制", "意识", "Gank", "gank", "逆风"]):
        return "game_guide"
    if any(word in message for word in ["梯队", "版本", "资料", "查询"]):
        return "knowledge_search"
    if any(word in text for word in ["hi", "hello"]) or any(word in message for word in ["你好", "陪我", "聊聊"]):
        return "casual_chat"
    return "casual_chat"


def should_save_memory(message: str) -> bool:
    """Detect whether the player's message should be remembered."""
    return any(trigger in message for trigger in MEMORY_TRIGGERS)


def _select_tool(intent: str, context: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    """Call a deterministic local tool before asking the LLM when useful."""
    message = context.get("message", "")
    play_style = context.get("style", "") or memory.get("play_style", "")
    character = context.get("character", "") or memory.get("favorite_character", "")
    goal = context.get("goal", "") or memory.get("goal", "") or message

    if intent in {"game_guide", "knowledge_search"}:
        return guide_search(query=message, game=KING_GAME, top_k=3)
    if intent == "build_recommend":
        return build_recommend(
            game=KING_GAME,
            play_style=play_style or message,
            favorite_character=character,
            current_goal=goal,
        )
    if intent in {"task_planning", "match_review"}:
        return task_plan_tool(goal=goal, game=KING_GAME, play_style=play_style or "上分", available_minutes=90)
    return {}


def _build_messages(
    context: dict[str, Any],
    intent: str,
    memory: dict[str, Any],
    tool_result: dict[str, Any],
) -> list[dict[str, str]]:
    """Build the final prompt for the local model."""
    companion_context = {
        "game": KING_GAME,
        "intent": intent,
        "player_message": context.get("message", ""),
        "player_memory": memory,
        "tool_result": tool_result,
        "output_contract": {
            "summary": "1-2句话总结核心结论",
            "key_points": [{"tag": "标签", "content": "短句要点"}],
            "details": "简洁实用的详细建议",
            "follow_up_questions": ["3-5个下一步问题"],
        },
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": "请先按王者荣耀教练思路回答，再尽量用 JSON 对象表达；如果不能严格 JSON，也要保持分段清晰：\n"
            + json.dumps(companion_context, ensure_ascii=False, indent=2),
        },
        {"role": "user", "content": context.get("message", "")},
    ]


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Try to parse a JSON object from model output."""
    stripped = text.strip()
    candidates = [stripped]
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_answer_contract(parsed: dict[str, Any]) -> dict[str, Any]:
    """Unwrap the actual UI answer when the model echoes the prompt context."""
    answer_keys = {"summary", "key_points", "details", "follow_up_questions", "recommendations"}
    if answer_keys.intersection(parsed):
        return parsed

    output_contract = parsed.get("output_contract")
    if isinstance(output_contract, dict):
        return output_contract

    answer = parsed.get("answer")
    if isinstance(answer, dict):
        return _extract_answer_contract(answer)
    if isinstance(answer, str):
        nested = _extract_json_object(answer)
        if nested:
            return _extract_answer_contract(nested)

    return {}


def _fallback_text(raw_answer: str, parsed: dict[str, Any]) -> str:
    """Use readable text as fallback instead of dumping raw JSON into the UI."""
    if parsed:
        parts = [
            str(parsed.get("summary", "")).strip(),
            str(parsed.get("details", "")).strip(),
        ]
        points = parsed.get("key_points")
        if isinstance(points, list):
            for point in points:
                if isinstance(point, dict):
                    parts.append(str(point.get("content", "")).strip())
                else:
                    parts.append(str(point).strip())
        readable = " ".join(part for part in parts if part)
        if readable:
            return readable

    if _extract_json_object(raw_answer):
        return "这次建议已经整理成结构化卡片，重点看总结、核心要点和详细建议。"
    return raw_answer


def _split_sentences(text: str) -> list[str]:
    """Split Chinese/English text into short readable sentences."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    pieces = re.split(r"(?<=[。！？!?；;])\s*|\n+", cleaned)
    return [piece.strip(" -0123456789.、") for piece in pieces if piece.strip()]


def _guess_tag(content: str) -> str:
    """Pick a 王者荣耀 coaching tag for a key point."""
    tag_rules = [
        ("英雄选择", ["英雄", "澜", "赵云", "娜可露露", "镜", "兰陵王"]),
        ("开局思路", ["开局", "第一波", "前期", "一级"]),
        ("刷野路线", ["刷野", "野区", "红开", "蓝开"]),
        ("Gank时机", ["Gank", "gank", "抓", "支援"]),
        ("资源控制", ["龙", "暴君", "主宰", "资源", "河道"]),
        ("团队配合", ["队友", "团战", "阵容", "配合"]),
        ("出装铭文", ["出装", "铭文", "装备"]),
        ("逆风处理", ["逆风", "守塔", "止损"]),
    ]
    for tag, keywords in tag_rules:
        if any(keyword in content for keyword in keywords):
            return tag
    return "实战建议"


def _normalize_key_points(items: Any, fallback_text: str) -> list[dict[str, str]]:
    """Normalize model or fallback content into 4-6 tagged key points."""
    points: list[dict[str, str]] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                content = str(item.get("content", "")).strip()
                tag = str(item.get("tag", "")).strip() or _guess_tag(content)
            else:
                content = str(item).strip()
                tag = _guess_tag(content)
            if content:
                points.append({"tag": tag, "content": content[:80]})
    if not points:
        for sentence in _split_sentences(fallback_text)[:6]:
            points.append({"tag": _guess_tag(sentence), "content": sentence[:80]})
    defaults = [
        {"tag": "开局思路", "content": "先稳住发育和视野，不要为了硬抓人断掉自己的节奏。"},
        {"tag": "资源控制", "content": "暴君、主宰和敌方野区资源要提前看线权再动。"},
        {"tag": "团队配合", "content": "多围绕有控制或有爆发的队友打联动。"},
        {"tag": "逆风处理", "content": "逆风先清线守塔，少接无视野团战，等关键装备成型。"},
    ]
    for item in defaults:
        if len(points) >= 4:
            break
        points.append(item)
    return points[:6]


def _normalize_follow_ups(items: Any) -> list[str]:
    """Return 3-5 clean next-question prompts."""
    questions = [str(item).strip() for item in items or [] if str(item).strip()] if isinstance(items, list) else []
    for question in DEFAULT_FOLLOW_UPS:
        if question not in questions:
            questions.append(question)
        if len(questions) >= 5:
            break
    return questions[:5]


def format_companion_answer(
    raw_answer: str,
    intent: str,
    tool_result: dict[str, Any],
    user_message: str = "",
) -> dict[str, Any]:
    """Convert raw LLM text into UI-friendly 王者荣耀 response sections."""
    parsed = _extract_answer_contract(_extract_json_object(raw_answer) or {})
    fallback_text = _fallback_text(raw_answer, parsed)
    summary = str(parsed.get("summary", "")).strip()
    details = str(parsed.get("details", "")).strip()
    if not summary:
        sentences = _split_sentences(fallback_text)
        summary = " ".join(sentences[:2])[:140] or "这局思路先别乱，优先围绕发育、节奏和关键资源做决策。"
    if not details:
        details = fallback_text.strip()
    if "具体以当前游戏版本为准" not in details:
        details = f"{details}\n\n具体以当前游戏版本为准。"

    recommendations = parsed.get("recommendations") if isinstance(parsed.get("recommendations"), dict) else {}
    # Hero names are never trusted from the LLM. They must come from heroes.json through the recommendation service.
    request_text = f"{user_message} {raw_answer}"
    role = tool_result.get("role") or infer_role(request_text)
    heroes = tool_result.get("heroes") or recommend_heroes(
        role=role or "打野",
        beginner=True if any(word in request_text for word in ["容易上手", "新手", "简单"]) else None,
        difficulty=2 if any(word in request_text for word in ["容易上手", "新手", "简单"]) else None,
        play_style=request_text,
        limit=3,
    )
    builds = recommendations.get("builds") if isinstance(recommendations, dict) else []
    if not heroes:
        heroes = DEFAULT_HEROES
    if not builds:
        builds = tool_result.get("equipments") or DEFAULT_BUILDS

    return {
        "summary": summary,
        "key_points": _normalize_key_points(parsed.get("key_points"), fallback_text),
        "details": details[:1200],
        "follow_up_questions": _normalize_follow_ups(parsed.get("follow_up_questions")),
        "recommendations": {"heroes": heroes[:3], "builds": builds[:3]},
    }


def build_react_trace(
    intent: str,
    formatted: dict[str, Any],
    tool_result: dict[str, Any],
    message: str,
) -> dict[str, str]:
    """Create a compact ReAct trace for coach reasoning visualization."""
    summary = formatted.get("summary", "")
    tool_name = tool_result.get("tool", "") if tool_result else ""
    points = formatted.get("key_points") or []
    first_point = points[0].get("content", "") if points and isinstance(points[0], dict) else summary

    if any(word in message for word in ["开团", "团战", "强开"]):
        action = "先判断敌方关键控制和我方跟进距离，条件不足时选择拉扯或反打。"
        observation = "如果无视野强行开团，容易被反手控制，团战胜率会明显下降。"
    elif any(word in message for word in ["抓", "Gank", "gank"]):
        action = "优先抓压线过深、无位移或关键技能刚交过的敌方核心位。"
        observation = "成功抓人后可以转控龙或推塔；失败则要立即回到刷野节奏止损。"
    elif any(word in message for word in ["逆风", "劣势", "落后"]):
        action = "先清线守塔、补视野、避开无意义正面团，等待装备和人数差反打。"
        observation = "继续接无准备团会扩大经济差，稳住兵线能保留翻盘窗口。"
    elif tool_name:
        action = f"调用 {tool_name} 获取确定性信息，再结合玩家问题生成策略。"
        observation = "工具结果可以降低英雄推荐和路线规划的幻觉风险。"
    else:
        action = "根据当前问题直接给出王者荣耀教练建议，并提示下一步补充信息。"
        observation = "信息越完整，后续建议越能贴近当前对局。"

    thought = first_point or "先判断当前局势、英雄定位、敌方风险点，再选择行动优先级。"
    if intent:
        thought = f"识别为 {intent} 场景。{thought}"
    return {
        "thought": thought[:180],
        "action": action,
        "observation": observation,
    }


def chat_with_companion(context: dict[str, Any]) -> dict[str, Any]:
    """Run the full companion-agent flow and return API-ready metadata."""
    trace_id = uuid.uuid4().hex
    user_id = context.get("user_id") or "honor_user"
    message = context.get("message") or ""
    context = {**context, "game": KING_GAME, "user_id": user_id}
    intent = detect_intent(message, context.get("intent", ""))

    memory_store = LocalPlayerMemory()
    existing_memory = memory_store.get(user_id)
    memory_saved = False

    profile_update = {
        "favorite_game": KING_GAME,
        "favorite_character": context.get("character", ""),
        "play_mode": context.get("mode", ""),
        "play_style": context.get("style", ""),
        "goal": context.get("goal", ""),
    }
    if any(profile_update.values()):
        existing_memory = memory_store.update(user_id, profile_update)

    if should_save_memory(message):
        existing_memory = memory_store.append_note(user_id, message)
        memory_saved = True

    tool_result = _select_tool(intent=intent, context=context, memory=existing_memory)

    try:
        raw_answer = generate_answer(_build_messages(context, intent, existing_memory, tool_result))
    except LLMError as exc:
        raw_answer = str(exc)
    except Exception as exc:
        raw_answer = f"陪玩 Agent 处理失败：{exc}"

    formatted = format_companion_answer(raw_answer, intent=intent, tool_result=tool_result, user_message=message)
    react_trace = build_react_trace(
        intent=intent,
        formatted=formatted,
        tool_result=tool_result,
        message=message,
    )

    return {
        "answer": raw_answer,
        "trace_id": trace_id,
        "intent": intent,
        "summary": formatted["summary"],
        "key_points": formatted["key_points"],
        "details": formatted["details"],
        "follow_up_questions": formatted["follow_up_questions"],
        "tool_used": bool(tool_result),
        "tool_name": tool_result.get("tool", "") if tool_result else "",
        "memory_used": bool(existing_memory),
        "memory_saved": memory_saved,
        "llm_provider": get_settings().llm_provider,
        "plan": tool_result.get("steps", []) if tool_result else [],
        "recommendations": formatted["recommendations"],
        "memory": existing_memory,
        "react_trace": react_trace,
    }


def update_memory(user_id: str, profile: dict[str, Any], note: str = "") -> dict[str, Any]:
    """Public helper for /api/memory writes."""
    profile = {**profile, "favorite_game": KING_GAME}
    return memory_tool(user_id=user_id, action="write", profile=profile, note=note)["memory"]
