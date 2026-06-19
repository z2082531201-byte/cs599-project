from __future__ import annotations

from typing import Any

from openai import OpenAI, OpenAIError

from src.game_agent.config import get_settings


class DeepSeekError(RuntimeError):
    """Raised when DeepSeek cannot return a model answer."""


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages:
        content = message.get("content", "")
        normalized.append(
            {
                "role": str(message.get("role", "user")),
                "content": content if isinstance(content, str) else str(content),
            }
        )
    return normalized


def generate_answer(messages: list[dict[str, Any]]) -> str:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise DeepSeekError("请先配置 DEEPSEEK_API_KEY，或将 LLM_PROVIDER 设置为 ollama。")

    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=45,
    )

    try:
        response = client.chat.completions.create(
            model=settings.deepseek_model,
            messages=_normalize_messages(messages),
            temperature=0.4,
        )
    except OpenAIError as exc:
        raise DeepSeekError(f"DeepSeek 调用失败：{exc}") from exc

    content = response.choices[0].message.content if response.choices else ""
    if not content:
        raise DeepSeekError("DeepSeek 调用失败：模型未返回内容。")
    return content.strip()
