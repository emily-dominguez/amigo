# agent.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

from openai import OpenAI

from triage import triage_decision, TriageResult
from prompt import SYSTEM_PROMPT

client = OpenAI()

@dataclass
class AgentResult:
    role: str
    content: str
    meta: Dict[str, str]

# Fields we want the model to collect (in order)
FIELDS = [
    "GENDER",
    "MED_HISTORY",
    "MEDICATIONS",
    "ALLERGIES",
    "CHIEF_COMPLAINT",
    "TIMELINE",       # must use exact wording
    "LOCATION",
    "SEVERITY",
    "BETTER_WORSE",
    "ASSOCIATED",
    "REDFLAGS",       # must be exactly 3 fixed questions
    "CONCERNS",       # must be exact wording
]

def build_emergency_response(triage: TriageResult) -> str:
    return (
        "Based on what you've told me, your symptoms may be serious.\n\n"
        "Here's what I recommend: please seek emergency care immediately or call 911.\n\n"
        "This is beyond what I can safely assess remotely. "
        "I can provide guidance, but I cannot replace an in-person examination.\n\n"
        "If this isn't improving in 1–2 days after getting urgent care, please contact your doctor or return to care. "
        "How does this sound to you?"
    )

def build_clarify_response() -> str:
    # Clarify path stays deterministic (safe)
    return (
        "I understand.\n\n"
        "To make sure this is safe to assess, I need to ask a few important questions.\n\n"
        "When did this first start, and has it been getting better, worse, or staying the same?\n\n"
        "1. Are you having chest pain right now?\n"
        "2. Are you having trouble breathing while resting or speaking in full sentences?\n"
        "3. Have you fainted, passed out, or felt like you might pass out?\n\n"
        "What concerns you most about this?"
    )

def context_summary(patient_context: Dict[str, str]) -> str:
    # Keep compact; do not include huge text
    keys = ["age", "age_group", "guardian_confirmed", "GENDER", "MED_HISTORY", "MEDICATIONS", "ALLERGIES",
            "CHIEF_COMPLAINT", "TIMELINE", "LOCATION", "SEVERITY", "BETTER_WORSE", "ASSOCIATED", "REDFLAGS", "CONCERNS"]
    parts = []
    for k in keys:
        v = patient_context.get(k)
        if v:
            parts.append(f"{k}={v}")
    return " | ".join(parts)

def next_field(patient_context: Dict[str, str]) -> str:
    for f in FIELDS:
        if not patient_context.get(f):
            return f
    return "DONE"

def record_answer(patient_context: Dict[str, str], answer: str) -> None:
    """
    Store the user's message as the answer to the last asked field.
    We track last_asked in patient_context.
    """
    last = patient_context.get("last_asked")
    if last and last in FIELDS and not patient_context.get(last):
        patient_context[last] = answer.strip()

def call_model(history: List[Dict[str, str]], patient_context: Dict[str, str], next_f: str) -> str:
    summary = context_summary(patient_context)
    ready = (next_f == "DONE")

    system_msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"PATIENT_CONTEXT: {summary}"},
        {"role": "system", "content": f"NEXT_FIELD: {next_f}"},
        {"role": "system", "content": f"READY_FOR_RECOMMENDATIONS: {str(ready).lower()}"},
    ]

    msgs = system_msgs + history

    resp = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=msgs,
        temperature=0.3,
    )
    return resp.choices[0].message.content

def agent_reply(history: List[Dict[str, str]], user_message: str, patient_context: Dict[str, str]) -> AgentResult:
    triage_text = user_message  
    triage = triage_decision(triage_text)
    
    if triage.label == "emergency":
        return AgentResult(
            role="assistant", 
            content=build_emergency_response(triage),
            meta={"mode": "emergency", "matched": triage.matched_phrases}
        )
    
    if triage.label == "clarify":
        return AgentResult(
            role="assistant",
            content=build_clarify_response(),
            meta={"mode": "clarify", "matched": triage.matched_phrases}
        )

    # Mild or non-emergency path: use conversational model with strong system instructions
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"TRIAGE_LEVEL: {triage.label}"},
    ] + history

    resp = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=messages,
        temperature=0.3
    )
    
    return AgentResult(
        role="assistant", 
        content=resp.choices[0].message.content,
        meta={"mode": "conversational", "triage": triage.label}
    )
