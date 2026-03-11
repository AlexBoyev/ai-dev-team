# Next Steps — AI Dev Team

## Status
Pipeline is stable. Multi-repo support working. Per-run artifact isolation done.
UI is clean — tasks, logs, artifacts load correctly per repo.

---

## Step 1 — Live Polling During Runs (Frontend)

**Problem:** TaskTable and LogViewer fetch once on mount. During an active run
you see nothing until you manually refresh.

**Fix:** When `run_in_progress=true`, poll TaskTable and LogViewer every 2-3s.
Stop polling when run completes.

### Files to change
- `frontend/src/components/TaskTable.tsx`
  - Add `useEffect` interval that polls `fetchTasks(runId)` every 2500ms
  - Only activate interval when `running=true` prop
  - Clear interval on unmount or when running stops
- `frontend/src/components/LogViewer.tsx`
  - Same pattern — poll `fetchLogs(runId)` every 2500ms during active run
  - Append new logs, don't replace (avoid flicker)
- `frontend/src/App.tsx`
  - Pass `running={state.run_in_progress}` to TaskTable and LogViewer

### Props to add
```tsx
// TaskTable
interface Props {
  runId: string | null;
  refreshTick: number;
  running: boolean;   // ← new
}

// LogViewer
interface Props {
  runId: string | null;
  refreshTick: number;
  running: boolean;   // ← new
}
Step 2 — Run Cancellation (Stop Button)
Problem: No way to stop a running pipeline mid-execution.
Critical before adding real LLM agents that cost money.

Fix: Show a Stop button in RepoSelector (next to Run) only when
running=true. Calls /api/reset which revokes the Celery task.

Files to change
frontend/src/components/RepoSelector.tsx

Add Stop button next to Run button, visible only when running=true

frontend/src/App.tsx

Wire onStop handler that calls postReset() then poll()

backend/api/routes.py

/api/reset already exists and revokes Celery task — no changes needed

UI pattern
tsx
{running ? (
  <button className="btn btn-danger" onClick={onStop}>
    <Square size={13} /> Stop
  </button>
) : (
  <button className="btn btn-primary" onClick={onRun}
    disabled={!repoUrl.trim()}>
    <Play size={13} /> Run
  </button>
)}
Step 3 — Prompt Versioning
Problem: All agent prompts are hardcoded strings inside agent Python files.
Changing a prompt = code change + redeploy.

Fix: Move prompts to backend/prompts/ as YAML files.
Load at runtime. Each prompt has name + version + template.

Structure
text
backend/
  prompts/
    scan_and_report_v1.yaml
    summarize_key_files_v1.yaml
    build_qa_findings_v1.yaml
    review_outputs_v1.yaml
YAML format
text
name: scan_and_report
version: 1
model: gpt-4o
max_tokens: 2000
temperature: 0.2
system: |
  You are a senior software engineer analyzing a codebase...
user_template: |
  Analyze the following files from {repo_name}:
  {file_contents}
  Generate a structured report covering...
Files to create/change
backend/prompts/ — create folder + YAML files per task

backend/core/prompt_loader.py — loads YAML, renders template with vars

Each agent — replace hardcoded strings with prompt_loader.get("scan_and_report")

Step 4 — Cost / Token Tracking
Problem: No visibility into LLM spend per run or per task.

Fix: Add LLMCall table. Every LLM call logs tokens + cost.
Show per-run total cost in Run History.

New DB table
python
class LLMCall(Base):
    __tablename__ = "llm_calls"
    id            = Column(UUID, primary_key=True, default=uuid4)
    run_id        = Column(String, ForeignKey("runs.id"))
    task_id       = Column(String, ForeignKey("tasks.id"))
    agent_key     = Column(String)
    model         = Column(String)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    cost_usd      = Column(Numeric(10, 6))
    ts            = Column(DateTime)
Files to create/change
backend/db/models.py — add LLMCall model

backend/core/llm_client.py — wrapper around OpenAI/Anthropic that logs
every call to LLMCall table automatically

backend/api/routes.py — add /api/runs/{run_id}/cost endpoint

frontend/src/components/RunHistory.tsx — show cost column

New Alembic migration

Step 5 — First Real Agent
Start with: DeveloperAgent → scan_and_report task only.

Replace the rule-based report builder with a single GPT-4o call.
Use prompt from prompts/scan_and_report_v1.yaml.
Log tokens to LLMCall table.
Validate output quality before converting other agents.

Files to change
backend/agents/developer_agent.py

scan_and_report task: read selected files → call llm_client.complete()
→ return structured markdown report

backend/core/llm_client.py — must exist from Step 4

Current Service Names (docker compose)
backend — FastAPI + Alembic

frontend — React + Nginx

worker — Celery

postgres — DB

redis — Broker

Rebuild Commands
powershell
docker compose up --build -d backend worker   # Python changes
docker compose up --build -d frontend         # React changes
docker compose up --build -d                  # Everything
Key File Locations
text
backend/
  agents/
    developer_agent.py
    devops_agent.py
    qa_agent.py
    reviewer_agent.py
    manager.py
  api/
    routes.py
  core/
    orchestrator.py
    tasks.py
  db/
    models.py
    session.py
  prompts/          ← create in Step 3

frontend/src/
  components/
    TaskTable.tsx
    LogViewer.tsx
    ArtifactViewer.tsx
    RepoSelector.tsx
    RunHistory.tsx
    Header.tsx
  App.tsx
  api.ts
  types.ts
  index.css