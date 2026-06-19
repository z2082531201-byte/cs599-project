from __future__ import annotations

from typing import Any

import requests

from src.game_agent.config import get_settings


class OpenAICompatibleError(RuntimeError):
    """Raised when an OpenAI-compatible local model endpoint fails."""


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Keep only chat roles accepted by OpenAI-compatible APIs."""
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        if role not in {"system", "user", "assistant", "tool"}:
            role = "user"
        content = message.get("content", "")
        normalized.append({"role": role, "content": content if isinstance(content, str) else str(content)})
    return normalized


def generate_answer(messages: list[dict[str, Any]]) -> str:
    """Call Ollama through its OpenAI-compatible /v1/chat/completions API."""
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": settings.ollama_model,
        "messages": _normalize_messages(messages),
        "stream": False,
    }

    session = requests.Session()
    session.trust_env = False

    try:
        response = session.post(url, json=payload, timeout=120)
    except requests.ConnectionError as exc:
        raise OpenAICompatibleError(
            "本地 Ollama 服务未启动，请先运行 ollama serve，并确认 OpenAI compatible API 可访问。"
        ) from exc
    except requests.Timeout as exc:
        raise OpenAICompatibleError("Ollama 响应超时，请确认本地模型已经加载完成后重试。") from exc
    except requests.RequestException as exc:
        raise OpenAICompatibleError(f"Ollama 调用失败：{exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise OpenAICompatibleError("Ollama 返回了非 JSON 响应，请检查 base_url 是否为 /v1 地址。") from exc

    if response.status_code == 404:
        raise OpenAICompatibleError(f"当前 Ollama 模型不存在，请先执行 ollama pull {settings.ollama_model}。")
    if response.status_code >= 400:
        error = data.get("error", response.text)
        raise OpenAICompatibleError(f"Ollama 调用失败：{error}")

    choices = data.get("choices") or []
    if not choices:
        raise OpenAICompatibleError("Ollama 调用失败：模型未返回 choices。")
    content = (choices[0].get("message") or {}).get("content", "")
    if not content:
        raise OpenAICompatibleError("Ollama 调用失败：模型未返回内容。")
    return str(content).strip()
