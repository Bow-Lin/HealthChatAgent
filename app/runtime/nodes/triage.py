# app/runtime/nodes/triage.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Pattern, Dict, Any


@dataclass(frozen=True)
class TriageRule:
    """A triage rule: if pattern matches, mark the level and record a reason."""
    pattern: Pattern[str]
    level: str  # "urgent" | "non-urgent"
    reason: str


def _default_rules() -> List[TriageRule]:
    """
    Default red-flag / safety rules. You can extend or override via ctor.
    These are heuristic patterns for initial screening only.
    """
    urgent_terms = [
        r"severe chest pain",
        r"chest pain\b",
        r"difficulty breathing|shortness of breath|can't breathe",
        r"unconscious|passed out|fainted",
        r"stroke|facial droop|slurred speech|weakness on one side",
        r"heavy bleeding|uncontrolled bleeding",
        r"stiff neck with fever",
        r"seizure|convulsion",
        r"severe abdominal pain",
        r"high fever.*(infant|baby)",
        r"pregnan(t|cy).*(bleeding|severe pain)",
        r"sudden.*confusion|sudden.*vision loss",
        r"head injury.*(vomit|confusion|drowsy)",
        r"allergic reaction.*(swelling|difficulty breathing)",
    ]
    return [
        TriageRule(pattern=re.compile(p, re.I), level="urgent", reason=p.replace("|", "/"))
        for p in urgent_terms
    ]


def _normalize(text: str) -> str:
    """Simple normalization for matching."""
    return (text or "").strip().lower()


class SafetyTriageNode:
    """
    Safety triage node.
    - Reads user's free text from shared["user_text"].
    - Applies regex-based rules to detect red flags.
    - Writes:
        shared["triage_level"]   = "urgent" | "non-urgent"
        shared["triage_reasons"] = [matched_reason, ...]
        shared["warnings"]      += safety disclaimer (if not present)
    - If next nodes are wired, jumps to next_urgent or next_ok accordingly.
    """

    def __init__(
        self,
        rules: Optional[Iterable[TriageRule]] = None,
        disclaimer: Optional[str] = None,
    ) -> None:
        self.rules: List[TriageRule] = list(rules) if rules is not None else _default_rules()
        self.disclaimer = (
            disclaimer
            or "This system provides preliminary guidance only and is not a medical diagnosis. "
               "If symptoms worsen or any emergency signs appear, seek in-person care immediately."
        )
        # Flow wiring
        self._next_urgent = None
        self._next_ok = None

    # --- PocketFlow-style wiring API ---
    def on(self, cond: str, next_node: Any) -> "SafetyTriageNode":
        """Wire next node by condition: 'urgent' or 'ok'."""
        if cond not in ("urgent", "ok"):
            raise ValueError("cond must be 'urgent' or 'ok'")
        if cond == "urgent":
            self._next_urgent = next_node
        else:
            self._next_ok = next_node
        return self

    # --- Core execution ---
    async def exec(self, shared: Dict[str, Any]) -> Any:
        text = _normalize(shared.get("user_text", ""))
        matched_reasons: List[str] = []

        for rule in self.rules:
            if rule.pattern.search(text):
                if rule.level == "urgent":
                    matched_reasons.append(rule.reason)

        level = "urgent" if matched_reasons else "non-urgent"
        shared["triage_level"] = level
        shared["triage_reasons"] = matched_reasons

        # Ensure safety disclaimer is present
        warnings = shared.setdefault("warnings", [])
        if self.disclaimer not in warnings:
            warnings.append(self.disclaimer)

        # Optional: attach a short, user-facing triage note
        shared.setdefault("triage_note", _compose_triage_note(level, matched_reasons))

        # Branch to next node if wired; otherwise return gracefully
        if level == "urgent" and self._next_urgent is not None:
            return await self._next_urgent.exec(shared)
        if level == "non-urgent" and self._next_ok is not None:
            return await self._next_ok.exec(shared)
        return None


def _compose_triage_note(level: str, reasons: List[str]) -> str:
    """Generate a concise triage note for downstream usage or UI."""
    if level == "urgent":
        # Show at most 3 reasons to keep it short
        preview = ", ".join(reasons[:3]) if reasons else "red-flag criteria met"
        return f"Triage: URGENT ({preview})."
    return "Triage: non-urgent."
