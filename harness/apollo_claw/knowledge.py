"""Simple local knowledge search over Markdown files."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple


def iter_markdown(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return root.rglob("*.md")


def search(root: Path, query: str, limit: int = 5) -> List[Tuple[Path, str]]:
    terms = [t.lower() for t in query.replace("/", " ").split() if t.strip()]
    results: List[Tuple[Path, str]] = []
    for path in iter_markdown(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lower = text.lower()
        score = sum(lower.count(t) for t in terms)
        if score:
            idx = lower.find(terms[0]) if terms else 0
            start = max(0, idx - 160)
            results.append((path, text[start:start + 600]))
    results.sort(key=lambda item: item[0].name)
    return results[:limit]
