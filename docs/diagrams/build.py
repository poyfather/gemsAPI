"""
Draws the two README and ARCHITECTURE diagrams as SVG infographics.

    python docs/diagrams/build.py

writes docs/diagrams/lapidary-architecture.svg and docs/diagrams/lapidary-flow.svg.
No dependencies: plain SVG with a white background, system fonts and line icons,
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


def benefits(s: Svg, y: int, items: list[str]) -> None:
    fill, stroke, accent = THEMES["green"]
    s.rect(40, y, 1120, 70, "#f3faf5", "#cfe9d6", r=12, sw=1.5)
    s.icon("chart", 72, y + 35, accent, 26)
    s.text(98, y + 42, "Key benefits", 20, 800, INK)
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


if __name__ == "__main__":
    architecture()
    flow()
    print("wrote", ", ".join(p.name for p in sorted(OUT.glob("*.svg"))))
