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


class GemCreate(GemBase):
    pass


class GemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    tags: Optional[list[str]] = None


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
