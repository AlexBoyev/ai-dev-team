# AI Dev Team Factory

## Overview

AI Dev Team Factory is an experimental autonomous software development platform where AI agents collaborate like a real engineering team.

The platform orchestrates multiple agents responsible for planning, developing, testing, reviewing, and running software.

The system simulates a real software engineering organization with roles such as:

- Manager
- Developer
- Tester
- DevOps
- Reviewer

The system coordinates tasks between agents and gradually builds and maintains a software product.

The long-term goal is to explore how AI agents can autonomously maintain and improve complex codebases.

---

# Repository Structure

The repository contains two major components.

## 1. Agent Platform

The agent platform is the orchestration system.

It manages:

- agent coordination
- task management
- LLM integration
- execution tools
- system logging
- configuration

Agents collaborate through tasks and operate on a workspace project.

---

## 2. Workspace Project

The workspace project is the actual software product being built by the agents.

Agents can read and modify files in the workspace project.

Agents must **never modify the agent platform itself**.

This separation prevents the agents from breaking the orchestration system.

---

# Directory Structure
ai-dev-team/

core/
config.py
orchestrator.py
tasks.py
memory.py
llm_client.py

agents/
manager_agent.py
developer_agent.py
tester_agent.py
reviewer_agent.py
devops_agent.py

tools/
file_tools.py
execution_tools.py
git_tools.py
github_tools.py

workspace/
code_analyzer/

docs/
PROJECT_GUIDE.md
architecture.md

main.py
requirements.txt

---

# Workspace Product

## Autonomous Codebase Analyzer

The workspace project is a system that analyzes software repositories and provides insights into architecture, complexity, and potential improvements.

This product evolves through several stages.

---

# Stage 1 — Repository Analyzer

The system reads repositories and generates reports.

Features include:

- repository structure analysis
- dependency graphs
- code complexity metrics
- dead code detection
- unused import detection

Example output files:
analysis_report.md
dependency_graph.json
complexity_report.md


The analyzer is read-only during this stage.

---

# Stage 2 — Code Review Assistant

The analyzer begins suggesting improvements.

Example capabilities:

- detect long functions
- detect duplicated code
- suggest refactoring
- detect missing tests
- detect potential performance issues

Reports may include suggestions like:

Example:

File: api/users.py

Function create_user() is 120 lines long.

Suggestion:
Split validation logic into a separate module.

At this stage the system still does not automatically modify code.

---

# Stage 3 — Autonomous Code Maintainer

The system begins interacting with repositories.

Capabilities include:

- reading GitHub issues
- generating code patches
- generating tests
- running builds
- opening pull requests

Example workflow:

1. Manager reads GitHub issues
2. Developer generates fix
3. Tester generates test
4. DevOps runs build
5. Reviewer validates patch
6. Pull request is opened

This stage turns the system into an autonomous code maintenance assistant.

---

# Agent Roles

## Manager Agent

Responsibilities:

- create tasks
- prioritize backlog
- plan development
- coordinate team workflow

Example tasks:

- implement dependency graph
- add complexity metrics
- fix issue #52
- implement unused import detection

---

## Developer Agent

Responsibilities:

- implement features
- modify workspace code
- refactor modules
- optimize architecture

Developer agents may only modify files inside the workspace project.

---

## Tester Agent

Responsibilities:

- generate tests
- run tests
- detect regressions
- report failures

Testing will use frameworks such as pytest.

---

## DevOps Agent

Responsibilities:

- run builds
- execute tests
- manage runtime environment
- produce build reports

Later versions may run builds inside Docker containers.

---

## Reviewer Agent

Responsibilities:

- review generated code
- enforce architecture rules
- detect security risks
- approve or reject changes

Reviewer acts as the safety gate before merging code.

---

# Task System

Agents communicate through tasks.

Each task contains:

- id
- title
- description
- assigned_agent
- status
- result

Task lifecycle:

pending → in_progress → completed

Possible statuses:

- pending
- in_progress
- completed
- failed
- rejected

The orchestrator manages task assignment and state transitions.

---

# Orchestrator

The orchestrator is the central control system.

Responsibilities:

1. read tasks
2. select appropriate agent
3. execute task
4. record results
5. update task state

The orchestrator is started from the main application entry point.

Example:
python main.py


---

# LLM Usage Policy

Large Language Models assist the system but must not control core system logic.

LLMs may be used for:

- generating code
- generating tests
- explaining errors
- suggesting refactors

System control must remain deterministic Python logic.

---

# Configuration

Configuration is centralized.

Environment variables include:

- API keys
- model selection
- token limits
- request throttling
- daily token limits
- usage tracking file

Configuration must be loaded via `core/config.py`.

Example environment variables:
ANTHROPIC_API_KEY=...

LLM_MODEL_CHEAP=claude-3-haiku
LLM_MODEL_STRONG=claude-3-5-sonnet

LLM_MAX_TOKENS=800
LLM_TEMPERATURE=0.2

LLM_DAILY_TOKEN_LIMIT=250000

LLM_MIN_SECONDS_BETWEEN_CALLS=1.0
LLM_MAX_CALLS_PER_MINUTE=30

LLM_USAGE_FILE=.llm_usage.json
ANTHROPIC_API_KEY=...

LLM_MODEL_CHEAP=claude-3-haiku
LLM_MODEL_STRONG=claude-3-5-sonnet

LLM_MAX_TOKENS=800
LLM_TEMPERATURE=0.2

LLM_DAILY_TOKEN_LIMIT=250000

LLM_MIN_SECONDS_BETWEEN_CALLS=1.0
LLM_MAX_CALLS_PER_MINUTE=30

LLM_USAGE_FILE=.llm_usage.json