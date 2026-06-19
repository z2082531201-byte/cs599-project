from __future__ import annotations

import hashlib
import logging
import math
from pathlib import Path
from typing import Iterable

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings as ChromaSettings

from .config import get_settings


logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)


class HashEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic local embedding for Chroma memory."""

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _tokens(self, text: str) -> Iterable[str]:
        lowered = text.lower()
        for word in lowered.replace("，", " ").replace("。", " ").split():
            yield word
        for char in lowered:
            if "\u4e00" <= char <= "\u9fff":
                yield char


class MemoryStore:
    def __init__(self, persist_path: Path | None = None) -> None:
        settings = get_settings()
        self.persist_path = persist_path or settings.chroma_path
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.embedding = HashEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="game_agent_memory",
            embedding_function=self.embedding,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, user_id: str, content: str, memory_type: str = "conversation") -> str:
        memory_id = hashlib.sha1(f"{user_id}:{content}".encode("utf-8")).hexdigest()
        self.collection.upsert(
            ids=[memory_id],
            documents=[content],
            metadatas=[{"user_id": user_id, "memory_type": memory_type}],
        )
        return memory_id

    def query(self, user_id: str, query: str, limit: int = 5) -> list[str]:
        if not query:
            query = user_id
        result = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where={"user_id": user_id},
        )
        docs = result.get("documents") or [[]]
        return list(docs[0])

    def delete_user(self, user_id: str) -> int:
        existing = self.collection.get(where={"user_id": user_id})
        ids = existing.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)


def memory_manage(user_id: str, content: str, operate_type: str) -> tuple[bool, list[str]]:
    store = MemoryStore()
    normalized = operate_type.lower()
    if normalized in {"新增", "add"}:
        if not content.strip():
            return False, []
        store.add(user_id=user_id, content=content)
        return True, store.query(user_id, content)
    if normalized in {"查询", "query"}:
        return True, store.query(user_id, content)
    if normalized in {"删除", "delete"}:
        deleted = store.delete_user(user_id)
        return True, [f"deleted={deleted}"]
    return False, []
