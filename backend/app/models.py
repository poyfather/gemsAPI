from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app import settings


# ─── Gem models ────────────────────────────────────────────────────────────────

class GemBase(BaseModel):
    name: str = Field(..., description="Unique snake_case identifier, e.g. 'code_reviewer'")
    description: str = Field(default="", description="Human-readable description of what this gem does")
    system_prompt: str = Field(
        default="",
        description="The prompt content. Use {variable} for variables, {{gem:name}} to embed another gem."
    )
    model: str = Field(default_factory=lambda: settings.DEFAULT_MODEL, description="Default LLM model")
    provider: str = Field(default_factory=lambda: settings.DEFAULT_PROVIDER, description="LLM provider: 'anthropic' or 'openai'")
    tags: list[str] = Field(default=[], description="Tags for searching and filtering")
    kind: str = Field(default="prompt", description="'prompt' (one model call) or 'agent' (may call its tools in a loop)")
    tools: list[str] = Field(default=[], description="Registered tool names an agent gem may call; see GET /agents/tools")


class GemCreate(GemBase):
    pass


class GemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tags: Optional[list[str]] = None
    kind: Optional[str] = None
    tools: Optional[list[str]] = None


class Gem(GemBase):
    id: str
    variables: list[str] = Field(default=[], description="Variable names detected in system_prompt")
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Resolution models ─────────────────────────────────────────────────────────

class ResolveRequest(BaseModel):
    gem_name: str = Field(..., description="Name of the gem to resolve")
    variables: dict[str, str] = Field(default={}, description="Values for {variable} placeholders")


class ResolveResponse(BaseModel):
    gem_name: str
    resolved_prompt: str
    referenced_gems: list[str] = []
    variables_used: list[str] = []
    variables_missing: list[str] = []


# ─── Chat models ───────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    gem_name: str = Field(..., description="Name of the gem to use as system prompt")
    messages: list[ChatMessage]
    variables: dict[str, str] = Field(default={}, description="Fill {variable} placeholders in the gem")
    model_override: Optional[str] = Field(default=None, description="Override the gem's default model")
    provider_override: Optional[str] = Field(default=None, description="Override provider: 'anthropic' or 'openai'")
    stream: bool = Field(default=False, description="Stream the response via SSE")


class ChatResponse(BaseModel):
    content: str
    model: str
    provider: str
    gem_name: str


# ─── Agent run models (ADR-007) ────────────────────────────────────────────────

class RunRequest(BaseModel):
    message: str = Field(..., description="The user message that starts the run")
    variables: dict[str, str] = Field(default={}, description="Values for {variable} placeholders in the gem")
    model_override: Optional[str] = None
    provider_override: Optional[str] = None
    allow_risky: bool = Field(default=False, description="Let the run call tools marked risky")
    stream: bool = Field(default=False, description="Stream run events as Server-Sent Events")


class RunEvent(BaseModel):
    seq: int
    type: str = Field(..., description="run_started, model_turn, tool_call, tool_result, approval_requested, approval_decided, run_finished, run_failed")
    data: dict = Field(default={})
    created_at: datetime


class Run(BaseModel):
    id: str
    gem_name: str
    status: str = Field(..., description="running, waiting_approval, finished, failed, max_steps")
    model: str
    provider: str
    input: str
    output: Optional[str] = None
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class RunResult(BaseModel):
    run: Run
    events: list[RunEvent] = []


class ApprovalRequest(BaseModel):
    approve: bool = Field(..., description="True to let the pending risky tool call run, False to deny it")
    stream: bool = Field(default=False, description="Stream the rest of the run as Server-Sent Events")


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict
    risky: bool
    source: str = Field(default="builtin", description="'builtin' or the MCP server the tool comes from")
