"""
Draws every diagram in README.md and ARCHITECTURE.md as an SVG infographic.

    python docs/diagrams/build.py

writes docs/diagrams/*.svg: the big picture and the README flowchart, then the
component model, the three request flows (chat, MCP, agent runs), gem
composition and resolution, the data model, the trust boundaries and the
deployment topologies. No dependencies: plain SVG with a white background, system fonts and line icons,
so GitHub renders the files as images in light and dark mode alike. Edit the
layouts below and rerun to change a diagram.
"""
from __future__ import annotations

import pathlib
from html import escape

OUT = pathlib.Path(__file__).resolve().parent
FONT = "Segoe UI, -apple-system, BlinkMacSystemFont, Helvetica Neue, Arial, sans-serif"
INK, MUTED, ARROW = "#14213d", "#5b6577", "#3557d6"

THEMES = {
    "blue":   ("#eef4fe", "#3b82f6", "#1d4ed8"),
    "sky":    ("#f5f9ff", "#93b4f5", "#1d4ed8"),
    "green":  ("#ecf8ef", "#34a853", "#1e7a37"),
    "orange": ("#fff5ea", "#f08c2e", "#c2410c"),
    "purple": ("#f5f0ff", "#8b5cf6", "#6d28d9"),
    "pink":   ("#fff0f2", "#e8778b", "#be123c"),
    "gray":   ("#f2f4f7", "#9aa4b2", "#475467"),
    "white":  ("#ffffff", "#c9d3e3", "#1d4ed8"),
}

# Line icons on a 24 unit grid, drawn with the theme's accent colour.
ICONS = {
    "person":  '<circle cx="12" cy="7.5" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>',
    "gear":    '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="7"/><path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3M4.6 4.6l2.1 2.1M17.3 17.3l2.1 2.1M4.6 19.4l2.1-2.1M17.3 6.7l2.1-2.1"/>',
    "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "window":  '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 13l2 2-2 2M11 17h5"/>',
    "code":    '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
    "plug":    '<path d="M9 2v5M15 2v5M6 7h12v4a6 6 0 0 1-12 0zM12 17v5"/>',
    "db":      '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "shield":  '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/>',
    "check":   '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M7 12l3.5 3.5L17 9"/>',
    "loop":    '<path d="M20 12a8 8 0 0 1-14.3 4.9M4 12a8 8 0 0 1 14.3-4.9M18.5 3v4.5H14M5.5 21v-4.5H10"/>',
    "cpu":     '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    "route":   '<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M6 15.5V9a3 3 0 0 1 3-3h6.5M8.5 18h7"/>',
    "layers":  '<path d="M12 2l10 5-10 5L2 7z"/><path d="M2 12l10 5 10-5M2 17l10 5 10-5"/>',
    "clock":   '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "flask":   '<path d="M9 2h6M10 2v6l-5 10a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-10V2M7 14h10"/>',
    "tool":    '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
    "chat":    '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>',
    "cloud":   '<path d="M7 18h10a4 4 0 0 0 .6-8A6 6 0 0 0 6 9.6 4.2 4.2 0 0 0 7 18z"/>',
    "home":    '<path d="M3 11l9-7 9 7M5 9.5V20h14V9.5M10 20v-6h4v6"/>',
    "chart":   '<path d="M5 20v-7M12 20V5M19 20v-10"/>',
    "flow":    '<path d="M4 18v-6a4 4 0 0 1 4-4h11M15 4l4 4-4 4"/>',
    "spark":   '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    "pen":     '<path d="M4 20l4-1 11-11-3-3L5 16zM14 6l3 3"/>',
}


class Svg:
    def __init__(self, width: int, height: int) -> None:
        self.w, self.h, self.parts = width, height, []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def rect(self, x, y, w, h, fill, stroke, r=14, sw=2, dash=False, shadow=False) -> None:
        d = ' stroke-dasharray="6 5"' if dash else ""
        f = ' filter="url(#shadow)"' if shadow else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{f}/>')

    def text(self, x, y, s, size=14, weight=400, fill=INK, anchor="start", italic=False) -> None:
        st = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{st}>{escape(s)}</text>')

    def icon(self, name, cx, cy, color, size=26, badge=None) -> None:
        if badge:
            self.add(f'<circle cx="{cx}" cy="{cy}" r="{size * 0.85:.1f}" fill="{badge}"/>')
        s = size / 24
        self.add(f'<g transform="translate({cx - size / 2:.1f},{cy - size / 2:.1f}) scale({s:.3f})" fill="none" stroke="{color}" '
                 f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g>')

    def arrow(self, points, color=ARROW, dash=False, both=False, sw=2.2) -> None:
        d = "M" + " L".join(f"{x},{y}" for x, y in points)
        da = ' stroke-dasharray="6 5"' if dash else ""
        start = ' marker-start="url(#arrowStart)"' if both else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{da}{start} marker-end="url(#arrow)"/>')

    def label(self, x, y, s, anchor="start", size=12.5) -> None:
        """Small text on a white plate, for arrow labels that cross other shapes."""
        w = len(s) * size * 0.56 + 10
        x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x - 5)
        self.add(f'<rect x="{x0:.1f}" y="{y - size}" width="{w:.1f}" height="{size + 7}" rx="4" fill="#ffffff" opacity="0.92"/>')
        self.text(x, y, s, size, 500, ARROW, anchor)

    def card(self, x, y, w, h, theme, icon, title, lines=(), title_size=17, bullets=True, sub=None, shadow=True, icon_badge=True) -> None:
        fill, stroke, accent = THEMES[theme]
        self.rect(x, y, w, h, fill, stroke, shadow=shadow)
        ix = x + 30
        self.icon(icon, ix, y + 30, accent, 22, badge="#ffffff" if icon_badge else None)
        self.text(ix + 26, y + 36, title, title_size, 700, INK)
        ty = y + 36
        if sub:
            ty += 21
            self.text(ix + 26, ty, sub, 13, 400, MUTED)
        for line in lines:
            ty += 20
            self.text(x + 22, ty, ("•  " if bullets else "") + line, 13.5, 400, "#344054")

    def chip(self, x, y, w, h, theme, icon, title, sub=None) -> None:
        fill, stroke, accent = THEMES[theme]
        self.rect(x, y, w, h, fill, stroke, r=10, sw=1.6)
        self.icon(icon, x + 20, y + h / 2, accent, 19)
        if sub:
            self.text(x + 36, y + h / 2 - 3, title, 13.5, 700, INK)
            self.text(x + 36, y + h / 2 + 14, sub, 11.5, 400, MUTED)
        else:
            self.text(x + 36, y + h / 2 + 5, title, 13.5, 700, INK)

    def save(self, name: str, title: str, desc: str) -> None:
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'font-family="{FONT}" role="img" aria-labelledby="t d">'
                f'<title id="t">{escape(title)}</title><desc id="d">{escape(desc)}</desc>'
                '<defs>'
                f'<marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{ARROW}"/></marker>'
                f'<marker id="arrowStart" viewBox="0 0 10 10" refX="1.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{ARROW}"/></marker>'
                '<filter id="shadow" x="-5%" y="-5%" width="110%" height="120%"><feDropShadow dx="0" dy="2" stdDeviation="2.5" flood-color="#1e3a8a" flood-opacity="0.10"/></filter>'
                '</defs>'
                f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>')
        (OUT / name).write_text(head + "\n".join(self.parts) + "</svg>\n")


def benefits(s: Svg, y: int, items: list[str], title: str = "Key benefits", icon: str = "chart") -> None:
    fill, stroke, accent = THEMES["green"]
    s.rect(40, y, 1120, 70, "#f3faf5", "#cfe9d6", r=12, sw=1.5)
    s.icon(icon, 72, y + 35, accent, 26)
    s.text(98, y + 42, title, 20, 800, INK)
    col = (1120 - 230) / len(items)
    for i, item in enumerate(items):
        x = 270 + i * col
        s.add(f'<line x1="{x - 18}" y1="{y + 14}" x2="{x - 18}" y2="{y + 56}" stroke="#cfe9d6" stroke-width="1.5"/>')
        s.add(f'<circle cx="{x + 12}" cy="{y + 35}" r="11" fill="{accent}"/>')
        s.add(f'<path d="M{x + 6} {y + 35}l4 4 7-7" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
        words = item.split(" ")
        if len(item) > 22:
            half = len(words) // 2 + (1 if len(words) % 2 else 0)
            s.text(x + 30, y + 31, " ".join(words[:half]), 13.5, 500, INK)
            s.text(x + 30, y + 48, " ".join(words[half:]), 13.5, 500, INK)
        else:
            s.text(x + 30, y + 40, item, 13.5, 500, INK)


def flow_strip(s: Svg, y: int, steps: list[tuple[str, str, str, str | None]]) -> None:
    s.rect(40, y, 1120, 84, "#f5f9ff", "#cddcf6", r=12, sw=1.5)
    s.icon("flow", 66, y + 42, ARROW, 24)
    s.text(88, y + 38, "End-to-end", 17, 800, INK)
    s.text(88, y + 58, "flow", 17, 800, INK)
    x0, gap = 196, 14
    n = len(steps)
    w = (1160 - 16 - x0 - gap * (n - 1)) / n
    for i, (theme, icon, title, sub) in enumerate(steps):
        x = x0 + i * (w + gap)
        s.chip(x, y + 18, w, 48, theme, icon, title, sub)
        if i < n - 1:
            s.arrow([(x + w + 1, y + 42), (x + w + gap - 1, y + 42)], sw=1.8)


# ─── The architecture (ARCHITECTURE.md) ───────────────────────────────────────

def architecture() -> None:
    s = Svg(1200, 1240)
    s.text(600, 52, "Lapidary Architecture", 36, 800, INK, "middle")
    s.text(600, 84, "Prompt library + agent harness + Windows console + memory + gates", 18, 500, MUTED, "middle")

    # You
    s.rect(450, 108, 300, 64, "#ffffff", "#c9d3e3", shadow=True)
    s.icon("person", 492, 140, INK, 28)
    s.text(518, 136, "You", 19, 800, INK)
    s.text(518, 158, "ideas • questions • prompts", 13, 400, MUTED)
    s.arrow([(600, 172), (600, 196)])
    s.add(f'<path d="M171 196 H1029" stroke="{ARROW}" stroke-width="2.2" fill="none"/>')
    for x in (171, 465, 735, 1029):
        s.arrow([(x, 196), (x, 214)])

    # Ways in
    s.text(40, 210, "WAYS IN", 12, 800, MUTED)
    ways = [
        (40, "monitor", "Web UI", "Next.js on :3000", ["prompts, chat, tests", "history, compare, memory"]),
        (334, "window", "Lapidary Console", "Windows 11 app", ["first run and recipes", "Doctor, installs, PowerShell"]),
        (604, "code", "REST + OpenAI API", "one key, X-API-Key or bearer", ["/gems, /chat, /agents", "/v1 for Open WebUI"]),
        (898, "plug", "MCP clients", "stdio, or HTTP at /mcp", ["Claude Desktop, ChatGPT", "Cursor, Codex, OpenCode"]),
    ]
    for x, icon, title, sub, lines in ways:
        s.card(x, 216, 262, 116, "sky", icon, title, lines, title_size=16, sub=sub)
    for x in (171, 465, 735, 1029):
        s.arrow([(x, 332), (x, 368)])

    # Core
    fill, stroke, accent = THEMES["blue"]
    s.rect(40, 372, 1120, 236, fill, stroke, shadow=True)
    s.icon("gear", 486, 408, accent, 30)
    s.text(514, 418, "Lapidary backend", 26, 800, INK)
    s.text(600, 444, "FastAPI on :8000 • FastMCP • the same services behind every door", 14.5, 500, MUTED, "middle")
    cores = [
        ("layers", "Resolver", ["{{gem:name}} composition", "typed blanks + defaults", "worked examples"]),
        ("route", "Which AI?", ["local • online • mix", "auto • hand pick", "says why it picked"]),
        ("loop", "Agent run loop", ["tools, step by step", "asks before risky tools", "every run recorded"]),
        ("clock", "History + tests", ["every save kept, restore", "tests with a baseline", "side-by-side compare"]),
        ("db", "Memory", ["observations, lessons", "decisions, handoffs", "one memory, every app"]),
    ]
    cw, gap = 204, 12
    for i, (icon, title, lines) in enumerate(cores):
        x = 60 + i * (cw + gap)
        theme = "green" if title == "Memory" else "white"
        s.card(x, 462, cw, 128, theme, icon, title, lines, title_size=16, shadow=False)
    for i in range(3):
        x = 60 + (i + 1) * (cw + gap) - gap
        s.add(f'<path d="M{x + 1} 526 h{gap - 2}" stroke="{ARROW}" stroke-width="1.8" fill="none" marker-end="url(#arrow)"/>')

    # Storage (side, dashed like auxiliary infrastructure)
    s.arrow([(1040, 590), (1040, 648)], dash=True, sw=1.8)
    s.label(1032, 630, "all of it stored in", "end", 12)

    # Gates
    fill, stroke, accent = THEMES["orange"]
    s.rect(40, 634, 860, 172, fill, stroke, shadow=True)
    s.icon("loop", 300, 668, accent, 28)
    s.text(326, 677, "Pipelines and gates", 24, 800, INK)
    s.text(470, 702, "a model never decides it is done • failures go back to the builder", 14, 500, MUTED, "middle")
    gates = [("code", "Builder", "writes the change"), ("check", "Gate 1", "tests"), ("monitor", "Gate 2", "visual review"),
             ("shield", "Gate 3", "adversarial review"), ("person", "You", "accept or reject")]
    gw, gg = 150, 17
    for i, (icon, title, sub) in enumerate(gates):
        x = 62 + i * (gw + gg)
        s.chip(x, 724, gw, 60, "white" if i else "white", icon, title, sub)
        if i < len(gates) - 1:
            s.arrow([(x + gw + 1, 754), (x + gw + gg - 1, 754)], color="#f08c2e", sw=2)
    s.arrow([(371, 608), (371, 634)])
    s.label(380, 626, "runs and pipelines", "start", 12)

    # Storage card
    s.card(920, 650, 240, 156, "gray", "db", "Storage", ["SQLite on this PC (default)", "or Supabase Postgres", "gems, versions, tests,", "runs, memory, pipelines"], title_size=17, bullets=False)

    # Models and tools
    fill, stroke, accent = THEMES["purple"]
    s.rect(40, 832, 1120, 186, fill, stroke, shadow=True)
    s.icon("cpu", 66, 866, accent, 30)
    s.text(92, 876, "Models and tools", 24, 800, INK)
    s.text(316, 876, "• free on this PC, or online with your own key", 16, 500, MUTED)
    s.add('<rect x="60" y="896" width="1080" height="34" rx="8" fill="#ffffff" stroke="#d9cdfa"/>')
    s.icon("route", 90, 913, accent, 18)
    s.text(108, 918, "Model router", 13.5, 800, INK)
    s.text(208, 918, "picks per call from your policy and what is set up • falls back the other way • records which model answered and why", 12.5, 400, MUTED)
    models = [
        ("purple", "cpu", "On this PC", "Ollama, LM Studio, oMLX • free"),
        ("purple", "cloud", "Claude", "Anthropic API • your key"),
        ("purple", "cloud", "ChatGPT", "OpenAI API • your key"),
        ("pink", "tool", "Tools", "PowerShell 7, REA, any MCP server"),
    ]
    mw = (1080 - 3 * 14) / 4
    for i, (theme, icon, title, sub) in enumerate(models):
        x = 60 + i * (mw + 14)
        f, st, ac = THEMES[theme]
        s.rect(x, 944, mw, 58, "#ffffff", st, r=10, sw=1.6)
        s.icon(icon, x + 28, 973, ac, 22, badge=f)
        s.text(x + 52, 968, title, 14.5, 800, INK)
        s.text(x + 52, 987, sub, 11.5, 400, MUTED)
    s.arrow([(474, 590), (474, 608)], sw=1.8)
    s.arrow([(474, 806), (474, 832)])
    s.label(484, 824, "model calls and tool calls", "start", 12)

    benefits(s, 1040, ["One home for every prompt", "Free and private on this PC", "Checked before it is done", "One memory for every app"])
    flow_strip(s, 1128, [
        ("white", "person", "You", None), ("sky", "chat", "Prompt", "or assistant"), ("blue", "layers", "Resolver", "builds it"),
        ("purple", "route", "Which AI", "your policy"), ("orange", "loop", "Gates", "check it"), ("pink", "tool", "Fix loop", "if a gate fails"),
        ("green", "check", "Approved", "and kept"),
    ])
    s.save("lapidary-architecture.svg", "Lapidary Architecture",
           "You reach Lapidary through the web UI, the Windows console, REST and the OpenAI-compatible API, or MCP clients. "
           "The backend resolves prompts, picks which AI answers, runs assistants with tools, keeps history, tests and memory, "
           "and runs pipelines through test, visual and adversarial gates before you accept. Models run on this PC or online; "
           "everything is stored in SQLite or Supabase.")


# ─── The flowchart (README) ───────────────────────────────────────────────────

def flow() -> None:
    s = Svg(1200, 830)
    s.text(600, 52, "How Lapidary Answers", 36, 800, INK, "middle")
    s.text(600, 84, "One prompt library, every app, the AI you choose", 18, 500, MUTED, "middle")

    # Ways in
    s.rect(40, 108, 1120, 92, "#f5f9ff", "#cddcf6", r=14, sw=1.5)
    s.icon("person", 74, 154, INK, 28)
    s.text(98, 150, "You ask from", 17, 800, INK)
    s.text(98, 170, "any of these", 13, 400, MUTED)
    apps = [("monitor", "Web UI", "try, chat, compare"), ("window", "Console", "the Windows app"), ("plug", "AI apps over MCP", "Claude, ChatGPT, Cursor"),
            ("chat", "Open WebUI", "gems as models"), ("code", "Your scripts", "REST and /v1")]
    aw = (1160 - 16 - 236 - 4 * 12) / 5
    for i, (icon, title, sub) in enumerate(apps):
        s.chip(236 + i * (aw + 12), 128, aw, 52, "white", icon, title, sub)
    s.arrow([(600, 200), (600, 232)])

    # Five stages
    stages = [
        ("blue", "layers", "1  Build the prompt", "Resolver", ["pastes in the prompts", "it is built from", "fills blanks, defaults", "adds worked examples", "and memory"]),
        ("purple", "route", "2  Pick the AI", "Which AI should we use?", ["free one on this PC", "online with your key", "a mix, or decide for me", "and says why"]),
        ("sky", "loop", "3  Answer or act", "Prompt or assistant", ["a prompt answers once", "an assistant uses tools", "step by step and asks", "before risky ones"]),
        ("orange", "shield", "4  Check it", "Gates and tests", ["tests, visual and", "adversarial review", "failures go back", "you accept the result"]),
        ("green", "db", "5  Keep it", "History and memory", ["every run recorded", "every save versioned", "lessons remembered", "for the next time"]),
    ]
    w, gap, y = 212, 15, 236
    for i, (theme, icon, title, sub, lines) in enumerate(stages):
        x = 40 + i * (w + gap)
        fill, stroke, accent = THEMES[theme]
        s.rect(x, y, w, 236, fill, stroke, shadow=True)
        s.icon(icon, x + 30, y + 32, accent, 24, badge="#ffffff")
        s.text(x + 52, y + 38, title, 15.5, 800, INK)
        s.text(x + 20, y + 66, sub, 13.5, 700, accent)
        for j, line in enumerate(lines):
            s.text(x + 20, y + 94 + j * 21, line, 13.5, 400, "#344054")
        if i < len(stages) - 1:
            s.arrow([(x + w + 2, y + 118), (x + w + gap - 2, y + 118)])
    s.add(f'<path d="M{40 + 4 * (w + gap) + w / 2:.0f} 472 V496 H600" stroke="{ARROW}" stroke-width="2.2" fill="none"/>')
    s.arrow([(600, 496), (600, 520)])

    # Result
    s.rect(330, 522, 540, 58, "#ffffff", "#34a853", r=14, sw=2.2, shadow=True)
    s.add('<circle cx="372" cy="551" r="15" fill="#34a853"/><path d="M364 551l5 5 10-10" stroke="#fff" stroke-width="2.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    s.text(398, 547, "An answer you can trust", 19, 800, INK)
    s.text(398, 567, "back in the app you asked from • recorded, versioned, remembered", 13, 400, MUTED)

    # Under the hood
    s.rect(40, 602, 1120, 118, "#f8f9fb", "#d0d5dd", r=14, sw=1.5, dash=True)
    s.icon("gear", 70, 640, THEMES["gray"][2], 24)
    s.text(94, 646, "Under the hood", 16, 800, INK)
    hood = [("gray", "db", "SQLite or Supabase", "one store for everything"), ("purple", "cpu", "Ollama and friends", "models on this PC"),
            ("purple", "cloud", "Claude and ChatGPT", "online, your own key"), ("pink", "tool", "Tools", "PowerShell 7, REA, MCP")]
    hw = (1120 - 40 - 3 * 14) / 4
    for i, (theme, icon, title, sub) in enumerate(hood):
        s.chip(60 + i * (hw + 14), 658, hw, 48, theme, icon, title, sub)

    benefits(s, 740, ["Write a prompt once", "Use it from every app", "Free and private by default", "Nothing done until checked"])
    s.save("lapidary-flow.svg", "How Lapidary Answers",
           "You ask from the web UI, the Windows console, Claude or ChatGPT over MCP, Cursor or Codex, Open WebUI, or a script. "
           "Lapidary builds the prompt, picks the AI, answers or acts with tools, checks the result with gates and tests, "
           "and keeps the run, the version and what it learned, then answers in the app you asked from.")


# ─── Shared pieces for the detailed diagrams ──────────────────────────────────

def header(s: Svg, title: str, sub: str) -> None:
    s.text(600, 52, title, 34, 800, INK, "middle")
    s.text(600, 82, sub, 17, 500, MUTED, "middle")


def text_width(t: str, size: float) -> float:
    return len(t) * size * 0.56


def plate(s: Svg, x: float, y: float, t: str, size: float = 12.5, color: str = ARROW, x0: float = 44, x1: float = 1156) -> None:
    """Centred label on a white plate, kept inside x0..x1."""
    w = text_width(t, size) + 12
    left = min(max(x - w / 2, x0), x1 - w)
    s.add(f'<rect x="{left:.1f}" y="{y - size - 1:.1f}" width="{w:.1f}" height="{size + 8:.1f}" rx="5" fill="#ffffff" stroke="#e3e9f5" stroke-width="1"/>')
    s.text(left + w / 2, y + 2, t, size, 500, color, "middle")


def zone(s: Svg, x, y, w, h, theme, icon, title, sub=None) -> None:
    """A dashed area with a heading, for groups and boundaries."""
    fill, stroke, accent = THEMES[theme]
    s.rect(x, y, w, h, fill, stroke, r=14, sw=1.6, dash=True)
    s.icon(icon, x + 24, y + 24, accent, 20)
    s.text(x + 42, y + 30, title, 15, 800, INK)
    if sub:
        s.text(x + 42 + text_width(title, 15) + 14, y + 30, sub, 12.5, 400, MUTED)


def box(s: Svg, x, y, w, h, theme, title, lines=(), title_size=14, mono=False, center=False, sub=None, shadow=False) -> None:
    """A small white card with an accent border: a module, a gem, a step."""
    fill, stroke, accent = THEMES[theme]
    s.rect(x, y, w, h, "#ffffff", stroke, r=10, sw=1.6, shadow=shadow)
    tx, anchor = (x + w / 2, "middle") if center else (x + 14, "start")
    s.text(tx, y + 23, title, title_size, 800, INK, anchor)
    ty = y + 23
    if sub:
        ty += 18
        s.text(tx, ty, sub, 12, 600, accent, anchor)
    for line in lines:
        ty += 17
        s.text(tx, ty, line, 12, 400, "#475467", anchor)


def numbered(s: Svg, cx, cy, n, color=ARROW, r=11) -> None:
    s.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}"/>')
    s.text(cx, cy + 4.3, str(n), 12, 800, "#ffffff", "middle")


GROUP_THEME = {"loop": "orange", "alt": "purple", "opt": "green"}


def actor(s: Svg, cx: float, y: float, w: float, theme: str, icon: str, title: str, sub: str) -> None:
    """A lifeline head: icon and title on one line, the subtitle under it, both centred and shrunk to fit."""
    fill, stroke, accent = THEMES[theme]
    s.rect(cx - w / 2, y, w, 58, fill, stroke, r=10, sw=1.6)
    ts = min(14.0, (w - 40) / (len(title) * 0.6))
    tw = len(title) * ts * 0.6 + 22
    s.icon(icon, cx - tw / 2 + 8, y + 21, accent, 16)
    s.text(cx - tw / 2 + 22, y + 26, title, ts, 800, INK)
    ss = min(11.5, (w - 14) / (len(sub) * 0.56))
    s.text(cx, y + 45, sub, ss, 400, MUTED, "middle")


def sequence(s: Svg, top: float, actors: list, steps: list, x0: float = 44, x1: float = 1156, row: float = 46) -> float:
    """
    A sequence diagram in the infographic style: actors as chips along the top,
    dashed lifelines, numbered messages, replies dashed, loop/alt groups as tinted
    areas. Steps: ("msg", a, b, text), ("reply", a, b, text), ("self", a, text),
    ("note", a, b, [lines], theme), ("loop"|"alt"|"opt", label, a, b), ("end",).
    Returns the y just below the last step.
    """
    n = len(actors)
    colw = (x1 - x0) / n
    cx = [x0 + colw * (i + 0.5) for i in range(n)]
    cw = min(colw - 10, 190)
    for i, (theme, icon, title, sub) in enumerate(actors):
        actor(s, cx[i], top, cw, theme, icon, title, sub)
    back = len(s.parts)          # lifelines and group areas go behind the messages
    behind: list[str] = []
    group_svg: list[tuple[int, str]] = []   # outer groups first, so an inner one sits on top
    y = top + 58 + 40
    num = 0
    groups = []
    for st in steps:
        kind = st[0]
        if kind in GROUP_THEME:
            _, label, a, b = st
            groups.append((y - 12, kind, label, a, b, len(groups)))
            y += 40
        elif kind == "end":
            gy, gk, gl, a, b, depth = groups.pop()
            fill, stroke, accent = THEMES[GROUP_THEME[gk]]
            inset = 6 + 12 * depth
            left, right = cx[min(a, b)] - colw / 2 + inset, cx[max(a, b)] + colw / 2 - inset
            tag = f"{gk}  {gl}"
            tw = text_width(tag, 12) + 16
            right = max(right, left + tw + 20)
            group_svg.append((depth, f'<rect x="{left:.1f}" y="{gy:.1f}" width="{right - left:.1f}" height="{y - gy - 12:.1f}" rx="10" fill="{fill}" fill-opacity="0.7" stroke="{stroke}" stroke-width="1.4" stroke-dasharray="5 4"/>'
                              f'<rect x="{left + 8:.1f}" y="{gy + 6:.1f}" width="{tw:.1f}" height="19" rx="6" fill="{stroke}"/>'
                              f'<text x="{left + 16:.1f}" y="{gy + 19.5:.1f}" font-size="12" font-weight="700" fill="#ffffff">{escape(tag)}</text>'))
            y += 10
        elif kind in ("msg", "reply"):
            _, a, b, label = st
            num += 1
            d = 1 if b > a else -1
            color = ARROW if kind == "msg" else "#6b84d9"
            plate(s, (cx[a] + cx[b]) / 2, y - 14, label, 12, INK if kind == "msg" else "#3d4b6b", x0, x1)
            s.arrow([(cx[a] + d * 26, y), (cx[b] - d * 5, y)], color=color, dash=(kind == "reply"), sw=1.9)
            numbered(s, cx[a] + d * 13, y, num, color)
            y += row
        elif kind == "self":
            _, a, label = st
            num += 1
            x = cx[a]
            s.add(f'<path d="M{x + 5} {y - 8} h34 v16 h-31" fill="none" stroke="{ARROW}" stroke-width="1.9" marker-end="url(#arrow)"/>')
            numbered(s, x - 15, y, num)
            w = text_width(label, 12) + 12
            left = min(x + 46, x1 - w)
            s.add(f'<rect x="{left:.1f}" y="{y - 12:.1f}" width="{w:.1f}" height="20" rx="5" fill="#ffffff" stroke="#e3e9f5"/>')
            s.text(left + 6, y + 2, label, 12, 500, INK)
            y += row
        elif kind == "note":
            _, a, b, lines, theme = st
            fill, stroke, accent = THEMES[theme]
            pad = 16 + 12 * len(groups)
            left, right = cx[min(a, b)] - colw / 2 + pad, cx[max(a, b)] + colw / 2 - pad
            h = 14 + 18 * len(lines)
            s.rect(left, y - 14, right - left, h, fill, stroke, r=8, sw=1.4)
            for i, line in enumerate(lines):
                s.text(left + 12, y + 2 + i * 18, line, 12, 600 if i == 0 else 400, INK if i == 0 else "#475467")
            y += h + 14
    for x in cx:
        behind.insert(0, f'<path d="M{x:.1f} {top + 58} V{y - 10:.1f}" stroke="#b8c4da" stroke-width="1.4" stroke-dasharray="4 5"/>')
    behind += [svg for _, svg in sorted(group_svg, key=lambda g: g[0])]
    s.parts[back:back] = behind
    return y


def table_card(s: Svg, x, y, w, theme, icon, name, cols, note=None) -> float:
    """A database table: header with the name, then one row per column with its type and key."""
    fill, stroke, accent = THEMES[theme]
    h = 44 + 19 * len(cols) + (20 if note else 0) + 6
    s.rect(x, y, w, h, "#ffffff", stroke, r=12, sw=1.8, shadow=True)
    s.add(f'<path d="M{x} {y + 38} V{y + 12} a12 12 0 0 1 12 -12 H{x + w - 12} a12 12 0 0 1 12 12 V{y + 38} Z" fill="{fill}"/>')
    s.add(f'<line x1="{x}" y1="{y + 38}" x2="{x + w}" y2="{y + 38}" stroke="{stroke}" stroke-width="1.2"/>')
    s.icon(icon, x + 22, y + 19, accent, 18)
    s.text(x + 38, y + 25, name, 15, 800, INK)
    ty = y + 38
    for col, typ, key in cols:
        ty += 19
        if key:
            kw = text_width(key, 10) + 10
            s.add(f'<rect x="{x + 12}" y="{ty - 12}" width="{kw:.1f}" height="15" rx="4" fill="{accent}"/>')
            s.text(x + 12 + kw / 2, ty - 1, key, 10, 800, "#ffffff", "middle")
        s.text(x + 46, ty, col, 12.5, 600 if key else 400, INK)
        s.text(x + w - 12, ty, typ, 11.5, 400, MUTED, "end")
    if note:
        s.text(x + 12, ty + 22, note, 11.5, 400, accent, italic=True)
    return h


# ─── Component model (ARCHITECTURE.md) ────────────────────────────────────────

def components() -> None:
    s = Svg(1200, 0)
    header(s, "Component Model", "Every door leads to the same services, one store and the AI you choose")

    # Callers
    s.text(40, 118, "WHO CALLS", 12, 800, MUTED)
    callers = [("monitor", "Web UI", "the browser"), ("window", "Lapidary Console", "Windows app"), ("plug", "MCP over HTTP", "connectors, ChatGPT"),
               ("code", "Scripts, Open WebUI", "REST and /v1"), ("plug", "MCP over stdio", "Claude Desktop, Cursor")]
    cw = (1120 - 4 * 14) / 5
    xs = [40 + i * (cw + 14) for i in range(5)]
    for x, (icon, title, sub) in zip(xs, callers):
        s.chip(x, 126, cw, 52, "white", icon, title, sub)

    # Next.js server
    zone(s, 40, 214, 430, 112, "sky", "monitor", "Next.js server", "frontend/ on :3000")
    box(s, 58, 254, 190, 58, "sky", "proxy.ts", ["adds X-API-Key on the hop"])
    box(s, 262, 254, 190, 58, "sky", "next.config.mjs", ["/api/* to BACKEND_URL"])
    s.arrow([(xs[0] + cw / 2, 178), (xs[0] + cw / 2, 214)])
    plate(s, xs[0] + cw / 2, 200, "same origin")
    # The console embeds the UI and starts the backend and UI as sidecars
    s.arrow([(xs[1] + cw / 2, 178), (xs[1] + cw / 2, 214)])
    plate(s, xs[1] + cw / 2 + 30, 200, "embeds the UI, starts sidecars")

    # MCP stdio process
    zone(s, 900, 214, 260, 112, "purple", "plug", "MCP stdio process")
    s.text(942, 262, "backend/mcp_server.py", 12.5, 600, "#344054")
    src = (OUT.parent.parent / "backend" / "mcp_server.py").read_text()
    s.text(942, 282, f"{src.count('@mcp.tool')} tools • {src.count('@mcp.resource')} resources", 12.5, 400, "#475467")
    s.text(942, 302, "no key check: its own process", 12.5, 400, "#475467")
    s.arrow([(xs[4] + cw / 2, 178), (xs[4] + cw / 2, 214)])

    # FastAPI
    zone(s, 40, 360, 1120, 176, "blue", "gear", "FastAPI service", "backend/app on :8000 • main.py, auth.py: every route but / and /health needs a key")
    routes = [("gems.py", "CRUD, resolve,", "versions, diff"), ("evals.py", "tests, compare,", "estimates"), ("chat.py", "chat (SSE),", "models, policy"),
              ("agents.py", "agents, runs,", "approve"), ("pipelines.py", "pipelines,", "accept"), ("memory.py", "search, remember,", "forget"),
              ("openai_compat.py", "/v1/models,", "/v1/chat/..."), ("mcp_http.py", "MCP at /mcp,", "same key")]
    rw = (1080 - 7 * 10) / 8
    for i, (title, l1, l2) in enumerate(routes):
        box(s, 60 + i * (rw + 10), 400, rw, 74, "blue" if i < 7 else "purple", title, [l1, l2], title_size=min(12.5, (rw - 22) / (len(title) * 0.6)))
    s.text(600, 516, "routes are thin: they validate, then call the shared services below", 13, 500, MUTED, "middle")
    # arrows from callers into FastAPI
    s.arrow([(255, 326), (255, 360)])
    plate(s, 255, 346, "HTTP + X-API-Key")
    s.arrow([(xs[2] + cw / 2, 178), (xs[2] + cw / 2, 360)])
    s.arrow([(xs[3] + cw / 2, 178), (xs[3] + cw / 2, 360)])
    plate(s, xs[3] + cw / 2, 340, "X-API-Key or bearer")

    # Services
    zone(s, 40, 568, 1120, 196, "green", "layers", "Shared service layer", "the same Python functions for REST, /mcp and stdio MCP")
    svc = [("gem_service", "resolver", "blanks, examples"), ("router.py", "which AI", "and why"), ("llm_service", "one adapter for", "every provider"),
           ("version_service", "every save", "kept"), ("eval_service", "tests,", "judge"), ("compare_service", "side by side", "runs"),
           ("memory_service", "recall,", "observe")]
    sw = (1080 - 6 * 10) / 7
    for i, (title, l1, l2) in enumerate(svc):
        box(s, 60 + i * (sw + 10), 606, sw, 66, "green", title, [l1, l2], title_size=12.5)
    agents = [("agents/runner.py", "the run loop, approvals"), ("agents/tools.py", "registry, builtin, MCP sources"),
              ("agents/run_service.py", "runs and events"), ("agents/pipeline.py", "builder, gates, accept")]
    aw = (1080 - 3 * 10) / 4
    for i, (title, l1) in enumerate(agents):
        box(s, 60 + i * (aw + 10), 684, aw, 60, "green", title, [l1], title_size=12.5)
    s.arrow([(600, 536), (600, 568)])
    s.add(f'<path d="M1160 270 H1180 V552 H760" stroke="{ARROW}" stroke-width="2.2" fill="none"/>')
    s.arrow([(760, 552), (760, 568)])
    plate(s, 1000, 556, "stdio MCP imports the same services")

    # Bottom row
    s.arrow([(200, 764), (200, 796)])
    s.arrow([(600, 764), (600, 796)])
    s.arrow([(1000, 764), (1000, 796)])
    s.card(40, 798, 360, 120, "gray", "db", "Storage", ["storage/: one Store interface", "SQLiteStore (default, this PC)", "SupabaseStore (GEMS_STORAGE)"], title_size=16, bullets=False)
    s.card(420, 798, 360, 120, "purple", "cpu", "AI providers", ["Anthropic and OpenAI SDKs", "local: Ollama, LM Studio, oMLX", "through llm_service only"], title_size=16, bullets=False)
    s.card(800, 798, 360, 120, "pink", "tool", "Tools for agents", ["PowerShell 7 (asks first)", "REA and any MCP server", "from configs/mcp_servers.json"], title_size=16, bullets=False)

    benefits(s, 940, ["MCP is a second door to the same services", "Keys checked at the REST and /mcp edge",
                      "No route imports a provider SDK", "One store: SQLite or Supabase"], "Key points", "check")
    s.h = 1030
    s.save("lapidary-components.svg", "Component Model",
           "Callers (the web UI through the Next.js proxy, the Windows console, MCP over HTTP, scripts and Open WebUI, and MCP over stdio) "
           "reach the FastAPI routes or the stdio MCP process; both call the same shared services (resolver, router, LLM adapter, versions, "
           "evals, compare, memory, the agent loop and pipelines), which use one store, the AI providers and the agent tools.")


# ─── Request flows (ARCHITECTURE.md) ──────────────────────────────────────────

def chat_flow() -> None:
    s = Svg(1200, 0)
    header(s, "Chat from the Web UI, Streamed", "One question from the chat page to the AI and back, token by token")
    actors = [("sky", "monitor", "Browser", "chat page"), ("sky", "route", "Next.js", "proxy.ts"), ("blue", "gear", "FastAPI", "routes/chat.py"),
              ("blue", "layers", "Resolver", "gem_service"), ("gray", "db", "Store", "SQLite, Supabase"), ("green", "db", "Memory", "memory_service"),
              ("purple", "route", "Router", "router.py"), ("purple", "cpu", "LLM adapter", "llm_service"), ("purple", "cloud", "AI", "local or online")]
    y = sequence(s, 108, actors, [
        ("msg", 0, 1, "POST /api/chat {gem_name, messages, variables, stream}"),
        ("self", 1, "adds X-API-Key"),
        ("msg", 1, 2, "POST /chat (rewritten)"),
        ("self", 2, "require_api_key"),
        ("msg", 2, 3, "resolve_gem(name, variables)"),
        ("loop", "once per gem in the reference tree", 3, 4),
        ("msg", 3, 4, "the active gem by name"),
        ("reply", 4, 3, "row"),
        ("end",),
        ("reply", 3, 2, "prompt: references expanded, blanks checked and filled, examples in"),
        ("msg", 2, 4, "get_gem_by_name: kind, pin, memory flag"),
        ("opt", "the gem remembers earlier work", 2, 5),
        ("msg", 2, 5, "recall_block(last message)"),
        ("reply", 5, 2, "<memory> block of the top matches"),
        ("end",),
        ("msg", 2, 6, "choose(gem, overrides)"),
        ("reply", 6, 2, "provider, model and the reason"),
        ("msg", 2, 7, "complete_stream(system, messages, model, provider)"),
        ("msg", 7, 8, "streaming request"),
        ("reply", 8, 7, "text deltas"),
        ("reply", 7, 2, "chunks"),
        ("reply", 2, 0, 'text/event-stream: data: {"content": ...} ... data: [DONE]'),
    ])
    benefits(s, y + 10, ["The browser never holds a key", "Blank errors stop it with a 400", "The router says why it picked",
                         "Provider errors become a fixed 502"], "Key points", "check")
    s.h = int(y + 100)
    s.save("lapidary-chat-flow.svg", "Chat from the Web UI, Streamed",
           "The browser posts to the Next.js proxy, which adds the API key and forwards to FastAPI. The route resolves the gem "
           "(one store query per gem in the tree), adds remembered context when the gem asks for it, asks the router which AI to use, "
           "and streams the provider's text back to the browser as server-sent events.")


def mcp_flow() -> None:
    s = Svg(1200, 0)
    header(s, "A Tool Call from an MCP Client", "Claude Desktop or Cursor starts the stdio server and calls the same services directly")
    actors = [("white", "plug", "MCP client", "Claude, Cursor"), ("purple", "plug", "mcp_server.py", "stdio process"), ("blue", "layers", "Resolver", "gem_service"),
              ("gray", "db", "Store", "SQLite or Supabase"), ("purple", "route", "Router", "router.py"), ("purple", "cpu", "LLM adapter", "llm_service"),
              ("purple", "cloud", "AI", "local or online")]
    y = sequence(s, 108, actors, [
        ("msg", 0, 1, "tools/call resolve_gem_prompt {name, variables}"),
        ("msg", 1, 2, "resolve_gem_detailed(name, variables, strict=False)"),
        ("loop", "once per gem in the reference tree", 2, 3),
        ("msg", 2, 3, "the active gem by name"),
        ("reply", 3, 2, "row"),
        ("end",),
        ("reply", 2, 1, "prompt, referenced gems, blanks used, defaulted and missing"),
        ("reply", 1, 0, "{gem_name, resolved_prompt, referenced_gems, variables_missing}"),
        ("msg", 0, 1, "tools/call chat_with_gem {gem_name, message}"),
        ("msg", 1, 2, "resolve_gem, then get_gem_by_name"),
        ("msg", 1, 4, "choose(gem, overrides)"),
        ("reply", 4, 1, "provider, model and the reason"),
        ("msg", 1, 5, "complete(system, [message], model, provider)"),
        ("msg", 5, 6, "request"),
        ("reply", 6, 5, "completion"),
        ("reply", 1, 0, "{gem_name, response, model, provider}"),
    ])
    benefits(s, y + 10, ["No HTTP and no key check in stdio", "Credentials come from backend/.env", "Same resolver and router as REST",
                         "Over HTTP it is /mcp, behind the key"], "Key points", "check")
    s.h = int(y + 100)
    s.save("lapidary-mcp-flow.svg", "A Tool Call from an MCP Client",
           "An MCP client calls resolve_gem_prompt or chat_with_gem over stdio; mcp_server.py calls the resolver, the router and the "
           "LLM adapter directly in its own process and returns the result, without HTTP or the API key check.")


def agent_flow() -> None:
    s = Svg(1200, 0)
    header(s, "Agent Runs", "A gem of kind agent keeps calling tools until it answers without one, recording every step")
    actors = [("white", "code", "Caller", "REST, MCP, chat"), ("blue", "loop", "run_agent", "agents/runner.py"), ("blue", "layers", "Resolver", "gem_service"),
              ("purple", "route", "Router", "and memory"), ("purple", "cpu", "LLM adapter", "complete_turn"), ("purple", "cloud", "AI", "with tools"),
              ("pink", "tool", "Tools", "registry, MCP"), ("gray", "db", "Run store", "runs, run_events")]
    y = sequence(s, 108, actors, [
        ("msg", 0, 1, "run_agent(gem, message, variables)"),
        ("msg", 1, 2, "resolve_gem_detailed, get_gem_by_name"),
        ("msg", 1, 3, "choose(gem); recall memory if the gem asks"),
        ("msg", 1, 7, "insert run (running), event run_started"),
        ("loop", "until it answers without tools, or AGENT_MAX_STEPS", 1, 7),
        ("msg", 1, 4, "complete_turn(system, messages, tools)"),
        ("msg", 4, 5, "messages with tools (Anthropic) or functions (OpenAI)"),
        ("reply", 5, 4, "text and zero or more tool calls"),
        ("reply", 4, 1, "ToolTurn, one neutral shape"),
        ("msg", 1, 7, "event model_turn"),
        ("alt", "tool calls present", 1, 7),
        ("note", 1, 7, ["A risky tool without allow_risky pauses the run:",
                        "status waiting_approval, loop state saved in runs.state, event approval_requested.",
                        "POST /runs/{id}/approve resumes it: approved, the call runs; denied, the model gets an error."], "orange"),
        ("msg", 1, 6, "execute each call; unknown or denied: an error string"),
        ("reply", 6, 1, "result text, capped at AGENT_TOOL_RESULT_MAX_CHARS"),
        ("msg", 1, 7, "events tool_call, tool_result"),
        ("self", 1, "append results in the provider's shape"),
        ("end",),
        ("end",),
        ("msg", 1, 7, "event run_finished; status, output, steps, tokens"),
        ("msg", 1, 3, "observe_run: keep a memory of what happened"),
        ("reply", 1, 0, "RunResult (run and events), or the events as SSE while it runs"),
    ])
    benefits(s, y + 10, ["A tool error never escapes the run", "Risky tools wait for a person", "Every turn is an event you can replay",
                         "Nothing held in memory between calls"], "Key points", "check")
    s.h = int(y + 100)
    s.save("lapidary-agent-flow.svg", "Agent Runs",
           "run_agent resolves the gem, picks the AI, records the run, then loops: the model answers with text and tool calls, "
           "tools run (risky ones pause for approval until POST /runs/{id}/approve), every turn and call is an event, "
           "and the run ends when the model answers without a tool or the step cap is reached.")


# ─── Gem composition and resolution (ARCHITECTURE.md) ─────────────────────────

def composition() -> None:
    s = Svg(1200, 0)
    header(s, "Gems Compose by Reference", "A {{gem:name}} tag pastes another gem in; the seed library leans on base_assistant")
    cw, gap = (1120 - 5 * 14) / 6, 14
    prompts = [("code_reviewer", "{language}"), ("creative_writer", "{style} {tone} {genre}"), ("study_buddy", "{subject} {level}"),
               ("writing_coach", "{audience}"), ("research_assistant", "{goal}"), ("adversarial_reviewer", "a gate, no blanks")]
    agents = [("gem_librarian", "no blanks"), ("windows_operator", "{task}"), ("rea_analyst", "{target_app} {feature}"),
              ("program_builder", "{description} {folder}"), ("test_runner", "a gate, no blanks")]

    # engineering_lead above code_reviewer
    box(s, 40, 108, cw, 58, "sky", "engineering_lead", ["{team_size}"], title_size=13.5, center=True, shadow=True)
    s.arrow([(40 + cw / 2, 166), (40 + cw / 2, 206)])
    plate(s, 40 + cw / 2 + 92, 192, "{{gem:code_reviewer}}", 12)
    for i, (theme, label) in enumerate([("sky", "prompt: answers once"), ("purple", "assistant: uses tools step by step")]):
        fill, stroke, accent = THEMES[theme]
        lx = 870 if i == 0 else 870
        ly = 118 + i * 26
        s.rect(lx, ly, 22, 16, "#ffffff", stroke, r=4, sw=1.8)
        s.text(lx + 32, ly + 13, label, 13, 500, INK)

    y1 = 208
    for i, (name, blanks) in enumerate(prompts):
        x = 40 + i * (cw + gap)
        box(s, x, y1, cw, 58, "sky", name, [blanks], title_size=13.5, center=True, shadow=True)
        s.add(f'<path d="M{x + cw / 2:.1f} {y1 + 58} V{y1 + 84}" stroke="{ARROW}" stroke-width="2" fill="none"/>')
    s.add(f'<path d="M{40 + cw / 2:.1f} {y1 + 84} H{40 + 5 * (cw + gap) + cw / 2:.1f}" stroke="{ARROW}" stroke-width="2" fill="none"/>')
    s.arrow([(600, y1 + 84), (600, y1 + 110)])

    # base_assistant
    by = y1 + 112
    s.rect(390, by, 420, 74, "#eef4fe", "#3b82f6", r=14, sw=2.2, shadow=True)
    s.icon("layers", 424, by + 37, THEMES["blue"][2], 26, badge="#ffffff")
    s.text(452, by + 32, "base_assistant", 19, 800, INK)
    s.text(452, by + 54, "the shared voice and rules • no blanks, no references", 12.5, 400, MUTED)
    plate(s, 700, y1 + 100, "{{gem:base_assistant}}", 12)

    y3 = by + 140
    s.arrow([(600, y3 - 26), (600, by + 76)])
    aw = (1120 - 4 * 14) / 5
    s.add(f'<path d="M{40 + aw / 2:.1f} {y3 - 26} H{40 + 4 * (aw + 14) + aw / 2:.1f}" stroke="{ARROW}" stroke-width="2" fill="none"/>')
    for i, (name, blanks) in enumerate(agents):
        x = 40 + i * (aw + 14)
        s.add(f'<path d="M{x + aw / 2:.1f} {y3} V{y3 - 26}" stroke="{ARROW}" stroke-width="2" fill="none"/>')
        box(s, x, y3, aw, 58, "purple", name, [blanks], title_size=13.5, center=True, shadow=True)

    # Stand-alone gems
    sy = y3 + 86
    zone(s, 40, sy, 1120, 112, "gray", "spark", "Stand alone", "no references, used as they are")
    alone = [("summarizer", "{depth} {target_length}"), ("prompt_enhancer", "rewrites a prompt"), ("memory_summarizer", "digests a run for memory"),
             ("build_and_check", "builder for a pipeline")]
    zw = (1080 - 3 * 14) / 4
    for i, (name, sub) in enumerate(alone):
        box(s, 60 + i * (zw + 14), sy + 44, zw, 54, "gray", name, [sub], title_size=13.5, center=True)

    benefits(s, sy + 132, ["A reference is plain text in the prompt", "Resolved by name when it is used", "Edit base_assistant: 12 gems change",
                           "Blanks from every level fill together"], "Key points", "check")
    s.h = int(sy + 222)
    s.save("lapidary-composition.svg", "Gems Compose by Reference",
           "engineering_lead embeds code_reviewer; six prompt gems and five assistant gems embed base_assistant; summarizer, prompt_enhancer, "
           "memory_summarizer and build_and_check stand alone.")


def resolution() -> None:
    s = Svg(1200, 0)
    header(s, "Resolving engineering_lead", 'with language = "Python" and team_size = "4"')
    steps = [
        ("blue", "layers", "Load engineering_lead", ["checks depth (10 at most)", "and the chain for cycles", "before any query"]),
        ("blue", "flow", "Expand code_reviewer", ["found {{gem:code_reviewer}}:", "recurse, depth 1; its", "examples get a placeholder"]),
        ("blue", "flow", "Expand base_assistant", ["found {{gem:base_assistant}}:", "recurse, depth 2; it has", "no references, so it returns"]),
        ("blue", "layers", "Splice back up", ["base text into", "code_reviewer, that into", "engineering_lead"]),
        ("purple", "pen", "Collect the blanks", ["{language}, {team_size}", "specs from embedded gems,", "the outer gem wins"]),
        ("purple", "check", "Check and default", ["required, type, choices;", "empty ones get defaults;", "errors stop with a 400"]),
        ("purple", "spark", "Fill in one pass", ["every blank at every level", "a value with braces", "is never filled again"]),
        ("green", "chat", "Swap in examples", ["<examples> at each", "{{examples}} marker,", "as literal text"]),
    ]
    w, gap = 250, 40
    for i, (theme, icon, title, lines) in enumerate(steps):
        row, col = divmod(i, 4)
        col = col if row == 0 else 3 - col
        x = 40 + col * (w + gap)
        y = 112 + row * 186
        fill, stroke, accent = THEMES[theme]
        s.rect(x, y, w, 140, fill, stroke, shadow=True)
        numbered(s, x + 26, y + 28, i + 1, accent, 13)
        s.text(x + 48, y + 33, title, 14.5, 800, INK)
        for j, line in enumerate(lines):
            s.text(x + 20, y + 66 + j * 21, line, 13, 400, "#344054")
        if i in (0, 1, 2):
            s.arrow([(x + w + 2, y + 70), (x + w + gap - 2, y + 70)])
        if i in (4, 5, 6):
            s.arrow([(x - 2, y + 70), (x - gap + 2, y + 70)])
    s.arrow([(40 + 3 * (w + gap) + w / 2, 252), (40 + 3 * (w + gap) + w / 2, 298)])
    s.text(70, 104, "REFERENCES FIRST", 11.5, 800, THEMES["blue"][2])
    s.text(70, 290, "THEN BLANKS AND EXAMPLES", 11.5, 800, THEMES["purple"][2])
    s.arrow([(40 + w / 2, 438), (40 + w / 2, 478)])

    # Result
    s.rect(40, 480, 1120, 92, "#ffffff", "#34a853", r=14, sw=2.2, shadow=True)
    s.add('<circle cx="80" cy="526" r="16" fill="#34a853"/><path d="M72 526l5 5 10-10" stroke="#fff" stroke-width="2.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    s.text(108, 516, "The resolved prompt", 19, 800, INK)
    s.text(108, 540, "with referenced_gems [code_reviewer, base_assistant], and the blanks used, defaulted and missing", 13.5, 400, MUTED)
    s.text(108, 560, "chat, runs, tests and MCP all start here; a past version from the history resolves the same way", 13.5, 400, MUTED)

    benefits(s, 594, ["At most 10 levels deep", "A cycle stops before any query", "References first, blanks last", "Examples stay literal text"], "Safety rails", "shield")
    s.h = 690
    s.save("lapidary-resolution.svg", "Resolving engineering_lead",
           "Load engineering_lead, expand code_reviewer and then base_assistant depth first, splice the text back up, collect the blanks "
           "and their specs, check and default them, fill every blank in one pass, swap in the worked examples, and return the prompt "
           "with the referenced gems.")


# ─── Data model (ARCHITECTURE.md) ─────────────────────────────────────────────

def data_model() -> None:
    s = Svg(1200, 0)
    header(s, "Data Model", "The same tables in SQLite on this PC and in Supabase Postgres • RLS on, no policies")
    W = 320
    c1, c2, c3 = 40, 440, 840
    top = 112
    gems = [("id", "uuid", "PK"), ("name", "text, unique", "UQ"), ("description", "text", ""), ("system_prompt", "{blanks}, {{gem:}}", ""),
            ("model", "text", ""), ("provider", "anthropic, openai, local, auto", ""), ("kind", "prompt or agent", ""), ("tools", "text[]", ""),
            ("tags", "text[], GIN index", ""), ("variables", "text[], derived", ""), ("variable_specs", "json", ""), ("examples", "json", ""),
            ("memory", "bool", ""), ("is_active", "bool, soft delete", ""), ("created_at", "timestamptz", ""), ("updated_at", "trigger", "")]
    hg = table_card(s, c2, top, W, "blue", "layers", "gems", gems)

    left = [("clock", "gem_versions", [("id", "uuid", "PK"), ("gem_id", "uuid", "FK"), ("version", "int, unique per gem", ""),
                                       ("snapshot", "json of the gem", ""), ("note", "text", ""), ("source", "api, mcp, revert, baseline", ""), ("created_at", "timestamptz", "")],
             "append only; a revert is a new row"),
            ("check", "eval_cases", [("id", "uuid", "PK"), ("gem_id", "uuid", "FK"), ("name", "text", ""), ("input", "text", ""),
                                     ("variables", "json", ""), ("check", "contains ... judge", ""), ("expected", "text", "")], None),
            ("chart", "eval_runs", [("id", "uuid", "PK"), ("gem_id", "uuid", "FK"), ("gem_version", "int", ""), ("provider, model", "text", ""),
                                    ("passed, total", "int", ""), ("results", "json per case", ""), ("baseline", "bool", "")], None)]
    y = top
    lefts = []
    for icon, name, cols, note in left:
        h = table_card(s, c1, y, W, "sky", icon, name, cols, note)
        lefts.append((y, h))
        y += h + 22

    right = [("loop", "runs", [("id", "uuid", "PK"), ("gem_id", "uuid", "FK"), ("gem_name", "text", ""), ("status", "running ... max_steps", ""),
                               ("model, provider", "text", ""), ("input, output", "text", ""), ("steps, tokens", "int", ""), ("state", "json while waiting", ""),
                               ("created_at, finished_at", "timestamptz", "")], None),
             ("flow", "run_events", [("id", "uuid", "PK"), ("run_id", "uuid, cascade", "FK"), ("seq", "int, unique per run", ""), ("type", "text", ""), ("data", "json", "")], None),
             ("db", "memories", [("id", "uuid", "PK"), ("kind", "observation ... note", ""), ("text", "text", ""), ("source", "run, chat, mcp, ...", ""),
                                 ("gem_name, run_id", "loose links", ""), ("tags, scope", "text", ""), ("search", "FTS5 or tsvector", "")], None)]
    y = top
    rights = []
    for icon, name, cols, note in right:
        h = table_card(s, c3, y, W, "purple" if name != "memories" else "green", icon, name, cols, note)
        rights.append((y, h))
        y += h + 22
    bottom_right = y

    py = top + hg + 40
    hp = table_card(s, c2, py, W, "orange", "flow", "pipelines", [("id", "uuid", "PK"), ("name", "text, unique", "UQ"), ("builder", "gem name", ""),
                                                                  ("gates", "json", ""), ("max_attempts", "int", ""), ("acceptance", "bool", "")])
    py2 = py + hp + 40
    hr = table_card(s, c2, py2, W, "orange", "loop", "pipeline_runs", [("id", "uuid", "PK"), ("pipeline_name", "by name", ""), ("status", "running ... passed", ""),
                                                                       ("input, output", "text", ""), ("attempts", "json: run ids, verdicts", ""), ("state, waiting_run_id", "while it waits", "")])

    # Relationships. Solid: a foreign key, one to many. Dashed: a link by name or inside JSON.
    trunk = c2 - 22
    last = lefts[-1][0] + 19
    s.add(f'<path d="M{c2} {top + 60} H{trunk} M{trunk} {top + 19} V{last}" stroke="{ARROW}" stroke-width="1.9" fill="none"/>')
    for ly, lh in lefts:
        s.arrow([(trunk, ly + 19), (c1 + W + 2, ly + 19)], sw=1.9)
        plate(s, (c1 + W + trunk) / 2 + 2, ly + 9, "1 : n", 11)
    rel_y = rights[0][0] + 19
    s.arrow([(c2 + W, top + 60), (c2 + W + 40, top + 60), (c2 + W + 40, rel_y), (c3 + 2, rel_y)], sw=1.9)
    plate(s, c2 + W + 40, rel_y + 30, "1 : n", 11)
    s.arrow([(c3 + W / 2, rights[0][0] + rights[0][1]), (c3 + W / 2, rights[1][0] - 2)], sw=1.9)
    plate(s, c3 + W / 2 + 34, rights[1][0] - 6, "1 : n", 11)
    mem_y = rights[2][0] + 19
    s.add(f'<path d="M{c3 + W} {mem_y} H1180 V{rights[0][0] + 60}" stroke="#6b84d9" stroke-width="1.6" stroke-dasharray="6 5" fill="none"/>')
    s.arrow([(1180, rights[0][0] + 60), (c3 + W + 2, rights[0][0] + 60)], color="#6b84d9", sw=1.6)
    s.arrow([(c2 + W / 2, py + hp), (c2 + W / 2, py2 - 2)], color="#6b84d9", dash=True, sw=1.6)
    plate(s, c2 + W / 2 + 64, py2 - 12, "1 : n, by name", 11)
    s.add(f'<path d="M{c2 + W} {py2 + 145} H{c3 - 22} V{rights[0][0] + 100}" stroke="#6b84d9" stroke-width="1.6" stroke-dasharray="6 5" fill="none"/>')
    s.arrow([(c3 - 22, rights[0][0] + 100), (c3 - 2, rights[0][0] + 100)], color="#6b84d9", sw=1.6)
    s.text(c2 + W / 2, py2 + hr + 22, "dashed: a link by name or inside JSON, no foreign key", 12, 500, "#6b84d9", "middle")

    end = max(py2 + hr + 30, bottom_right, lefts[-1][0] + lefts[-1][1]) + 26
    benefits(s, end, ["References between gems are text", "Deletes are soft: is_active", "Versions are never edited",
                      "Service role only, no anon access"], "Key points", "check")
    s.h = int(end + 92)
    s.save("lapidary-data-model.svg", "Data Model",
           "gems is the centre: gem_versions, eval_cases, eval_runs and runs point at it; run_events belong to runs; memories link to runs "
           "and gems loosely; pipelines own pipeline_runs by name, whose attempts hold run ids.")


# ─── Trust boundaries (ARCHITECTURE.md) ───────────────────────────────────────

def trust() -> None:
    s = Svg(1200, 0)
    header(s, "Trust Boundaries", "Where each secret lives, and where a request is checked")
    cols = [(40, 250, "white", "person", "Callers"), (310, 250, "sky", "route", "Edge"), (580, 300, "blue", "gear", "Backend processes"), (900, 260, "gray", "db", "Data and AI")]
    for x, w, theme, icon, title in cols:
        zone(s, x, 104, w, 596, theme, icon, title)

    rows = [130 + 30, 290, 420, 545]
    # Row 1: web
    box(s, 56, rows[0], 218, 76, "white", "Web UI", ["holds no secrets", "calls /api on its own origin"], shadow=True)
    box(s, 326, rows[0], 218, 76, "sky", "Next.js server", ["proxy.ts adds GEMS_API_KEY", "holds that key only"], shadow=True)
    box(s, 596, rows[0], 268, 96, "blue", "FastAPI service", ["checks the key on every route", "but / and /health; per-client keys", "holds DB and AI keys"], shadow=True)
    s.arrow([(274, rows[0] + 38), (326, rows[0] + 38)])
    s.arrow([(544, rows[0] + 38), (596, rows[0] + 38)])
    s.icon("shield", 570, rows[0] + 38, THEMES["green"][2], 20, badge="#ecf8ef")

    # Row 2: MCP over HTTP
    box(s, 56, rows[1], 218, 76, "white", "MCP client over HTTP", ["Claude, ChatGPT connectors", "sends its own key"], shadow=True)
    box(s, 596, rows[1], 268, 76, "purple", "/mcp on the same API", ["same key check", "allowed hosts for a tunnel"], shadow=True)
    s.arrow([(274, rows[1] + 38), (596, rows[1] + 38)])
    plate(s, 435, rows[1] + 30, "X-API-Key or bearer", 12)
    s.icon("shield", 570, rows[1] + 38, THEMES["green"][2], 20, badge="#ecf8ef")

    # Row 3: MCP over stdio
    box(s, 56, rows[2], 218, 76, "white", "MCP client over stdio", ["Claude Desktop, Cursor", "starts the process itself"], shadow=True)
    box(s, 326, rows[2], 218, 76, "sky", "stdin and stdout", ["no network port", "nothing to intercept"], shadow=False)
    box(s, 596, rows[2], 268, 92, "pink", "mcp_server.py", ["no key check: trusts whoever", "can start it on this machine", "reads backend/.env"], shadow=True)
    s.arrow([(274, rows[2] + 38), (326, rows[2] + 38)])
    s.arrow([(544, rows[2] + 38), (596, rows[2] + 38)])

    # Row 4: the console
    box(s, 56, rows[3], 218, 96, "white", "Lapidary Console", ["your keys encrypted with", "Windows safeStorage", "in your profile"], shadow=True)
    box(s, 326, rows[3], 218, 96, "sky", "127.0.0.1 only", ["backend and UI run as", "sidecars with a key made", "on first start"], shadow=False)
    box(s, 596, rows[3], 268, 96, "orange", "Lapidary Helper (SYSTEM)", ["local pipe, no remote clients", "allowlisted installs only", "verified console updates"], shadow=True)
    s.arrow([(274, rows[3] + 40), (326, rows[3] + 40)])
    s.add(f'<path d="M165 {rows[3] + 96} V{rows[3] + 122} H730" stroke="#6b84d9" stroke-width="1.6" stroke-dasharray="6 5" fill="none"/>')
    s.arrow([(730, rows[3] + 122), (730, rows[3] + 98)], color="#6b84d9", sw=1.6)
    plate(s, 440, rows[3] + 126, "install and update requests over the pipe", 11.5)

    # Data and AI
    box(s, 916, rows[0], 228, 96, "gray", "Supabase Postgres", ["RLS on, no policies:", "only the service role key", "reads or writes"], shadow=True)
    box(s, 916, rows[1] + 30, 228, 76, "gray", "SQLite file", ["on this PC, in your", "profile when the console runs"], shadow=True)
    box(s, 916, rows[2] + 30, 228, 96, "purple", "AI providers", ["Anthropic, OpenAI: your keys", "local models: no key,", "nothing leaves the PC"], shadow=True)
    # every backend process reaches the store and the AI the same way
    s.add(f'<path d="M864 {rows[0] + 48} H886 M864 {rows[1] + 38} H886 M864 {rows[2] + 46} H886 M886 {rows[0] + 48} V{rows[2] + 78}" stroke="{ARROW}" stroke-width="2" fill="none"/>')
    s.arrow([(886, rows[0] + 48), (914, rows[0] + 48)])
    s.arrow([(886, rows[1] + 68), (914, rows[1] + 68)])
    s.arrow([(886, rows[2] + 78), (914, rows[2] + 78)])

    benefits(s, 720, ["The browser never sees a key", "Every REST and /mcp call needs a key", "stdio MCP trusts who starts it",
                      "The helper runs only allowlisted installs"], "Key points", "shield")
    s.h = 810
    s.save("lapidary-trust.svg", "Trust Boundaries",
           "The browser holds no secrets; the Next.js proxy adds the API key; FastAPI checks it on every route and at /mcp and holds the "
           "database and AI keys; the stdio MCP process has no key check and trusts whoever starts it; the console keeps keys in Windows "
           "safeStorage and runs the backend on 127.0.0.1; the helper service only runs allowlisted installs; Supabase allows only the service role.")


# ─── Deployment topologies (ARCHITECTURE.md) ──────────────────────────────────

def deployment() -> None:
    s = Svg(1200, 0)
    header(s, "Deployment Topologies", "From one Windows PC to a hosted split deploy: same code, same store interface")
    cols = [
        ("blue", "window", "Windows console", "one PC, one installer", [("window", "Lapidary Console", "Electron, per machine"), ("gear", "lapidary-backend.exe", "127.0.0.1:8000"),
                                                                     ("monitor", "Web UI", "Next standalone :3000"), ("shield", "Lapidary Helper", "installs and updates"),
                                                                     ("plug", "backend.exe --mcp", "for Claude Desktop")]),
        ("green", "code", "Local development", "any OS", [("gear", "uvicorn app.main:app", "--reload :8000"), ("monitor", "next dev", ":3000"),
                                                        ("plug", "python mcp_server.py", "started by the client")]),
        ("orange", "layers", "Docker Compose", "one host", [("gear", "backend image", "python:3.12-slim"), ("monitor", "frontend image", "node:24-alpine"),
                                                         ("check", "waits for /health", "then starts the UI")]),
        ("purple", "cloud", "Split deploy", "hosted", [("gear", "Backend", "Fly.io, Railway or Render"), ("monitor", "Frontend on Vercel", "BACKEND_URL set"),
                                                     ("route", "/api/* rewrite", "frontend to backend")]),
    ]
    w, gap = (1120 - 3 * 14) / 4, 14
    for i, (theme, icon, title, sub, chips) in enumerate(cols):
        x = 40 + i * (w + gap)
        fill, stroke, accent = THEMES[theme]
        s.rect(x, 104, w, 414, fill, stroke, shadow=True)
        s.icon(icon, x + 28, 134, accent, 22, badge="#ffffff")
        s.text(x + 50, 140, title, 16, 800, INK)
        s.text(x + 50, 160, sub, 12.5, 400, MUTED)
        for j, (cicon, ctitle, csub) in enumerate(chips):
            s.chip(x + 14, 178 + j * 60, w - 28, 50, "white", cicon, ctitle, csub)
        store = ["SQLite in your profile", "SQLite, or Supabase from .env", "Supabase from .env", "Supabase cloud"][i]
        s.add(f'<line x1="{x + 16}" y1="486" x2="{x + w - 16}" y2="486" stroke="{stroke}" stroke-width="1.2"/>')
        s.text(x + 18, 506, "stores in", 12, 700, accent)
        s.text(x + 82, 506, store, 12.5, 500, INK)
    # Stores
    s.rect(40, 574, 545, 70, "#f2f4f7", "#9aa4b2", r=12, sw=1.8, shadow=True)
    s.icon("db", 72, 609, THEMES["gray"][2], 24, badge="#ffffff")
    s.text(100, 604, "SQLite file", 17, 800, INK)
    s.text(100, 625, "the default without a Supabase project • the console keeps it in your profile", 12.5, 400, MUTED)
    s.rect(615, 574, 545, 70, "#f2f4f7", "#9aa4b2", r=12, sw=1.8, shadow=True)
    s.icon("cloud", 647, 609, THEMES["gray"][2], 24, badge="#ffffff")
    s.text(675, 604, "Supabase Postgres", 17, 800, INK)
    s.text(675, 625, "set SUPABASE_URL and the service role key • GEMS_STORAGE=supabase", 12.5, 400, MUTED)
    cx = [40 + i * (w + gap) + w / 2 for i in range(4)]
    s.arrow([(cx[0], 518), (cx[0], 572)])
    s.arrow([(cx[1] - 30, 518), (cx[1] - 30, 572)])
    s.arrow([(cx[1] + 30, 518), (cx[1] + 30, 546), (700, 546), (700, 572)], dash=True, sw=1.8)
    plate(s, cx[1] + 120, 550, "or", 11.5)
    s.arrow([(cx[2], 518), (cx[2], 572)])
    s.arrow([(cx[3], 518), (cx[3], 572)])
    plate(s, cx[2], 550, "from .env", 11.5)
    benefits(s, 664, ["One installer on Windows", "SQLite needs no setup", "Supabase when you host it", "MCP over stdio, or at /mcp"], "Key points", "check")
    s.h = 754
    s.save("lapidary-deployment.svg", "Deployment Topologies",
           "Four ways to run Lapidary: the Windows console on one PC with SQLite, local development with uvicorn, next dev and the stdio MCP "
           "server, Docker Compose with a backend and a frontend image, and a split deploy with the backend on Fly.io, Railway or Render and the "
           "frontend on Vercel; the store is a SQLite file or Supabase Postgres.")


if __name__ == "__main__":
    architecture()
    flow()
    components()
    chat_flow()
    mcp_flow()
    agent_flow()
    composition()
    resolution()
    data_model()
    trust()
    deployment()
    print("wrote", ", ".join(p.name for p in sorted(OUT.glob("*.svg"))))
