from __future__ import annotations

from typing import Any

import requests

from src.game_agent.config import get_settings


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot return a model answer."""


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if role not in {"system", "user", "assistant", "tool"}:
            role = "user"
        normalized.append({"role": role, "content": content if isinstance(content, str) else str(content)})
    return normalized


def generate_answer(messages: list[dict[str, Any]]) -> str:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    url = f"{base_url}/api/chat"
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
        raise OllamaError("本地 Ollama 服务未启动，请先运行 ollama serve，并确认模型已下载。") from exc
    except requests.Timeout as exc:
        raise OllamaError("Ollama 响应超时，请确认本地模型已正常加载后重试。") from exc
    except requests.RequestException as exc:
        raise OllamaError(f"Ollama 调用失败：{exc}") from exc

    if response.status_code == 404:
        raise OllamaError(f"当前 Ollama 模型不存在，请先执行 ollama pull {settings.ollama_model}。")

    try:
        data = response.json()
    except ValueError as exc:
        raise OllamaError("本地 Ollama 服务未启动，请先运行 ollama serve，并确认模型已下载。") from exc

    if response.status_code >= 400:
        error = str(data.get("error", response.text))
        if "not found" in error.lower() or "pull" in error.lower():
            raise OllamaError(f"当前 Ollama 模型不存在，请先执行 ollama pull {settings.ollama_model}。")
        raise OllamaError(f"Ollama 调用失败：{error}")

    content = (data.get("message") or {}).get("content", "")
    if not content:
        raise OllamaError("Ollama 调用失败：模型未返回内容。")
    return str(content).strip()
