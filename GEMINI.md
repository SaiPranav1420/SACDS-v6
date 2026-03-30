# GEMINI.md — Antigravity-Specific Overrides
> Antigravity reads this file with higher precedence than AGENTS.md.
> Use this for Antigravity-specific behavior. Shared rules live in AGENTS.md.

---

## Agent Mode

Always use **Planning mode** (not Fast mode) for this project.
The pipeline has 9 interdependent layers — Fast mode will miss cross-layer constraints.

## Task Planning Requirements

Before writing any code, produce an **Implementation Plan artifact** that includes:
1. Which layer(s) of the ABAC pipeline are affected
2. Whether the change alters any decision logic in L4 (if so, flag for explicit review)
3. List of files to be modified
4. The 3 smoke tests from `AGENTS.md §10` that will be run after

## Agent Parallelism Rules

You may spawn parallel agents, but enforce these boundaries:
- **Agent A** — backend/engine work (`sacds/engine.py`, `app.py`)
- **Agent B** — frontend work (`templates/index.html`)
- **Never** let both agents touch `sacds/engine.py` simultaneously — it is the shared state

## Review Triggers

Always pause and request human review before:
- Any change to L4 decision logic (the `decide()` function)
- Any change to `SENSITIVITY_LEVELS` or `DEFAULT_POLICIES`
- Adding a new Python dependency to `requirements.txt`
- Any destructive file operation

## Workflow: `/run-tests`

Run all three smoke tests from `AGENTS.md §10` and report pass/fail.

## Workflow: `/start-server`

```bash
cd <workspace_root>
pip install -r requirements.txt --break-system-packages
python -m spacy download en_core_web_sm
python app.py
```

## Workflow: `/git-status`

Show uncommitted changes and suggest a conventional commit message.
Format: `<type>(<scope>): <description>` — e.g. `feat(engine): add composite sensitivity scoring`

## Browser Validation

After any frontend change, open `http://localhost:5000` in the Antigravity browser and:
1. Select user "Eve Intern"
2. Load the "Mixed Sensitivity Report" sample
3. Run analysis
4. Verify that PII and FINANCIAL sections show REDACT (not SHOW) for intern clearance

## Security Note

This project handles simulated sensitive data labels.
Do NOT connect any MCP server that has write access to external storage while working on this project.
