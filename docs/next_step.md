# Next Step — Repository Intelligence + Analysis Limits + Artifact UX

## Current phase

The project already has:
- FastAPI backend + dashboard UI
- Run/Reset flow
- `/api/state` polling
- orchestrator → agents → tools pipeline
- repo cloning into `workspace/repos/<repo_name>`
- artifact generation:
  - `report.md`
  - `code_summary.md`
  - `qa_findings.md`
  - `review.md`
  - `final_summary.md`

The next milestone is **not** adding more scaffolding.
The next milestone is making the analyzer smarter, safer, and easier to consume.

---

## Milestone goal

Teach the system to answer:

1. What is this project?
2. How does it likely run?
3. Where should I start reading?
4. Is the repo too large / noisy to analyze fully?
5. Where can I open the generated artifacts in the UI?

---

## Deliverables

By the end of this step, the system should:

- detect likely project type
- detect languages / frameworks / tools
- detect likely run/build/test hints
- produce a recommended reading order
- enforce safe indexing / summarization limits
- clearly report skipped files and truncation
- expose generated artifact file links in the UI
- include tests for the new logic

---

## Implementation plan

### Step 1 — Improve DeveloperAgent intelligence
**File:** `backend/agents/developer_agent.py`

Add / keep:
- ignored directories
- blocked extensions
- allowed text/source extensions
- max indexed files
- max selected files
- max file size for summarization

Add repo intelligence sections to `report.md`:
- Project overview
- How it likely runs
- Where to start reading
- Important files
- Entrypoint candidates
- Repository limits and indexing

Expected output examples:
- Project type: Python application
- Languages: Python, Markdown
- Frameworks / tools: Python project, Docker
- Likely run: `python main.py`
- Reading order:
  1. README.md
  2. requirements.txt
  3. main.py

---

### Step 2 — Keep tool layer safe
**File:** `backend/tools/tool_registry.py`

Ensure tools:
- ignore junk directories like:
  - `.git`
  - `node_modules`
  - `dist`
  - `build`
  - `.venv`
  - `venv`
  - `.idea`
  - `.vscode`
- raise `ToolError` for unreadable/non-UTF8 text files
- never escape `workspace/`

This is mostly done, but verify it is the final stable version.

---

### Step 3 — Upgrade QA findings
**File:** `backend/agents/qa_agent.py`

Add rule-based QA checks for:
- missing README
- missing test directory
- missing dependency manifest
- missing entrypoint
- missing Docker support
- TODO / FIXME / HACK counts
- suspiciously large files
- repo size risks

Expected `qa_findings.md` sections:
- Inventory summary
- Structure checks
- Deferred work markers
- Large files
- Risks
- Strengths

---

### Step 4 — Upgrade ReviewerAgent
**File:** `backend/agents/reviewer_agent.py`

Make reviewer validate:
- artifact presence
- artifact length
- target subdir consistency
- report coverage
- QA coverage
- code summary coverage

Expected `review.md` sections:
- Overall status
- Artifact presence
- Consistency checks
- Coverage checks
- Strengths
- Concerns
- Recommended next actions

---

### Step 5 — Improve DevOps artifact writing
**File:** `backend/agents/devops_agent.py`

Keep:
- `clone_repository`
- `write_artifacts`

Improve `write_artifacts` to also generate a better `final_summary.md` with:
- review status
- indexed file count
- selected file count
- project type
- languages
- frameworks/tools
- reading order
- entrypoints
- run hints
- QA highlights
- review highlights
- next actions

---

### Step 6 — Keep orchestrator aligned
**File:** `backend/core/orchestrator.py`

Make sure `_build_payload()` passes the correct artifacts:

For `build_qa_findings`:
- `workspace_files`
- `workspace_metadata`
- `selected_files`
- `report_md`

For `review_outputs`:
- `report_md`
- `code_summary_md`
- `qa_findings_md`
- `target_subdir`

For `write_artifacts`:
- `workspace_files`
- `selected_files`
- `report_md`
- `code_summary_md`
- `qa_findings_md`
- `review_md`
- `target_subdir`

No manager change needed right now.

---

### Step 7 — Add artifact links to UI
**Files:**
- `backend/api/routes.py`
- `frontend/templates/index.html`
- `frontend/static/app.js`
- optionally `frontend/static/styles.css`

Add a lightweight endpoint such as:
- `GET /api/artifacts`

Return available generated files from `workspace/`, for example:
- `report.md`
- `code_summary.md`
- `qa_findings.md`
- `review.md`
- `final_summary.md`
- `repo_inventory.json`
- `selected_files.json`

UI should show:
- clickable artifact list
- artifact section visible after run
- no redesign needed

Example display:
- report.md
- code_summary.md
- qa_findings.md
- review.md
- final_summary.md

Optional next step later:
- preview artifact content in a panel

---

### Step 8 — Add tests
**Files:**
- `tests/test_agents.py`
- `tests/test_orchestrator.py`
- maybe new:
  - `tests/test_repo_intelligence.py`
  - `tests/test_tool_registry.py`

Add tests for:
- ignored directories are skipped
- `.git` files never enter analysis
- binary/unreadable files are skipped safely
- repo intelligence detects common files
- reading order is generated
- run hints are generated
- large repo truncation is reported
- all artifacts use same target subdir
- final summary is created

---

## Suggested order of implementation

1. Finalize `developer_agent.py`
2. Finalize `qa_agent.py`
3. Finalize `reviewer_agent.py`
4. Finalize `devops_agent.py`
5. Finalize `orchestrator.py`
6. Add `/api/artifacts`
7. Update UI to show artifact links
8. Add tests

This order keeps the backend artifact pipeline stable before touching the frontend.

---

## Success checklist

A successful run should now produce:

- `workspace/report.md`
- `workspace/code_summary.md`
- `workspace/qa_findings.md`
- `workspace/review.md`
- `workspace/final_summary.md`
- `workspace/repo_inventory.json`
- `workspace/selected_files.json`

And these should all:
- reference the same `Target subdir`
- contain useful project identity info
- contain run/read guidance
- survive mixed repos without crashing

UI should:
- still support Run / Reset
- still use `/api/state` polling
- show artifact links after run

---

## What comes after this milestone

After Repository Intelligence + Analysis Limits + Artifact UX is stable, then the next milestone should be:

### Real autonomous code agents
Examples:
- propose changes
- edit files inside `workspace/`
- create patch suggestions
- write implementation plans
- later integrate an LLM

But do **not** do that before this repo-intelligence layer is stable.

---

## Important note for next chat

When opening the next chat, say:

> Read docs/PROJECT_CONTEXT.md and docs/AGENTS.md.  
> The current system already supports repo cloning and multi-agent analysis.  
> We are now implementing the “Repository Intelligence + Analysis Limits + Artifact UX” milestone from next_step.md.  
> Start with artifact links in the UI and backend `/api/artifacts` endpoint, then add tests.