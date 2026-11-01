"""Small, deterministic command layer for conversational lead operations."""
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass
class LeadCommand:
    action: str
    category: str = ""
    management_terms: List[str] = None


def parse_command(prompt: str) -> LeadCommand:
    text = (prompt or "").strip().lower()
    category = "hotel" if "hotel" in text else ""
    management_terms = [
        term
        for term in ("company", "management", "managed by", "group", "chain", "corporation")
        if term in text
    ]
    if any(word in text for word in ("remove", "exclude", "delete", "filter out")):
        return LeadCommand("exclude_managed", category, management_terms or ["company"])
    if any(word in text for word in ("keep", "include", "only")):
        return LeadCommand("include_category", category, management_terms or [])
    return LeadCommand("unknown", category, management_terms or [])


def _text(row: Dict) -> str:
    return " ".join(str(value or "") for value in row.values()).lower()


def apply_command(rows: Iterable[Dict], command: LeadCommand):
    """Apply a safe, explainable command and return kept rows plus exclusions."""
    kept, excluded = [], []
    for row in rows:
        text = _text(row)
        is_category = not command.category or command.category in text
        has_management = bool(
            re.search(r"\bmanaged\s+by\b|\bmanagement\b|\bcompany\b|\bgroup\b|\bchain\b|\bcorporation\b", text)
        )
        if command.action == "exclude_managed" and is_category and has_management:
            excluded.append(dict(row, command_result="excluded_managed_business"))
        elif command.action == "include_category" and command.category and not is_category:
            excluded.append(dict(row, command_result="excluded_category"))
        else:
            kept.append(dict(row, command_result="kept"))
    return kept, excluded