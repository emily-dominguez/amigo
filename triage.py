from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import re

TEMP_F_REGEX = re.compile(r"(\d{2,3}(?:\.\d)?)\s*°?\s*f\b|\b(\d{2,3}(?:\.\d)?)\s*degrees?\s*f\b")


@dataclass
class TriageResult:
    label: str  # "emergency" | "clarify" | "mild"
    reasons: List[str]
    matched_phrases: List[str]

def _extract_max_temp_f(text: str) -> float | None:
    temps = []
    for m in TEMP_F_REGEX.finditer(text):
        val = m.group(1) or m.group(2)
        try:
            temps.append(float(val))
        except ValueError:
            continue
    return max(temps) if temps else None

def _normalize(text: str) -> str:
    text = text.lower().strip()
    # normalize apostrophes
    text = text.replace("’", "'")
    return text


def _match_any(text: str, phrases: List[str]) -> List[str]:
    hits = []
    for p in phrases:
        if p in text:
            hits.append(p)
    return hits


# -------------------------
# 1) CLEAR EMERGENCY PHRASES
# -------------------------
FEVER_DANGER_PHRASES = [
    "confused",
    "can't stay awake",
    "cannot stay awake",
    "unresponsive",
    "stiff neck",
    "rash that's spreading",
    "rash that is spreading",
    "shaking uncontrollably",
]

EMERGENCY_PHRASES = [
    # Consciousness / stroke-like
    "passed out", "fainted", "lost consciousness", "blacked out",
    "can't wake", "hard to wake", "unresponsive",
    "can't talk", "slurred speech", "face drooping", "one side of face drooping",
    "sudden weakness", "can't move my arm", "can't move my leg", "one side feels numb",
    "totally confused", "don't know where i am", "acting really strange",

    # Breathing / airway
    "can't breathe", "cannot breathe", "barely breathing", "gasping", "struggling to breathe",
    "wheezing badly", "lips turning blue", "blue fingers",
    "throat is closing", "tongue swelling", "can't swallow", "cannot swallow",

    # Chest pain & circulation
    "crushing chest pain", "heavy weight on my chest",
    "chest pain going to my arm", "jaw pain", "chest pressure",
    "sudden chest pain with shortness of breath",
    "heart racing really fast and i feel like i'll pass out",
    "chest tightness and sweating", "chest tightness and nausea",

    # Severe pain / trauma
    "worst pain of my life", "10 out of 10 pain",
    "thunderclap headache", "sudden, severe headache",
    "bone sticking out", "limb looks crooked", "obvious deformity",
    "hit my head and now vomiting", "head injury and can't stay awake",
    "serious burn", "large burn",

    # Bleeding / major injury
    "bleeding won't stop", "soaking through bandages",
    "coughing up blood", "vomiting blood", "blood in stool",
    "stab wound", "gunshot", "major car accident", "hit by car",
    "neck injury", "back injury and can't feel my legs",

    # Infection / sepsis-type
    "shaking uncontrollably with fever", "very high fever and confused",
    "fever and can't stay awake", "fever and stiff neck", "fever and rash",

    # Allergic reaction / anaphylaxis
    "allergic reaction and now can't breathe",
    "tongue swelling quickly", "lips swelling quickly", "face swelling quickly",
    "throat feels tight",

    # Pregnancy / pediatrics (optional signals)
    "pregnant and heavy bleeding", "pregnant and severe abdominal pain",
    "no fetal movement",
    "baby less than 3 months with fever", "newborn with fever",
    "baby not feeding and very sleepy", "baby breathing fast",

    # Mental health safety
    "i want to kill myself", "overdose", "took a bunch of pills",
    "cut myself badly", "hearing voices telling me to hurt myself",
    "might hurt someone",
]

# -------------------------------
# 2) AMBIGUOUS BUT CONCERNING TERMS
# -------------------------------
CONCERNING_PHRASES = [
    # Severity without detail
    "really bad pain", "terrible pain", "excruciating",
    "something is very wrong", "just not right", "can't get comfortable",
    "pain won't let me sleep",

    # Vague breathing/chest
    "short of breath", "hard to catch my breath",
    "chest feels tight", "pressure in my chest", "heavy chest",
    "winded easily", "out of breath walking",

    # Neuro-ish
    "dizzy", "lightheaded", "woozy", "off balance",
    "pins and needles", "tingling", "numb",
    "blurry vision", "double vision",

    # Infection/systemic
    "flu-like", "achy all over", "high fever", "fever for days",
    "fever won't break", "chills", "shivers", "sweats all night",
    "extreme fatigue", "so tired i can't get out of bed",

    # Heart language
    "heart is racing", "palpitations", "skipped beats",
    "chest discomfort", "weird feeling in chest",

    # GI/GU
    "can't keep anything down", "vomiting everything",
    "severe diarrhea", "black stool", "bright red blood",
    "haven't peed all day", "pee is very dark", "pain in side and fever",

    # Mental health (non-explicit)
    "can't go on", "don't want to live anymore",
    "thinking about hurting myself",
    "seeing things", "hearing voices",
]

# Small regexes for stronger emergency combos
EMERGENCY_REGEXES = [
    # chest pain + radiation
    (re.compile(r"chest (pain|pressure).*(arm|jaw)"), "chest pain/pressure with arm/jaw symptoms"),
    # shortness of breath + chest pain
    (re.compile(r"(shortness of breath|can't breathe|difficulty breathing).*(chest pain|pressure)"),
     "breathing trouble with chest pain/pressure"),
]


def triage_decision(user_message: str) -> TriageResult:
    text = _normalize(user_message)
    # Fever handling (clarify unless >=103F or danger signs)
    max_temp = _extract_max_temp_f(text)
    if max_temp is not None and max_temp >= 103.0:
        return TriageResult(
            label="emergency",
            reasons=["fever >= 103F"],
            matched_phrases=[f"{max_temp}F"],
        )

    if ("fever" in text or "high fever" in text) and any(p in text for p in FEVER_DANGER_PHRASES):
        return TriageResult(
            label="emergency",
            reasons=["fever with danger signs"],
            matched_phrases=["fever + danger sign"],
        )


    matched_emergency = _match_any(text, EMERGENCY_PHRASES)
    matched_concerning = _match_any(text, CONCERNING_PHRASES)

    reasons: List[str] = []
    matched_phrases: List[str] = []

    for phrase in matched_emergency:
        reasons.append("emergency phrase match")
        matched_phrases.append(phrase)

    for rx, label in EMERGENCY_REGEXES:
        if rx.search(text):
            reasons.append(label)
            matched_phrases.append(label)

    if reasons:
        return TriageResult(label="emergency", reasons=reasons, matched_phrases=matched_phrases)

    if matched_concerning:
        return TriageResult(
            label="clarify",
            reasons=["concerning phrase match"],
            matched_phrases=matched_concerning[:6],  # cap for readability
        )

    return TriageResult(label="mild", reasons=[], matched_phrases=[])
