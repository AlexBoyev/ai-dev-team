Live view of agents, tasks, and run logs.

Run
Reset
Agents
Idle
manager
Manager
idle
Current task: —
Last action: —
dev_1
Developer
idle
Current task: —
Last action: Scan complete
qa_1
Tester
idle
Current task: —
Last action: Insights complete
devops
DevOps
idle
Current task: —
Last action: Report written
reviewer
Reviewer
idle
Current task: —
Last action: —
Task Status
auto updates
Tasks
queue + results
ID	Title	Status	Assigned	Result
09dedc07	Analyze workspace for TODO/FIXME + suspicious strings + large files	completed	qa_1	todo_hits=0, suspicious_hits=0
0aa2c589	Scan workspace directory	completed	dev_1	files=1, dirs=2, py=0
d600cd2c	Write scan report to workspace/reports/latest_report.md	completed	devops	Wrote workspace/reports/latest_report.md
Live Logs
last 250 lines
# Next Step Plan — Tool Layer + Real Agents (no LLM yet)

You currently have:
- FastAPI dashboard + `/api/run`, `/api/reset`, `/api/state`
- Persistence (`data/state.json`, `data/logs.jsonl`, `data/runs/*.json`)
- Orchestrator (`backend/core/orchestrator.py`) that runs a real pipeline:
  1) scan workspace
  2) write `workspace/reports/latest_report.md`
  3) analyze TODO/FIXME + suspicious strings + largest files and append to report

The next milestone is to stop “orchestrator calling services directly” and move to:
**orchestrator → agent → tool → workspace**.

This makes the system ready for Claude/LLM later.

---

## Goal of this step (tomorrow)

✅ Implement a **Tool Registry** and wrap existing capabilities as tools  
✅ Implement **Agent classes** that execute tasks using tools  
✅ Update orchestrator to run the same 3 tasks, but via agents/tools  
✅ Keep the UI unchanged (dashboard continues to show agents/tasks/logs)

No Claude API yet. No WebSockets yet. No Docker yet.

---

## Step 0 — Current structure baseline

You should have something like:
backend/
api/
routes.py
core/
memory.py
orchestrator.py
persistence.py
services/
scanner_service.py
insights_service.py
tools/
file_tools.py
frontend/
templates/index.html
static/styles.css
static/app.js
workspace/
reports/latest_report.md
data/
state.json
logs.jsonl
runs/

### 3.1 Create: `backend/agents/base_agent.py`

**Responsibilities:**
- Common agent shape: name, role
- `run_task(task: TaskState) -> str` (returns result string)
- Helper method for safe tool calls:
  - `call_tool(tool_name: str, **kwargs)`

The base agent should not know business logic; children implement it.

### 3.2 Create: `backend/agents/developer_agent.py`
Role: `Developer`

It should handle tasks:
- `"Scan workspace directory"`
  - call `run_tool("scan_workspace", root="workspace")`
  - return a short summary string like: `files=X, dirs=Y, py=Z`

### 3.3 Create: `backend/agents/devops_agent.py`
Role: `DevOps`

It should handle tasks:
- `"Write scan report to workspace/reports/latest_report.md"`
  - call `build_report_md` (using the scan result)
  - call `write_report(path="workspace/reports/latest_report.md", content=report_md)`
  - return `"Wrote workspace/reports/latest_report.md"`

### 3.4 Create: `backend/agents/qa_agent.py`
Role: `Tester`

It should handle tasks:
- `"Analyze workspace for TODO/FIXME + suspicious strings + large files"`
  - call `analyze_workspace(root="workspace")`
  - call `append_insights_to_report` using the existing report content
  - write updated report
  - return summary: `todo_hits=X, suspicious_hits=Y`

Note: QA agent needs to read the current report. You can read from:
- `workspace/reports/latest_report.md` directly (safe)
Or store report string in orchestrator and pass it to agents (preferred later).
For now, simplest is to read it from disk.

---

## Step 4 — Update Orchestrator to use Agents + Tools

Modify:
`backend/core/orchestrator.py`

### 4.1 Keep same behavior and same 3 tasks
- Task creation stays
- Status updates stay
- Logs stay
- Snapshots stay
- Only replace internal implementation:
  - instead of calling `scan_directory / build_markdown_report / analyze_workspace` directly,
  - the orchestrator assigns tasks and calls the correct agent’s `run_task()`.

### 4.2 Add agent registry in orchestrator

Example mapping:
- `"dev_1"` → `DeveloperAgent("dev_1")`
- `"devops"` → `DevOpsAgent("devops")`
- `"qa_1"` → `QaAgent("qa_1")`

When task assigned_agent is X:
- select agent object
- run `agent.run_task(task_state)`
- capture returned result string
- mark task completed with that result

### 4.3 Maintain the lock-based “single run at a time”
Keep:
- `if get_run_in_progress(): return`
- `set_run_in_progress(True)` / False in finally

---

## Step 5 — Smoke tests (manual)

After completing Steps 1–4:

1) Start server:
   - `python driver.py`
2) Open:
   - http://127.0.0.1:8010
3) Click Run

Expected:
- Tasks complete as before
- Report file updated as before
- Logs show agent-specific lines
- No errors in console
- `data/runs/` contains run snapshots

---

## Done Criteria (this step is complete when)

✅ Orchestrator no longer imports `scanner_service` or `insights_service` directly  
✅ Orchestrator calls agent objects  
✅ Agents call tools via registry  
✅ Tools wrap your existing services  
✅ UI unchanged and still works

---

## Notes / Constraints (important)

- Agents may only operate inside `workspace/` for now.
- No LLM calls yet.
- No environment variables for this step.
- Keep functions deterministic and safe.

---

## Next Step after this (future)

Once this tool/agent architecture is stable:
- Add Claude/LLM only to Developer agent (small scope)
- Add Git sandbox in `workspace/repo/` so agents can commit and diff changes
- Add test runner tool and QA agent writes pytest files
- Add “Reviewer” agent that approves diffs

---

## Checklist (tomorrow execution order)

1) Create `backend/tools/tool_registry.py`
2) Create `backend/tools/workspace_tools.py` + register tools
3) Create `backend/agents/base_agent.py`
4) Create developer/devops/qa agent classes
5) Update orchestrator to use agents and tools
6) Run `python driver.py` and click Run
7) Verify `workspace/reports/latest_report.md` and UI tasks/logs