# AI Dev Team System

## Overview

This project implements an **autonomous AI development team simulator**.

Multiple agents collaborate to analyze, improve, and extend a codebase using a shared workspace.

The system includes:

- FastAPI backend
- Dashboard UI
- Task orchestrator
- Agents with roles
- Tool system
- Persistent state
- Workspace sandbox

The goal is to eventually allow **AI agents to write code, run tests, and improve a project autonomously**.

---

# Architecture
# AI Dev Team System

## Overview

This project implements an **autonomous AI development team simulator**.

Multiple agents collaborate to analyze, improve, and extend a codebase using a shared workspace.

The system includes:

- FastAPI backend
- Dashboard UI
- Task orchestrator
- Agents with roles
- Tool system
- Persistent state
- Workspace sandbox

The goal is to eventually allow **AI agents to write code, run tests, and improve a project autonomously**.

---

# Architecture
UI Dashboard
↓
FastAPI API
↓
Orchestrator
↓
Agents
↓
Tools
↓
Workspacee

The orchestrator assigns tasks to agents.  
Agents use tools to interact with the workspace.

---

# Core Components

## Orchestrator

Location:
backend/core/orchestrator.py

Responsibilities:

- create tasks
- assign tasks to agents
- track run state
- log actions
- update persistence

Only **one run can execute at a time**.

---

# Agents

Agents simulate roles in a development team.

Current agents:

| Agent | Role |
|------|------|
| manager | Manager |
| dev_1 | Developer |
| qa_1 | Tester |
| devops | DevOps |
| reviewer | Reviewer |

Currently only the following agents execute real work:

- DeveloperAgent
- QaAgent
- DevOpsAgent

Manager and Reviewer are placeholders for future logic.

---

# Agent Responsibilities

## DeveloperAgent

Tasks:

- scan workspace
- later: generate code

Tools used:

- scan_workspace

---

## QaAgent

Tasks:

- analyze TODO/FIXME comments
- detect suspicious strings
- detect large files

Tools used:

- analyze_workspace

---

## DevOpsAgent

Tasks:

- generate markdown report
- write report to workspace

Tools used:

- build_report_md
- write_report

---

# Tools

Tools are registered in:
backend/tools/tool_registry.py

Agents can only perform actions through tools.

Current tools:

| Tool | Purpose |
|-----|------|
| scan_workspace | scan files and folders |
| build_report_md | generate markdown report |
| analyze_workspace | detect issues in workspace |
| write_report | write report to disk |

Tools provide a **safe interface to the filesystem**.

---

# Workspace

Agents operate inside:
workspace/
for example:
reports/
latest_report.md

Agents must **never modify files outside workspace/**.

---

# Persistence

State and logs are saved to:
data/state.json
data/logs.jsonl
data/runs/
Saved state includes:

- agents
- tasks
- run state

Logs are appended to `logs.jsonl`.

---

# Dashboard

Location:


frontend/


The dashboard shows:

- agents status
- tasks
- logs
- run/reset controls

State is fetched from:


GET /api/state
---

# Current Pipeline

When a run starts:

1. Scan workspace
2. Generate report
3. Analyze TODO/FIXME
4. Append insights to report

Output file:


workspace/reports/latest_report.md


---

# Future Roadmap

Next steps:

1. Introduce tool registry
2. Convert orchestrator to agent execution model
3. Add Claude-powered developer agent
4. Add test runner tool
5. Add git sandbox
6. Enable autonomous code generation

---

# Rules for AI Agents

Agents must follow these rules:

1. Never modify files outside `workspace/`
2. Only execute actions through registered tools
3. Always log actions
4. Return structured results
5. Avoid destructive operations

---

# Long-Term Goal

The system will evolve into a **self-improving AI development team** capable of:

- analyzing codebases
- generating improvements
- writing tests
- fixing bugs
- committing changes
- reviewing code

All within an isolated workspace.