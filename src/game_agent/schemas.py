from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_query: Optional[str] = Field(default=None, min_length=1)
    message: Optional[str] = Field(default=None, min_length=1)
    user_id: str = Field(default="demo_user", min_length=1)
    game_name: str = ""
    task_type: str = "普通问答"
    game_stage: str = ""
    play_style: str = ""
    favorite_character: str = ""
    current_goal: str = ""

    @property
    def query_text(self) -> str:
        return (self.message or self.user_query or "").strip()


class ChatResponse(BaseModel):
    answer: str
    trace_id: str
    tool_used: bool = False
    tool_name: str = ""
    memory_used: bool = False
    memory_saved: bool = False
    llm_provider: str = "deepseek"


class MemoryRequest(BaseModel):
    user_id: str
    content: str = ""
    operate_type: Literal["新增", "查询", "删除", "add", "query", "delete"]


class MemoryResponse(BaseModel):
    operate_result: bool
    related_memory: list[str] = Field(default_factory=list)


class ToolInvokeRequest(BaseModel):
    tool_name: str
    tool_params: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    tool_data: Any


class TraceResponse(BaseModel):
    trace_id: str
    events: list[dict[str, Any]]
    elapsed_ms: float


class CompanionChatRequest(BaseModel):
    user_id: str = Field(default="demo_user", min_length=1)
    message: str = Field(..., min_length=1)
    game: str = ""
    character: str = ""
    mode: str = ""
    style: str = ""
    goal: str = ""
    intent: str = ""


class CompanionChatResponse(BaseModel):
    answer: str
    trace_id: str
    intent: str
    summary: str = ""
    key_points: list[dict[str, str]] = Field(default_factory=list)
    details: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    tool_used: bool = False
    tool_name: str = ""
    memory_used: bool = False
    memory_saved: bool = False
    llm_provider: str = "deepseek"
    plan: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    react_trace: dict[str, str] = Field(default_factory=dict)


class PlayerMemoryWriteRequest(BaseModel):
    user_id: str = Field(default="demo_user", min_length=1)
    favorite_game: str = ""
    favorite_character: str = ""
    play_mode: str = ""
    play_style: str = ""
    goal: str = ""
    note: str = ""


class PlanRequest(BaseModel):
    user_id: str = Field(default="demo_user", min_length=1)
    game: str = ""
    goal: str = Field(..., min_length=1)
    style: str = ""
    available_minutes: int = Field(default=90, ge=10, le=600)


class RecommendRequest(BaseModel):
    user_id: str = Field(default="demo_user", min_length=1)
    game: str = ""
    character: str = ""
    style: str = ""
    goal: str = ""
