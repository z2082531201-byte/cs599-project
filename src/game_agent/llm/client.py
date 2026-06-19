from __future__ import annotations

from typing import Any

from src.game_agent.config import get_settings


class LLMError(RuntimeError):
    """Provider-neutral LLM error."""


def generate_answer(messages: list[dict[str, Any]]) -> str:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()

    try:
        if provider == "ollama":
            from .openai_compatible_client import generate_answer as ollama_generate

            return ollama_generate(messages)
        if provider == "deepseek":
            from .deepseek_client import generate_answer as deepseek_generate

            return deepseek_generate(messages)
    except RuntimeError as exc:
        raise LLMError(str(exc)) from exc

    raise LLMError("未知 LLM_PROVIDER，请设置为 ollama 或 deepseek。")
