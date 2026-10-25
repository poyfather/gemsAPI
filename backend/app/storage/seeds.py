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
        return self.array() if self.peek("ARRAY[") else self.string()


def parse_seed_gems(sql: str) -> list[dict]:
    """Every VALUES tuple of the gems INSERT in schema.sql, as dicts keyed by COLUMNS."""
    marker = "INSERT INTO gems ("
    start = sql.find(marker)
    if start == -1:
        return []
    cols_end = sql.find(")", start)
    cols = [c.strip() for c in sql[start + len(marker):cols_end].split(",")]
    sc = _Scanner(sql)
    sc.i = sql.find("VALUES", cols_end) + len("VALUES")
    gems: list[dict] = []
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
        row = dict(zip(cols, values))
        row.setdefault("kind", "prompt")
        row.setdefault("tools", [])
        gems.append(row)
        if sc.peek(","):
            sc.expect(",")
    return gems


def load_seed_gems(path: str | pathlib.Path) -> list[dict]:
    p = pathlib.Path(path)
    return parse_seed_gems(p.read_text()) if p.exists() else []
