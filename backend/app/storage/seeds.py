"""
Seed gems for a fresh SQLite database, read from supabase/schema.sql so the
seeds have one source. The parser understands exactly the literal forms the
seed section uses: 'strings' with '' escapes, ARRAY['a', 'b'] and ARRAY[]::TEXT[].
"""
from __future__ import annotations
import pathlib

COLUMNS = ["name", "description", "system_prompt", "model", "provider", "tags", "variables", "kind", "tools"]


class _Scanner:
    def __init__(self, text: str) -> None:
        self.s, self.i = text, 0

    def skip_ws(self) -> None:
        while self.i < len(self.s):
            if self.s.startswith("--", self.i):
                nl = self.s.find("\n", self.i)
                self.i = len(self.s) if nl == -1 else nl + 1
            elif self.s[self.i].isspace():
                self.i += 1
            else:
                break

    def peek(self, token: str) -> bool:
        self.skip_ws()
        return self.s.startswith(token, self.i)

    def expect(self, token: str) -> None:
        if not self.peek(token):
            raise ValueError(f"expected {token!r} at {self.i}: {self.s[self.i:self.i + 30]!r}")
        self.i += len(token)

    def string(self) -> str:
        self.expect("'")
        out = []
        while True:
            j = self.s.find("'", self.i)
            if j == -1:
                raise ValueError("unterminated string")
            out.append(self.s[self.i:j])
            if self.s.startswith("''", j):
                out.append("'")
                self.i = j + 2
                continue
            self.i = j + 1
            return "".join(out)

    def array(self) -> list[str]:
        self.expect("ARRAY[")
        items: list[str] = []
        while not self.peek("]"):
            items.append(self.string())
            if self.peek(","):
                self.expect(",")
        self.expect("]")
        if self.peek("::TEXT[]"):
            self.expect("::TEXT[]")
        return items

    def value(self):
        if self.peek("ARRAY["):
            return self.array()
        if self.peek("'"):
            s = self.string()
            self.skip_ws()
            if self.s.startswith("::", self.i):          # a cast such as ::jsonb; the text is what matters
                self.i += 2
                while self.i < len(self.s) and (self.s[self.i].isalnum() or self.s[self.i] in "_[]"):
                    self.i += 1
            return s
        self.skip_ws()
        for word, val in (("true", True), ("false", False), ("NULL", None)):
            if self.s.startswith(word, self.i):
                self.i += len(word)
                return val
        j = self.i
        while j < len(self.s) and (self.s[j].isdigit() or self.s[j] == "-"):
            j += 1
        if j == self.i:
            raise ValueError(f"unexpected value at {self.i}: {self.s[self.i:self.i + 30]!r}")
        n = int(self.s[self.i:j])
        self.i = j
        return n


def parse_seed_rows(sql: str, table: str) -> list[dict]:
    """Every VALUES tuple of `INSERT INTO <table> (...)` in schema.sql, as dicts keyed by the column list."""
    marker = f"INSERT INTO {table} ("
    start = sql.find(marker)
    if start == -1:
        return []
    cols_end = sql.find(")", start)
    cols = [c.strip() for c in sql[start + len(marker):cols_end].split(",")]
    sc = _Scanner(sql)
    sc.i = sql.find("VALUES", cols_end) + len("VALUES")
    rows: list[dict] = []
    while True:
        sc.skip_ws()
        if sc.peek("ON CONFLICT") or sc.i >= len(sql) or not sc.peek("("):
            break
        sc.expect("(")
        values = []
        while not sc.peek(")"):
            values.append(sc.value())
            if sc.peek(","):
                sc.expect(",")
        sc.expect(")")
        rows.append(dict(zip(cols, values)))
        if sc.peek(","):
            sc.expect(",")
    return rows


def parse_seed_gems(sql: str) -> list[dict]:
    """Every VALUES tuple of the gems INSERT in schema.sql, as dicts keyed by COLUMNS."""
    gems = parse_seed_rows(sql, "gems")
    for row in gems:
        row.setdefault("kind", "prompt")
        row.setdefault("tools", [])
    return gems


def load_seed_pipelines(path: str | pathlib.Path) -> list[dict]:
    """The pipelines INSERT in schema.sql (ADR-011 gates); gates arrive as a JSON string."""
    import json

    p = pathlib.Path(path)
    rows = parse_seed_rows(p.read_text(), "pipelines") if p.exists() else []
    for r in rows:
        if isinstance(r.get("gates"), str):
            r["gates"] = json.loads(r["gates"])
    return rows


def load_seed_gems(path: str | pathlib.Path) -> list[dict]:
    p = pathlib.Path(path)
    return parse_seed_gems(p.read_text()) if p.exists() else []
