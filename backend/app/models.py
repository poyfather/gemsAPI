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
    provider: str = Field(default_factory=lambda: settings.DEFAULT_PROVIDER, description="LLM provider: 'anthropic', 'openai', 'local', or 'auto' to let the model policy decide")
    tags: list[str] = Field(default=[], description="Tags for searching and filtering")
    kind: str = Field(default="prompt", description="'prompt' (one model call) or 'agent' (may call its tools in a loop)")
    tools: list[str] = Field(default=[], description="Registered tool names an agent gem may call; see GET /agents/tools")
    memory: bool = Field(default=False, description="Recall: prepend the top memory matches for the message inside a <memory> block (ADR-010)")


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
    memory: Optional[bool] = None
    note: Optional[str] = Field(default=None, description="What changed and why; kept with the new version in the gem's history")


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
    memory_scope: str = Field(default="default", description="Which memory scope a gem with memory on recalls from")


class ChatResponse(BaseModel):
    content: str
    model: str
    provider: str
    gem_name: str
    reason: str = Field(default="", description="Why this model answered (the model policy's explanation)")


# ─── Agent run models (ADR-007) ────────────────────────────────────────────────

class RunRequest(BaseModel):
    message: str = Field(..., description="The user message that starts the run")
    variables: dict[str, str] = Field(default={}, description="Values for {variable} placeholders in the gem")
    model_override: Optional[str] = None
    provider_override: Optional[str] = None
    allow_risky: bool = Field(default=False, description="Let the run call tools marked risky")
    stream: bool = Field(default=False, description="Stream run events as Server-Sent Events")
    memory_scope: str = Field(default="default", description="Which memory scope the run recalls from and records to")


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


# ─── Memory (ADR-010) ──────────────────────────────────────────────────────────

MEMORY_KINDS = ("observation", "summary", "decision", "preference", "lesson", "handoff", "note")
MEMORY_SOURCES = ("run", "chat", "mcp", "console", "user")


class MemoryCreate(BaseModel):
    text: str = Field(..., description="What to remember. Anything inside <private>...</private> is dropped before storing.")
    kind: str = Field(default="note", description="observation, summary, decision, preference, lesson, handoff or note")
    tags: list[str] = Field(default=[])
    scope: str = Field(default="default", description="Keeps projects apart; 'default' unless you say otherwise")
    source: str = Field(default="user", description="run, chat, mcp, console or user")
    gem_name: Optional[str] = None
    run_id: Optional[str] = None


class Memory(MemoryCreate):
    id: str
    created_at: datetime


class MemoryIndexEntry(BaseModel):
    """The compact form search returns: enough to decide which ones to fetch in full."""
    id: str
    kind: str
    scope: str
    created_at: datetime
    line: str = Field(..., description="The first line of the text, at most 160 characters")
    tags: list[str] = []


# ─── Pipelines and gates (ADR-011, roadmap 45) ────────────────────────────────

PIPELINE_STATUSES = ("running", "waiting_approval", "waiting_acceptance", "passed", "failed", "max_attempts")
GATE_ROLES = ("test", "visual", "review", "custom")


class PipelineGate(BaseModel):
    gem: str = Field(..., description="The gate gem; it answers with findings and a final line VERDICT: PASS or VERDICT: FAIL")
    role: str = Field(default="review", description="test, visual, review or custom; shown to the gem and in the record")
    provider_override: Optional[str] = Field(default=None, description="Run the gate on another provider, for an adversarial review on a different model")
    model_override: Optional[str] = None
    instructions: str = Field(default="", description="Extra instructions appended to what the gate is given")


class PipelineBase(BaseModel):
    name: str = Field(..., description="Unique snake_case name")
    description: str = ""
    builder: str = Field(..., description="The gem that does the work; its output goes through the gates")
    gates: list[PipelineGate] = Field(default=[])
    max_attempts: int = Field(default=3, ge=1, le=10, description="How many times the builder may try before the pipeline gives up")
    acceptance: bool = Field(default=True, description="Pause for a person to accept the result after every gate passed")


class PipelineCreate(PipelineBase):
    pass


class PipelineUpdate(BaseModel):
    description: Optional[str] = None
    builder: Optional[str] = None
    gates: Optional[list[PipelineGate]] = None
    max_attempts: Optional[int] = None
    acceptance: Optional[bool] = None


class Pipeline(PipelineBase):
    id: str
    created_at: datetime
    updated_at: datetime


class GateResult(BaseModel):
    gem: str
    role: str
    run_id: Optional[str] = None
    verdict: str = Field(default="waiting", description="pass, fail or waiting")
    findings: str = ""


class Attempt(BaseModel):
    number: int
    builder_run_id: Optional[str] = None
    builder_status: str = "running"
    output: Optional[str] = None
    gates: list[GateResult] = []
    feedback: str = Field(default="", description="What the builder was told from the previous attempt")


class PipelineRunRequest(BaseModel):
    message: str = Field(..., description="The task for the builder")
    variables: dict[str, str] = Field(default={})
    allow_risky: bool = False
    stream: bool = False
    memory_scope: str = "default"


class PipelineResumeRequest(BaseModel):
    accept: Optional[bool] = Field(default=None, description="For a run waiting for acceptance: true accepts, false sends it back to the builder with the note")
    note: str = Field(default="", description="Why it was rejected; given to the builder as findings")
    stream: bool = False


class PipelineRun(BaseModel):
    id: str
    pipeline_name: str
    status: str = Field(..., description="running, waiting_approval, waiting_acceptance, passed, failed, max_attempts")
    input: str
    output: Optional[str] = None
    attempts: list[Attempt] = []
    waiting_run_id: Optional[str] = Field(default=None, description="The agent run to approve when the status is waiting_approval")
    error: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class PipelineResult(BaseModel):
    run: PipelineRun
    events: list[RunEvent] = []


# ─── Version history (roadmap 14) ─────────────────────────────────────────────

VERSIONED_FIELDS = ("name", "description", "system_prompt", "model", "provider", "tags", "variables", "kind", "tools", "memory")


class GemVersion(BaseModel):
    """A gem as it was after one save. `snapshot` holds VERSIONED_FIELDS."""
    gem_id: str
    version: int
    snapshot: dict
    note: str = ""
    source: str = Field(default="api", description="api, mcp, revert or baseline")
    created_at: datetime


class GemVersionSummary(BaseModel):
    version: int
    note: str = ""
    source: str = "api"
    created_at: datetime
    changed: list[str] = Field(default=[], description="Fields that differ from the version before")
    current: bool = False


class GemDiff(BaseModel):
    gem_name: str
    from_version: int
    to_version: int
    changed: list[str] = []
    fields: dict[str, dict] = Field(default={}, description="Every changed field except the prompt, as {from, to}")
    prompt_diff: str = Field(default="", description="Unified diff of system_prompt; empty when the prompt did not change")


class RevertRequest(BaseModel):
    note: str = Field(default="", description="Why; added to the new version's note")


# ─── Evals per gem (roadmap 28) ───────────────────────────────────────────────

EVAL_CHECKS = ("contains", "not_contains", "all_of", "equals", "json", "judge")


class EvalCaseCreate(BaseModel):
    name: str = Field(default="", description="A short label, e.g. 'vague request'")
    input: str = Field(..., description="The user message the gem is given")
    variables: dict[str, str] = Field(default={}, description="Values for the gem's {variable} blanks")
    check: str = Field(default="contains", description="contains, not_contains, all_of (one phrase per line), equals, json (a JSON schema subset), judge (criteria for an AI judge)")
    expected: str = Field(default="", description="The phrase, phrases, exact text, JSON schema or judging criteria")


class EvalCaseUpdate(BaseModel):
    name: Optional[str] = None
    input: Optional[str] = None
    variables: Optional[dict[str, str]] = None
    check: Optional[str] = None
    expected: Optional[str] = None


class EvalCase(EvalCaseCreate):
    id: str
    gem_id: str
    created_at: datetime


class EvalCaseResult(BaseModel):
    case_id: str
    name: str = ""
    passed: bool
    output: str = ""
    detail: str = Field(default="", description="Why it passed or failed, in a sentence")


class EvalEstimate(BaseModel):
    cases: int
    calls: int = Field(..., description="Model calls the run would make: one per case, plus one per judge case")
    provider: str
    model: str
    free: bool = Field(..., description="True when the AI runs on this PC, so the run costs nothing")
    input_tokens: int = Field(..., description="Rough estimate, characters divided by four")
    max_output_tokens: int
    max_calls: int = Field(..., description="The cap per run (GEMS_EVAL_MAX_CALLS)")


class EvalRunRequest(BaseModel):
    provider_override: Optional[str] = None
    model_override: Optional[str] = None
    max_calls: Optional[int] = Field(default=None, description="Refuse the run if it needs more calls than this; never above GEMS_EVAL_MAX_CALLS")


class EvalRun(BaseModel):
    id: str
    gem_id: str
    gem_version: int = Field(..., description="The gem's version in its history when the run happened")
    provider: str
    model: str
    passed: int
    total: int
    results: list[EvalCaseResult] = []
    baseline: bool = False
    created_at: datetime


class EvalRunReport(BaseModel):
    run: EvalRun
    baseline: Optional[EvalRun] = None
    regressions: list[str] = Field(default=[], description="Cases that passed in the baseline and fail now")
    fixed: list[str] = Field(default=[], description="Cases that failed in the baseline and pass now")


# ─── Side-by-side runs (roadmap 30) ───────────────────────────────────────────

class CompareVariant(BaseModel):
    label: str = Field(default="", description="Shown above the column; made up from the version and AI when empty")
    version: Optional[int] = Field(default=None, description="A version from the gem's history; the current one when empty")
    provider_override: Optional[str] = None
    model_override: Optional[str] = None


class CompareRequest(BaseModel):
    message: str = Field(default="", description="The question every column answers; not needed when comparing on the tests")
    variables: dict[str, str] = Field(default={})
    variants: list[CompareVariant] = Field(..., min_length=2, max_length=4)


class CompareColumn(BaseModel):
    label: str
    version: int
    provider: str
    model: str
    reason: str = ""
    output: str = ""
    error: str = ""
    seconds: float = 0
    run_id: Optional[str] = Field(default=None, description="The agent run, for an assistant")


class CompareResult(BaseModel):
    gem_name: str
    message: str
    columns: list[CompareColumn]


class CompareEstimate(BaseModel):
    calls: int
    tests: int
    columns: list[dict] = Field(default=[], description="label, version, provider, model and free for each column")
    free: bool = Field(..., description="True when every column runs on this PC")
    max_calls: int


class CompareTestsResult(BaseModel):
    gem_name: str
    columns: list[CompareColumn] = Field(default=[], description="Which version and AI each column used; output is empty")
    cases: list[dict] = Field(default=[], description="name, then for each column: passed and detail")
    totals: list[int] = Field(default=[], description="Tests passed per column")
