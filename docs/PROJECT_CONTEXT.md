# AI Dev Team Project Context

This file describes the project structure and system behavior so that AI tools and developers can quickly understand the repository.

---

# Project Goal

Build a **multi-agent AI development team simulator** where autonomous agents collaborate to analyze, improve, and extend a codebase.

Agents operate in a shared workspace and communicate through tasks and logs.

The system will evolve into a platform capable of autonomous software development.

---

# Technology Stack

Backend

- Python 3.12
- FastAPI
- Uvicorn

Frontend

- HTML
- CSS
- Vanilla JavaScript

Persistence

- JSON state storage
- JSONL logs

Workspace

- Local sandbox folder where agents operate

Future additions:

- Docker
- Git integration
- LLM-powered agents

---

# Repository Structure
backend/
agents/
api/
core/
services/
tools/

frontend/
static/
templates/

workspace/
reports/

data/
state.json
logs.jsonl
runs/

docs/
AGENTS.md
PROJECT_CONTEXT.md

driver.py

---

# Backend Components

## Orchestrator

Location:
backend/core/orchestrator.py

Responsibilities:

- create tasks
- assign tasks
- execute pipeline
- log results
- manage run lifecycle

Only one run can execute at a time.

---

## Memory System

Location:
backend/core/memory.py
Stores:

- agent states
- tasks
- logs
- run status

---

## Persistence

Location:
backend/core/persistence.py

Stores data to disk.

Files:
data/state.json
data/logs.jsonl
data/runs/


---

# Tools System

Location:


backend/tools/


Tools are the only way agents interact with the environment.

Current tools:


scan_workspace
build_report_md
analyze_workspace
write_report


Future tools:


read_file
write_file
run_tests
git_commit
git_diff
generate_code


---

# Workspace

Agents operate inside:


workspace/


Example:


workspace/
reports/
latest_report.md


Agents must never modify files outside this folder.

---

# Dashboard

Location:


frontend/


Provides real-time monitoring.

Shows:

- agent status
- task queue
- run logs
- system controls

Endpoints:


GET /api/state
POST /api/run
POST /api/reset


---

# Current Pipeline

When Run is pressed:

1. Scan workspace
2. Generate markdown report
3. Analyze TODO/FIXME and suspicious strings
4. Append insights to report

Output:


workspace/reports/latest_report.md


---

# Current Limitations

- Agents are not yet autonomous
- No LLM integration
- Tasks are predefined
- No Git version control

---

# Future Roadmap

Planned improvements:

Phase 1

- Tool registry
- Real agent classes
- Agent task execution

Phase 2

- Claude / GPT integration
- AI-generated code
- Test generation

Phase 3

- Git sandbox
- Pull request simulation
- Code review agent

Phase 4

- Autonomous development loops
- Multi-repo support
- Scalable architecture

---

# System Rules

Agents must follow strict constraints.

1. Operate only inside workspace
2. Use registered tools only
3. Log all actions
4. Avoid destructive operations
5. Return structured outputs

---

# Vision

The long-term goal is to create an **autonomous AI software team** capable of improving and maintaining a project with minimal human input.