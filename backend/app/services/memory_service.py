"""
Lapidary Memory (ADR-010): what persists across runs, chats and clients.

Modelled on claude-mem. Capture: when a run finishes, a short observation of what
was asked, which tools ran and what came of it is stored, written by the
`memory_summarizer` gem when a model is available and as a plain digest otherwise.
Recall, in three steps so context stays small: search returns a compact index,
get returns the few full records that matter, and a gem marked `memory: true`
gets the top matches for the message inside a <memory> block. Text inside
<private>...</private> is never stored.
"""
from __future__ import annotations
import logging
import re
from collections import Counter
from datetime import datetime

from app import settings
from app.models import MEMORY_KINDS, MEMORY_SOURCES, Memory, MemoryCreate, MemoryIndexEntry, Run, RunEvent
from app.storage import get_store

logger = logging.getLogger(__name__)

_WS = re.compile(r"[ \t]+")
_OPEN, _CLOSE = "<private>", "</private>"
SUMMARIZER_GEM = "memory_summarizer"


def _store():
    """Indirection so tests can swap the backend."""
    return get_store()


def strip_private(text: str) -> str:
    """
    Drop everything inside <private>...</private> (any case), then tidy whitespace.
    A plain scan, not a regular expression, so a string full of tags cannot make it slow;
    an opening tag without a closing one drops the rest of the text.
    """
    text = text or ""
    lower = text.lower()
    kept, pos = [], 0
    while True:
        i = lower.find(_OPEN, pos)
        if i == -1:
            kept.append(text[pos:])
            break
        kept.append(text[pos:i])
        j = lower.find(_CLOSE, i + len(_OPEN))
        if j == -1:
            break
        pos = j + len(_CLOSE)
    out = _WS.sub(" ", "".join(kept))
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _check(kind: str, source: str) -> None:
    if kind not in MEMORY_KINDS:
        raise ValueError(f"kind must be one of {', '.join(MEMORY_KINDS)}")
    if source not in MEMORY_SOURCES:
        raise ValueError(f"source must be one of {', '.join(MEMORY_SOURCES)}")


async def remember(text: str, *, kind: str = "note", tags: list[str] | None = None, scope: str = "default",
                   source: str = "user", gem_name: str | None = None, run_id: str | None = None) -> Memory | None:
    """Store one memory. Returns None when nothing is left after <private> text is removed."""
    _check(kind, source)
    clean = strip_private(text)
    if not clean:
        return None
    clean = clean[: settings.MEMORY_MAX_CHARS]
    data = MemoryCreate(text=clean, kind=kind, tags=[t.strip().lower() for t in (tags or []) if t.strip()],
                        scope=scope or "default", source=source, gem_name=gem_name, run_id=run_id)
    return await _store().add_memory(data)


def index_entry(m: Memory) -> MemoryIndexEntry:
    first = m.text.strip().splitlines()[0] if m.text.strip() else ""
    return MemoryIndexEntry(id=m.id, kind=m.kind, scope=m.scope, created_at=m.created_at, tags=m.tags,
                            line=first if len(first) <= 160 else first[:157] + "...")


async def search(query: str, *, scope: str | None = "default", kinds: list[str] | None = None, limit: int = 10) -> list[Memory]:
    """Full records matching the query (newest first when the query is empty)."""
    return await _store().search_memories(query or "", scope=scope or None, kinds=kinds or None, limit=max(1, min(limit, 100)))


async def search_index(query: str, *, scope: str | None = "default", kinds: list[str] | None = None, limit: int = 10) -> list[MemoryIndexEntry]:
    """Step one of recall: the compact index."""
    return [index_entry(m) for m in await search(query, scope=scope, kinds=kinds, limit=limit)]


async def get(ids: list[str]) -> list[Memory]:
    """Step two of recall: the full text of the ones that matter."""
    return await _store().get_memories([i for i in ids if i][:50])


async def forget(memory_id: str) -> bool:
    return await _store().delete_memory(memory_id)


async def recall_block(message: str, *, scope: str = "default", limit: int | None = None, max_chars: int | None = None) -> str:
    """
    The <memory> block a gem with memory on gets before its prompt: the top
    matches for the message, one line each, capped in size. Empty when
    nothing matches, so the prompt is unchanged.
    """
    limit = limit or settings.MEMORY_RECALL_LIMIT
    max_chars = max_chars or settings.MEMORY_RECALL_MAX_CHARS
    found = await search(message, scope=scope, limit=limit) if message.strip() else []
    if not found:
        return ""
    lines, used = [], 0
    for m in found:
        when = m.created_at.strftime("%Y-%m-%d") if isinstance(m.created_at, datetime) else str(m.created_at)[:10]
        line = f"- [{m.kind}, {when}] {m.text.strip()}"
        if used + len(line) > max_chars:
            line = line[: max(0, max_chars - used - 3)] + "..."
            lines.append(line)
            break
        lines.append(line)
        used += len(line) + 1
    return "<memory>\nWhat you remember from earlier work (use when relevant, say when you do):\n" + "\n".join(lines) + "\n</memory>"


# ─── capture from runs ─────────────────────────────────────────────────────────

def _short(text: str | None, n: int) -> str:
    t = strip_private(text or "").replace("\n", " ")
    return t if len(t) <= n else t[: n - 3] + "..."


def digest(run: Run, events: list[RunEvent]) -> str:
    """A plain observation of a run, written without a model: what was asked, which tools ran, how it ended, what it said."""
    calls = Counter(str(e.data.get("name")) for e in events if e.type == "tool_call")
    errors = sum(1 for e in events if e.type == "tool_result" and e.data.get("is_error"))
    denied = sum(1 for e in events if e.type == "approval_decided" and not e.data.get("approved"))
    tools = ", ".join(f"{n} x{c}" if c > 1 else n for n, c in calls.most_common()) or "none"
    outcome = {"finished": "finished", "max_steps": "stopped at the step limit", "failed": f"failed ({_short(run.error, 80)})"}.get(run.status, run.status)
    parts = [
        f"{run.gem_name} was asked: {_short(run.input, 240)}",
        f"Tools used: {tools}." + (f" {errors} tool error{'s' if errors != 1 else ''}." if errors else "") + (f" {denied} call{'s' if denied != 1 else ''} denied." if denied else ""),
        f"Outcome: {outcome} after {run.steps} step{'s' if run.steps != 1 else ''}.",
    ]
    if run.output:
        parts.append(f"It said: {_short(run.output, 400)}")
    return "\n".join(parts)


async def _summarize(run: Run, events: list[RunEvent], plain: str) -> str | None:
    """Ask the memory_summarizer gem for a two or three sentence observation; None when it cannot run."""
    from app.services import gem_service, llm_service
    from app.services import router as model_router

    gem = await gem_service.get_gem_by_name(SUMMARIZER_GEM)
    if gem is None:
        return None
    transcript = []
    for e in events:
        if e.type == "model_turn" and e.data.get("text"):
            transcript.append(f"assistant: {_short(str(e.data['text']), 600)}")
        elif e.type == "tool_call":
            transcript.append(f"tool call {e.data.get('name')}: {_short(str(e.data.get('input')), 200)}")
        elif e.type == "tool_result":
            transcript.append(f"tool result {e.data.get('name')}: {_short(str(e.data.get('output')), 300)}")
    resolved, _ = await gem_service.resolve_gem(SUMMARIZER_GEM, {})
    choice = await model_router.choose(gem)
    text = await llm_service.complete(resolved, [{"role": "user", "content": plain + "\n\nTranscript:\n" + "\n".join(transcript[-30:])}],
                                      choice.model, choice.provider, max_tokens=400)
    return strip_private(text) or None


async def observe_run(run: Run, events: list[RunEvent], *, scope: str = "default") -> Memory | None:
    """Store an observation of a finished run. Never raises: memory must not break a run."""
    if not settings.MEMORY_CAPTURE or run.gem_name == SUMMARIZER_GEM:
        return None
    try:
        plain = digest(run, events)
        text = None
        if settings.MEMORY_SUMMARIZE:
            try:
                text = await _summarize(run, events, plain)
            except Exception as exc:  # noqa: BLE001 - the digest is the fallback
                logger.info("memory summarizer unavailable for run %s: %s", run.id, type(exc).__name__)
        return await remember(text or plain, kind="observation", scope=scope, source="run", gem_name=run.gem_name, run_id=run.id,
                              tags=["summarized"] if text else [])
    except Exception:  # noqa: BLE001
        logger.exception("could not store an observation for run %s", run.id)
        return None
