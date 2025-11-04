# app/runtime/nodes/reply_extract.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from pocketflow import Node

_FOLLOWUP_KEYS = ("followups", "questions")
_WARNING_KEYS = ("warnings", "cautions", "alerts")
_FOLLOWUP_PATTERNS = [
    re.compile(r"(?i)\bfollow[-\s]?ups?\b[:：]\s*(.*)"),
    re.compile(r"(?i)\bquestions?\b[:：]\s*(.*)"),
]
_BULLET_RE = re.compile(r"^[-*•·]\s+")
_SPLIT_RE = re.compile(r"[;、·•\-–—]\s*|\s{2,}")

def _dedup_norm(items: List[str]) -> List[str]:
    out, seen = [], set()
    for x in items:
        s = str(x).strip()
        if not s:
            continue
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out

def _extract_inline(line: str) -> List[str]:
    items: List[str] = []
    for p in _FOLLOWUP_PATTERNS:
        m = p.search(line)
        if m:
            parts = [y.strip(" -•·\t") for y in _SPLIT_RE.split(m.group(1)) if y.strip()]
            items.extend(parts)
    return items

def _heuristic_followups(text: str) -> List[str]:
    cands: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _BULLET_RE.match(line):
            cands.append(_BULLET_RE.sub("", line))
            continue
        cands.extend(_extract_inline(line))
    return _dedup_norm(cands)

def _from_json_block(reply: str) -> tuple[List[str], List[str]]:
    try:
        data = json.loads(reply)
    except Exception:
        return [], []
    fups: List[str] = []
    warns: List[str] = []
    if isinstance(data, dict):
        for k in _FOLLOWUP_KEYS:
            v = data.get(k)
            if isinstance(v, list):
                fups.extend(str(x) for x in v)
                break
        for k in _WARNING_KEYS:
            v = data.get(k)
            if isinstance(v, list):
                warns.extend(str(x) for x in v)
                break
    elif isinstance(data, list):
        fups.extend(str(x) for x in data)
    return _dedup_norm(fups), _dedup_norm(warns)

class ReplyExtractNode(Node):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def exec(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        reply = shared.get("assistant_reply") or ""
        followups, warnings = _from_json_block(reply)
        if not followups:
            followups = _heuristic_followups(reply)
        shared["followups"] = followups
        base_warnings = shared.get("warnings") or []
        merged = _dedup_norm([*base_warnings, *warnings])
        shared["warnings"] = merged
        return shared
