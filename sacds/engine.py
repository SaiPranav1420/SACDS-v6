"""
SACDS v6 — Semantic Adaptive Content & Document Security
Core engine extracted from SACDS_v6_Final.ipynb
9-layer ABAC pipeline (L1–L9) | NIST SP 800-162
"""

import re
import math
import random
import sqlite3
import json
import datetime
import os
from collections import defaultdict, Counter

# ─── Global seed ──────────────────────────────────────────────────────────────
GLOBAL_SEED = 42
random.seed(GLOBAL_SEED)

# ─── 6-class sensitivity schema ───────────────────────────────────────────────
LABEL_NORMALISE = {"RESTRICTED": "CONFIDENTIAL"}

def normalise_label(label):
    return LABEL_NORMALISE.get(label, label)

SENSITIVITY_LEVELS = {
    "PUBLIC":       0,
    "CONFIDENTIAL": 2,
    "LEGAL":        2,
    "FINANCIAL":    3,
    "PII":          4,
    "TOP_SECRET":   5,
}

SENSITIVE_MAP = {
    "PERSON": "PII", "GPE": "PII", "LOC": "PII",
    "ORG": "CONFIDENTIAL", "MONEY": "FINANCIAL",
    "CARDINAL": "FINANCIAL", "PERCENT": "FINANCIAL",
    "DATE": "CONFIDENTIAL", "TIME": "CONFIDENTIAL",
    "PRODUCT": "CONFIDENTIAL", "LAW": "LEGAL",
    "NORP": "CONFIDENTIAL", "QUANTITY": "CONFIDENTIAL",
}

MINORITY_CLASSES = {"CONFIDENTIAL", "LEGAL", "FINANCIAL"}
IMBALANCE_MULT   = 5.0

DOC_CLASS_MULTIPLIER = {
    "public": 0.50, "internal": 0.75, "confidential": 1.00,
    "restricted": 1.20, "secret": 1.50,
}

ROLE_HIERARCHY = {
    "admin": 5, "manager": 4, "employee": 3, "auditor": 2, "intern": 1,
}

# ─── Expanded keyword lists ────────────────────────────────────────────────────
KEYWORD_BOOST = {
    "PII": [
        "ssn", "social security", "passport", "national id", "date of birth",
        "dob", "phone number", "email address", "bank account", "medical record",
        "patient", "biometric", "fingerprint", "facial recognition", "driver license",
        "personal identifier", "home address", "birth certificate", "salary",
    ],
    "FINANCIAL": [
        "revenue", "profit", "loss", "balance sheet", "cash flow", "ebitda",
        "quarterly earnings", "fiscal", "budget", "invoice", "payroll",
        "financial statement", "audit report", "tax return", "credit score",
        "trading", "investment portfolio", "asset", "liability",
    ],
    "LEGAL": [
        "attorney", "counsel", "litigation", "court order", "lawsuit",
        "settlement", "injunction", "subpoena", "nda", "non-disclosure",
        "intellectual property", "patent", "copyright", "trademark",
        "gdpr", "compliance", "regulatory", "statute", "clause",
    ],
    "TOP_SECRET": [
        "top secret", "classified", "eyes only", "compartmented",
        "special access program", "sap", "sci", "national security",
        "need to know", "codeword", "noforn",
    ],
    "CONFIDENTIAL": [
        "confidential", "proprietary", "internal use only", "not for distribution",
        "trade secret", "business strategy", "merger", "acquisition", "roadmap",
        "internal memo", "restricted distribution",
    ],
    "PUBLIC": [
        "press release", "public announcement", "news release", "open source",
        "published", "publicly available", "for immediate release",
    ],
}

# PII regex patterns
PII_PATTERNS = [
    (r'\b\d{3}-\d{2}-\d{4}\b',                  "PII"),   # SSN
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "PII"),  # email
    (r'\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b', "PII"),  # phone
    (r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',      "PII"),   # DOB
    (r'\b[A-Z][0-9]{8}\b',                        "PII"),   # passport-like
    (r'\$[\d,]+(?:\.\d{2})?',                     "FINANCIAL"),  # dollar amounts
    (r'\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|million|billion)\b', "FINANCIAL"),
]

PROTECTED_LBLS  = {"PII", "TOP_SECRET", "FINANCIAL"}
LOW_CLR_ROLES   = {"intern", "auditor"}

# ─── Default policies ──────────────────────────────────────────────────────────
DEFAULT_POLICIES = {
    "admin":    {"labels": ["PUBLIC","CONFIDENTIAL","LEGAL","FINANCIAL","PII","TOP_SECRET"], "clearance": 5},
    "manager":  {"labels": ["PUBLIC","CONFIDENTIAL","LEGAL","FINANCIAL"], "clearance": 4},
    "employee": {"labels": ["PUBLIC","CONFIDENTIAL"], "clearance": 3},
    "auditor":  {"labels": ["PUBLIC","CONFIDENTIAL","FINANCIAL"], "clearance": 2},
    "intern":   {"labels": ["PUBLIC"], "clearance": 1},
}

# ─── User personas ──────────────────────────────────────────────────────────────
USER_PERSONAS = {
    "alice_admin":    {"user_id": "alice_admin",    "name": "Alice Admin",    "role": "admin"},
    "bob_manager":    {"user_id": "bob_manager",    "name": "Bob Manager",    "role": "manager"},
    "carol_employee": {"user_id": "carol_employee", "name": "Carol Employee", "role": "employee"},
    "dave_auditor":   {"user_id": "dave_auditor",   "name": "Dave Auditor",   "role": "auditor"},
    "eve_intern":     {"user_id": "eve_intern",     "name": "Eve Intern",     "role": "intern"},
}

ABSTRACT_TEMPLATES = {
    "PII":        "an individual's personal information",
    "FINANCIAL":  "financial data",
    "LEGAL":      "legal content",
    "TOP_SECRET": "[CLASSIFIED]",
    "CONFIDENTIAL": "confidential information",
}

# ─── L1: Identity Layer ────────────────────────────────────────────────────────
def get_user_profile(user_id: str) -> dict:
    profile = USER_PERSONAS.get(user_id)
    if not profile:
        raise ValueError(f"Unknown user_id: {user_id}")
    role = profile["role"]
    clearance = DEFAULT_POLICIES.get(role, {}).get("clearance", 0)
    return {**profile, "clearance": clearance}

def get_all_users():
    return [
        {**p, "clearance": DEFAULT_POLICIES[p["role"]]["clearance"]}
        for p in USER_PERSONAS.values()
    ]

# ─── L2: Semantic Sensitivity Scorer ──────────────────────────────────────────
_NLP = None
_NLP_MODE = None

def _get_nlp():
    global _NLP, _NLP_MODE
    if _NLP is None and _NLP_MODE is None:
        try:
            import spacy
            for model in ["en_core_web_trf", "en_core_web_lg", "en_core_web_sm"]:
                try:
                    _NLP = spacy.load(model)
                    _NLP_MODE = model
                    return _NLP, _NLP_MODE
                except Exception:
                    continue
        except Exception:
            pass
        _NLP_MODE = "keyword-only"
    return _NLP, _NLP_MODE


def _keyword_score(text: str) -> tuple[str, float, list]:
    """Keyword + regex based sensitivity scoring."""
    tl = text.lower()
    scores = defaultdict(float)

    # Regex PII/FINANCIAL patterns
    for pattern, label in PII_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            scores[label] += len(matches) * 1.5

    # Keyword matching
    for label, keywords in KEYWORD_BOOST.items():
        for kw in keywords:
            if kw.lower() in tl:
                scores[label] += 1.0

    if not scores:
        return "PUBLIC", 0.0, []

    top_label = max(scores, key=scores.get)
    confidence = min(scores[top_label] / 5.0, 1.0)
    found_kws = [kw for label, kws in KEYWORD_BOOST.items()
                 for kw in kws if kw.lower() in tl]
    return top_label, confidence, found_kws[:5]


def _ner_score(text: str, nlp) -> tuple[str, float, list]:
    """spaCy NER-based sensitivity scoring."""
    doc = nlp(text)
    ent_labels = [SENSITIVE_MAP.get(ent.label_, None) for ent in doc.ents]
    ent_labels = [l for l in ent_labels if l]
    if not ent_labels:
        return "PUBLIC", 0.0, []
    counts = Counter(ent_labels)
    top_label = max(counts, key=counts.get)
    confidence = min(counts[top_label] / 3.0, 1.0)
    entities = [{"text": ent.text, "label": ent.label_,
                 "sensitivity": SENSITIVE_MAP.get(ent.label_, "PUBLIC")}
                for ent in doc.ents]
    return top_label, confidence, entities


def tag_section(section: dict, doc_class: str = "internal", nlp_mode: str = "hybrid") -> dict:
    """Tag a text section with sensitivity label and score."""
    text = section.get("text", "")
    if not text.strip():
        return {**section, "top_label": "PUBLIC", "sensitivity_score": 0,
                "ml_confidence": 0.0, "entities": [], "nlp_mode": "keyword-only",
                "keywords_found": []}

    nlp, mode = _get_nlp()
    kw_label, kw_conf, kw_found = _keyword_score(text)

    entities = []
    if nlp and nlp_mode in ("ner", "hybrid"):
        ner_label, ner_conf, entities = _ner_score(text, nlp)
        # Ensemble: keyword + NER (weighted average)
        kw_score  = SENSITIVITY_LEVELS.get(kw_label, 0) * kw_conf  * 0.45
        ner_score = SENSITIVITY_LEVELS.get(ner_label, 0) * ner_conf * 0.55
        combined_score = kw_score + ner_score
        # Pick the higher label
        top_label = kw_label if SENSITIVITY_LEVELS.get(kw_label, 0) >= SENSITIVITY_LEVELS.get(ner_label, 0) else ner_label
        confidence = max(kw_conf, ner_conf)
        used_mode  = mode
    else:
        top_label  = kw_label
        confidence = kw_conf
        used_mode  = "keyword-only"

    doc_mult  = DOC_CLASS_MULTIPLIER.get(doc_class, 1.0)
    base_sens = SENSITIVITY_LEVELS.get(top_label, 0)
    adj_score = min(5, round(base_sens * doc_mult))

    return {
        **section,
        "top_label":       normalise_label(top_label),
        "sensitivity_score": adj_score,
        "ml_confidence":   round(confidence, 3),
        "entities":        entities,
        "nlp_mode":        used_mode,
        "keywords_found":  kw_found,
        "doc_class":       doc_class,
    }


# ─── L3: Policy context ────────────────────────────────────────────────────────
POLICY_RESTRICT_KW = ["classified", "confidential", "restricted", "sensitive", "prohibited"]
POLICY_PERMIT_KW   = ["public", "approved", "open", "permitted", "authorized"]

def extract_policy_signal(text: str, role: str, sensitivity_label: str) -> dict:
    tl = text.lower()
    permit_score  = sum(1 for kw in POLICY_PERMIT_KW  if kw in tl)
    restrict_score = sum(1 for kw in POLICY_RESTRICT_KW if kw in tl)
    sens = SENSITIVITY_LEVELS.get(sensitivity_label, 0)
    if sens >= 4:
        restrict_score += 2
    if restrict_score > permit_score:
        return {"signal": "RESTRICT", "confidence": round(restrict_score / (restrict_score + permit_score + 1), 3)}
    elif permit_score > restrict_score:
        return {"signal": "PERMIT",   "confidence": round(permit_score  / (restrict_score + permit_score + 1), 3)}
    return {"signal": "NEUTRAL", "confidence": 0.0}


# ─── L4: AB-SAC Decision Engine ───────────────────────────────────────────────
def decide(user_profile: dict, section: dict, policy_signal: str = "NEUTRAL") -> tuple[str, str, int]:
    """Return (decision, reason, clearance_gap)."""
    role      = user_profile.get("role", "intern")
    clearance = DEFAULT_POLICIES.get(role, {}).get("clearance", 0)
    sec_score = section.get("sensitivity_score", 0)
    top_label = section.get("top_label", "PUBLIC")
    ml_conf   = section.get("ml_confidence", 0.0)
    gap       = clearance - sec_score

    if sec_score == 0 or top_label == "PUBLIC":
        return "SHOW", "Public content — unrestricted", gap

    effective_gap = gap
    if policy_signal == "RESTRICT" and gap == -1:
        effective_gap = -2
    elif policy_signal == "PERMIT" and gap == -1:
        effective_gap = 0

    if ml_conf >= 0.80 and top_label in PROTECTED_LBLS and role in LOW_CLR_ROLES:
        effective_gap = min(effective_gap, -2)

    if effective_gap >= 0:
        return "SHOW",   f"Gap +{gap}: [{role}] cleared for [{top_label}]", gap
    elif effective_gap == -1:
        if ml_conf >= 0.70 and top_label in PROTECTED_LBLS:
            return "REDACT", f"Gap -1 + high ML conf ({ml_conf:.2f}): REDACT [{top_label}]", gap
        return "MASK",   f"Gap -1: partial masking for [{top_label}]", gap
    else:
        return "REDACT", f"Gap {gap}: [{role}] lacks clearance for [{top_label}]", gap


# ─── L5: Entity-Level Sanitizer ───────────────────────────────────────────────
def sanitize_section(section: dict, user_clearance: int, policy_signal: str = "NEUTRAL") -> dict:
    text      = section.get("text", "")
    entities  = section.get("entities", [])
    sanitized = text

    for ent in entities:
        sensitivity = ent.get("sensitivity", "PUBLIC")
        score = SENSITIVITY_LEVELS.get(sensitivity, 0)
        if score >= 4 and user_clearance < 3:
            replacement = f"[{sensitivity}_REDACTED]"
        elif score >= 2 and user_clearance < 4:
            replacement = ABSTRACT_TEMPLATES.get(sensitivity, "some content")
        else:
            replacement = ent.get("text", "")
        if replacement != ent.get("text", ""):
            sanitized = sanitized.replace(ent.get("text", ""), replacement, 1)

    # Also redact regex-matched PII
    if user_clearance < 3:
        for pattern, label in PII_PATTERNS[:3]:  # SSN, email, phone
            sanitized = re.sub(pattern, f"[{label}_REDACTED]", sanitized)

    return {**section, "sanitized_text": sanitized, "original_text": text}


# ─── Main pipeline: analyze document ──────────────────────────────────────────
def split_into_sections(text: str) -> list[dict]:
    """Split text into sections by paragraphs / double newlines."""
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    return [{"section_id": i, "text": p} for i, p in enumerate(paragraphs)]


def analyze_document(text: str, user_id: str, doc_class: str = "internal",
                     nlp_mode: str = "hybrid") -> dict:
    """
    Full 9-layer SACDS pipeline.
    Returns structured analysis with per-section decisions.
    """
    # L1: Identity
    user_profile = get_user_profile(user_id)
    role         = user_profile["role"]
    clearance    = user_profile["clearance"]

    # Split text into sections
    sections_raw = split_into_sections(text)

    results = []
    for sec in sections_raw:
        # L2: Semantic scoring
        tagged = tag_section(sec, doc_class, nlp_mode)

        # L3: Policy signal
        policy_ctx = extract_policy_signal(sec["text"], role, tagged["top_label"])

        # L4: Decision
        decision, reason, gap = decide(user_profile, tagged, policy_ctx["signal"])

        # L5: Sanitization
        if decision == "MASK":
            sanitized = sanitize_section(tagged, clearance, policy_ctx["signal"])
            display_text = sanitized["sanitized_text"]
        elif decision == "REDACT":
            display_text = f"[SECTION REDACTED — {tagged['top_label']} content requires clearance level {tagged['sensitivity_score']}]"
        else:
            display_text = sec["text"]

        results.append({
            "section_id":       sec["section_id"],
            "original_text":    sec["text"],
            "display_text":     display_text,
            "decision":         decision,
            "reason":           reason,
            "top_label":        tagged["top_label"],
            "sensitivity_score": tagged["sensitivity_score"],
            "ml_confidence":    tagged["ml_confidence"],
            "clearance_gap":    gap,
            "policy_signal":    policy_ctx["signal"],
            "nlp_mode":         tagged["nlp_mode"],
            "keywords_found":   tagged.get("keywords_found", []),
            "entities":         [
                {"text": e["text"], "label": e.get("label",""), "sensitivity": e.get("sensitivity","PUBLIC")}
                for e in tagged.get("entities", [])
            ],
        })

    # Summary stats
    decision_counts = Counter(r["decision"] for r in results)
    label_counts    = Counter(r["top_label"] for r in results)

    return {
        "user":          user_profile,
        "doc_class":     doc_class,
        "nlp_mode":      nlp_mode,
        "sections":      results,
        "summary": {
            "total_sections":  len(results),
            "show":    decision_counts.get("SHOW",   0),
            "mask":    decision_counts.get("MASK",   0),
            "redact":  decision_counts.get("REDACT", 0),
            "labels":  dict(label_counts),
        },
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }


def get_policies() -> dict:
    return DEFAULT_POLICIES


def get_sensitivity_levels() -> dict:
    return SENSITIVITY_LEVELS
