from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Pattern, List, Dict, Any
from pocketflow import AsyncNode

@dataclass(frozen=True)
class TriageRule:
    pattern: Pattern[str]
    level: str
    reason: str

def _default_rules() -> List[TriageRule]:
    urgent_terms = [
        (r"severe chest pain", "出现严重胸痛"),
        (r"chest pain\b", "出现胸痛"),
        (r"difficulty breathing|short(?:ness)? of breath|can't breathe", "出现呼吸困难或气促"),
        (r"unconscious|passed out|fainted", "出现意识丧失或晕厥"),
        (r"stroke|facial droop|slurred speech|weakness on one side", "疑似中风症状"),
        (r"heavy bleeding|uncontrolled bleeding", "出现大量或无法控制的出血"),
        (r"stiff neck with fever", "发热伴随颈部僵硬"),
        (r"seizure|convulsion", "出现癫痫发作或抽搐"),
        (r"severe abdominal pain", "出现剧烈腹痛"),
        (r"high fever.*(infant|baby)", "婴幼儿持续高热"),
        (r"pregnan(t|cy).*(bleeding|severe pain)", "孕期出现出血或剧烈疼痛"),
        (r"sudden.*confusion|sudden.*vision loss", "突发意识混乱或视力丧失"),
        (r"head injury.*(vomit|confusion|drowsy)", "头部外伤伴呕吐或意识异常"),
        (r"allergic reaction.*(swelling|difficulty breathing)", "过敏反应伴肿胀或呼吸困难"),
    ]
    return [TriageRule(re.compile(p, re.I), "urgent", r) for p, r in urgent_terms]

def _normalize(s: str) -> str:
    return (s or "").strip().lower()

class SafetyTriageNode(AsyncNode):
    def __init__(self, rules: List[TriageRule] | None = None, disclaimer: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.rules = list(rules) if rules is not None else _default_rules()
        self.disclaimer = disclaimer or (
            "This system provides preliminary guidance only and is not a medical diagnosis. "
            "If symptoms worsen or any emergency signs appear, seek in-person care immediately."
        )

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        # narrow payload if you like; passthrough keeps it simple
        return shared

    async def exec_async(self, prep: Dict[str, Any]) -> Dict[str, Any]:
        text = _normalize(prep.get("user_text", ""))
        matched = [r.reason for r in self.rules if r.level == "urgent" and r.pattern.search(text)]
        level = "urgent" if matched else "ok"
        # return a pure result; no shared mutation here
        return {"level": level, "reasons": matched}

    async def post_async(self, shared: Dict[str, Any], prep: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        # commit to shared and route
        shared["triage_level"] = "urgent" if exec_res["level"] == "urgent" else "non-urgent"
        shared["triage_reasons"] = exec_res["reasons"]
        shared.setdefault("warnings", [])
        if self.disclaimer not in shared["warnings"]:
            shared["warnings"].append(self.disclaimer)
        shared.setdefault(
            "triage_note",
            "Triage: URGENT (" + ", ".join(exec_res["reasons"][:3]) + ")."
            if exec_res["reasons"] else "Triage: non-urgent."
        )
        return exec_res["level"]  # "urgent" | "ok"
