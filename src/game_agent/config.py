from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
load_dotenv()
class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    llm_provider: str = Field(default="deepseek", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434/v1", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5:3b", alias="OLLAMA_MODEL")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    chroma_persist_path: str = Field(default="./game_memory", alias="CHROMA_PERSIST_PATH")
    log_path: str = Field(default="./logs", alias="LOG_PATH")
    @property
    def chroma_path(self) -> Path:
        return Path(self.chroma_persist_path)
    @property
    def logs_dir(self) -> Path:
        return Path(self.log_path)
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
