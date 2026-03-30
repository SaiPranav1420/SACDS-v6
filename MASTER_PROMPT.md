# MASTER PROMPT — SACDS v6
## Paste this into Antigravity Agent Manager → Planning Mode

---

```
You are taking over development of SACDS v6 (Semantic Adaptive Content & Document Security),
a research-grade document security system built for an IEEE conference submission.

Start by reading @/AGENTS.md in full — it is the authoritative project constitution and
contains the architecture, coding standards, decision logic rules, and test protocol.
Then read @/GEMINI.md for Antigravity-specific behavior overrides.

--- PROJECT SUMMARY ---

SACDS v6 enforces section-level access control on sensitive documents using:
  - A 9-layer ABAC pipeline (L1 Identity → L9 Research Metrics)
  - NLP sensitivity scoring (spaCy NER + TF-IDF keyword ensemble)
  - A 6-class label schema: PUBLIC, CONFIDENTIAL, LEGAL, FINANCIAL, PII, TOP_SECRET
  - Role-based clearance (admin=5, manager=4, employee=3, auditor=2, intern=1)
  - SHOW / MASK / REDACT decisions per document section
  - A Flask REST API (app.py) + single-file web frontend (templates/index.html)

--- CURRENT STATE ---

The project is fully implemented and running. All files are in this workspace:
  - sacds/engine.py         → core pipeline (L1–L6 + sanitization)
  - app.py                  → Flask REST API with 5 endpoints
  - templates/index.html    → classified-terminal-aesthetic web UI
  - SACDS_v6_Final.ipynb    → original research notebook (source of truth for L7–L9)

--- FIRST TASK ---

Before doing anything else:
1. Read @/AGENTS.md
2. Read @/GEMINI.md
3. Run the three smoke tests in AGENTS.md §10 and report results
4. Start the Flask server with `python app.py` and open http://localhost:5000 in the browser
5. Confirm the UI loads, select "Eve Intern", load the "Mixed Sensitivity Report" sample,
   run analysis, and verify PII/FINANCIAL sections are REDACT for the intern role
6. Report: "SACDS v6 is healthy" or list any failures found

Once the health check passes, await further instructions.

--- CONSTRAINTS (non-negotiable) ---
  - Never change SENSITIVITY_LEVELS, DEFAULT_POLICIES, or GLOBAL_SEED values
  - Never re-introduce RESTRICTED as a standalone label
  - Never add frontend build tools (no npm, no webpack)
  - Always run tests from AGENTS.md §10 before marking any task complete
  - L4 decide() function changes require explicit human review
```

---

## How to Use This Prompt

1. Open **Antigravity** and open the `sacds-v6/` folder as your workspace
2. Switch to **Planning mode** (not Fast)
3. Select **Gemini 3 Pro** (High) for the initial setup
4. Paste the prompt block above into the Agent Manager chat
5. The agent will read `AGENTS.md` + `GEMINI.md`, run the health check, and confirm readiness
6. After confirmation, give follow-up tasks in natural language

## Example Follow-Up Prompts

After the health check passes, you can ask things like:

**Add a feature:**
```
Add a /api/batch-analyze endpoint that accepts an array of documents
and returns analysis results for all of them in parallel.
Follow the API contract in AGENTS.md §8 and run the smoke tests after.
```

**Improve the NLP:**
```
The keyword scorer in tag_section() misses plural forms of keywords.
Add simple stemming (strip trailing 's') before matching.
Run smoke tests after.
```

**Extend the frontend:**
```
Add a "comparison mode" to the frontend that lets the user run the same
document through two different user roles side-by-side and see where
the decisions differ. Keep the same classified terminal aesthetic.
```

**Run the full notebook pipeline:**
```
Open the SACDS_v6_Final.ipynb notebook, run all cells in order,
and report the final evaluation metrics (Precision, Recall, F1, AUC-ROC).
```

**Deploy preparation:**
```
Prepare the project for deployment on Google Cloud Run.
Add a Dockerfile and a .env.example file.
Do not change any existing code — add only the deployment config.
```

---

## Notes on Antigravity-Specific Behavior

- **Use `@filename` syntax** to include specific files as context, e.g. `@/sacds/engine.py`
- **Planning mode** is required — SACDS has cross-layer dependencies Fast mode will break
- **Pro (High)** model for complex changes to `engine.py`; Pro (Low) for frontend tweaks
- **Browser sub-agent** can validate the UI at `http://localhost:5000` after frontend changes
- The `/run-tests` workflow (defined in `GEMINI.md`) triggers the 3 smoke tests on demand
- The `/start-server` workflow starts Flask if it isn't running
