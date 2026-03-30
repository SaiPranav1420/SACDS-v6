# AGENTS.md — SACDS v6 Project Rules
> This file is the authoritative agent constitution for SACDS v6.
> It is auto-loaded by Antigravity, Claude Code, and Cursor at the start of every session.
> Do NOT remove or rename this file.

---

## 1. Project Overview

**SACDS v6** (Semantic Adaptive Content & Document Security) is a research-grade document
access-control system submitted to an IEEE conference. It enforces **section-level visibility**
of sensitive documents based on user role, NLP-derived sensitivity scores, and reinforcement
learning–adapted policies.

It implements the **NIST SP 800-162 ABAC framework** and extends the baseline paper:
> Karimi, L., Abdelhakim, M., & Joshi, J.B.D. (2021). arXiv:2105.08587

---

## 2. Tech Stack

| Layer    | Technology                                                     |
|----------|----------------------------------------------------------------|
| Backend  | Python 3.10+, Flask 3.x                                        |
| NLP      | spaCy (`en_core_web_sm/lg/trf`), scikit-learn TF-IDF + LR     |
| Embeddings | `sentence-transformers` / `all-MiniLM-L6-v2` (optional)     |
| Storage  | SQLite (via `sqlite3` stdlib)                                  |
| RL Agent | Custom Double-DQN with Prioritized Experience Replay (pure Python) |
| Frontend | Vanilla HTML/CSS/JS (single-file, no build step)               |
| Notebook | Jupyter (`SACDS_v6_Final.ipynb`) — full research pipeline      |

---

## 3. Repository Structure

```
sacds-v6/
├── AGENTS.md                  ← THIS FILE — agent rules, read every session
├── GEMINI.md                  ← Antigravity-specific overrides
├── MASTER_PROMPT.md           ← Task prompt for Antigravity Agent Manager
├── app.py                     ← Flask REST API entry point
├── sacds/
│   ├── __init__.py
│   └── engine.py              ← Core 9-layer SACDS pipeline
├── templates/
│   └── index.html             ← Single-file web frontend
├── SACDS_v6_Final.ipynb       ← Original research notebook (source of truth)
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 4. Core Architecture — 9-Layer ABAC Pipeline

Always preserve this layer order. Never collapse or reorder layers.

| Layer | Name                        | File               | Key Function                              |
|-------|-----------------------------|--------------------|-------------------------------------------|
| L1    | Identity Layer              | `engine.py`        | User auth + role resolution               |
| L2    | Semantic Sensitivity Scorer | `engine.py`        | NLP labeling (6-class)                    |
| L3    | Policy Context Retrieval    | `engine.py`        | NIST policy signal extraction             |
| L4    | AB-SAC Decision Engine      | `engine.py`        | SHOW / MASK / REDACT per section          |
| L5    | Entity-Level Sanitizer      | `engine.py`        | Named entity & PII regex masking          |
| L6    | Audit Logger                | `engine.py`        | SQLite trail with composite scores        |
| L7    | RL Policy Optimizer         | (notebook only)    | Double-DQN with PER buffer                |
| L8    | Policy Conflict Detector    | (notebook only)    | Drift + escalation blocking               |
| L9    | Research Metrics            | (notebook only)    | F1 / AUC-ROC / leakage rate               |

---

## 5. Sensitivity Label Schema (6-class — v6)

`RESTRICTED` was merged into `CONFIDENTIAL` in v6 to reduce label confusion and improve Macro-F1.
Never re-introduce `RESTRICTED` as a standalone label.

```python
SENSITIVITY_LEVELS = {
    "PUBLIC":       0,
    "CONFIDENTIAL": 2,   # Absorbs legacy RESTRICTED
    "LEGAL":        2,
    "FINANCIAL":    3,
    "PII":          4,
    "TOP_SECRET":   5,
}
```

---

## 6. Role Clearance Matrix

```
admin    → clearance 5  (all labels)
manager  → clearance 4  (up to FINANCIAL)
employee → clearance 3  (PUBLIC + CONFIDENTIAL)
auditor  → clearance 2  (PUBLIC + CONFIDENTIAL + FINANCIAL)
intern   → clearance 1  (PUBLIC only)
```

---

## 7. Decision Logic — L4 Rules (Critical — Do Not Change)

```
gap = user_clearance - section_sensitivity_score

gap >= 0          → SHOW
gap == -1         → MASK  (unless ML confidence >= 0.70 + protected label → REDACT)
gap <= -2         → REDACT
policy "RESTRICT" + gap == -1 → effective_gap = -2 (REDACT)
policy "PERMIT"   + gap == -1 → effective_gap =  0 (SHOW)
ML conf >= 0.80 + protected_label + low_clearance_role → force REDACT
```

`PROTECTED_LBLS = {"PII", "TOP_SECRET", "FINANCIAL"}`
`LOW_CLR_ROLES = {"intern", "auditor"}`

---

## 8. REST API Contract

**Base URL:** `http://localhost:5000`

| Method | Route                 | Description                        |
|--------|-----------------------|------------------------------------|
| GET    | `/`                   | Web frontend (index.html)          |
| GET    | `/api/users`          | List all user personas             |
| GET    | `/api/policies`       | Role → clearance + label mapping   |
| GET    | `/api/sensitivity-levels` | Sensitivity label → integer    |
| GET    | `/api/sample-texts`   | 3 sample documents for testing     |
| POST   | `/api/analyze`        | Full pipeline analysis             |

**POST `/api/analyze` body:**
```json
{
  "text":      "<document text>",
  "user_id":   "carol_employee",
  "doc_class": "internal",
  "nlp_mode":  "hybrid"
}
```

Valid `user_id` values: `alice_admin`, `bob_manager`, `carol_employee`, `dave_auditor`, `eve_intern`
Valid `doc_class` values: `public`, `internal`, `confidential`, `restricted`, `secret`
Valid `nlp_mode` values: `hybrid`, `keyword_only`, `ner`

---

## 9. Coding Standards

### Python
- Python 3.10+ syntax only (use `match`, `|` union types, `X | None` annotations)
- Type hints on all public functions
- Docstrings on all module-level functions
- No third-party libraries beyond `requirements.txt` — keep the install surface minimal
- DB path constant: `DB_PATH = "sacds_v4.db"` — do not rename (keeps backward compat with notebook)
- Global seed: `GLOBAL_SEED = 42` — all random calls must use this seed

### Flask
- All routes return `jsonify(...)` — no raw `dict`
- Error responses: `jsonify({"error": "..."})` with appropriate HTTP status code
- Never use `app.run(debug=True)` in production — the `if __name__ == "__main__":` guard is correct

### HTML/CSS/JS Frontend
- Single-file architecture — all CSS and JS inline in `templates/index.html`
- No build tools, no npm, no bundler
- CSS variables in `:root` for all colors/fonts — never hardcode hex in component styles
- The classified terminal aesthetic (dark bg, teal accent, monospace) must be preserved
- All API calls use `fetch()` — no jQuery, no axios

---

## 10. Testing Protocol

Before marking any task complete, the agent MUST verify:

1. **Engine smoke test:**
   ```bash
   python3 -c "
   from sacds.engine import analyze_document
   r = analyze_document('SSN: 123-45-6789 revenue \$1M', 'eve_intern', 'confidential', 'hybrid')
   assert r['summary']['redact'] > 0, 'PII/FINANCIAL should be REDACT for intern'
   print('✅ Engine smoke test passed')
   "
   ```

2. **Role differentiation test:**
   ```bash
   python3 -c "
   from sacds.engine import analyze_document
   text = 'SSN: 123-45-6789\nPublic announcement for all.'
   intern = analyze_document(text, 'eve_intern', 'confidential', 'hybrid')
   admin  = analyze_document(text, 'alice_admin', 'confidential', 'hybrid')
   assert admin['summary']['show'] >= intern['summary']['show'], 'Admin should see >= intern'
   print('✅ Role differentiation test passed')
   "
   ```

3. **Flask startup test:**
   ```bash
   python3 -c "from app import app; print('✅ Flask app imports cleanly')"
   ```

---

## 11. What Agents MUST NOT Do

- ❌ Do NOT rename `SENSITIVITY_LEVELS`, `DEFAULT_POLICIES`, `USER_PERSONAS`, or `GLOBAL_SEED`
- ❌ Do NOT re-introduce `RESTRICTED` as a standalone sensitivity label
- ❌ Do NOT add build steps, package.json, webpack, or any frontend bundler
- ❌ Do NOT add external Python dependencies not in `requirements.txt` without updating it
- ❌ Do NOT modify the 9-layer pipeline order in `engine.py`
- ❌ Do NOT remove the `if __name__ == "__main__":` guard in `app.py`
- ❌ Do NOT delete `SACDS_v6_Final.ipynb` — it is the research source of truth
- ❌ Do NOT change the `DB_PATH = "sacds_v4.db"` constant

---

## 12. Key Architectural Decisions (Rationale)

| Decision | Why |
|----------|-----|
| SQLite over PostgreSQL | Zero-config for research/demo; swap is one import |
| Vanilla JS frontend | No build step = zero friction for IEEE reviewers to run |
| `RESTRICTED` merged into `CONFIDENTIAL` | Reduces the hardest confusion pair; +3–5% Macro-F1 |
| Keyword + NER ensemble | Keyword catches regex patterns NER misses; NER catches entities keywords miss |
| Gap-only MASK at -1 | Partial disclosure at boundary is better than binary block |
| GLOBAL_SEED = 42 | All results must be reproducible for paper replication |
