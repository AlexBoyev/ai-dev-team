# AI Dev Team – Agent Definitions

This document defines the agents used in the AI development team system.

Agents simulate a real software team and collaborate through tasks assigned by the orchestrator.

Each agent can only interact with the system using **registered tools**.

---

# System Architecture

Orchestrator  
↓  
Agents  
↓  
Tools  
↓  
Workspace  

Agents never directly modify files or call services.  
All actions must go through tools.

---

# Agent List

## Manager

Role: Project manager.

Responsibilities:

- Create initial tasks
- Monitor progress
- Detect blocked tasks
- Assign tasks to agents
- Approve pipeline stages

Future responsibilities:

- Prioritize backlog
- Detect project risks
- Spawn additional tasks

Current implementation:

Manager is currently simulated by the orchestrator.

---

## Developer Agent

Name example:
dev1

Role: Software developer.

Responsibilities:

- Scan workspace structure
- Generate code modules
- Refactor code
- Implement features

Current tasks:

- Scan workspace directory

Future tasks:

- Write Python modules
- Implement TODO fixes
- Generate helper utilities

Tools used:

- scan_workspace
- write_file
- read_file

Future tools:

- generate_code
- modify_code
- create_module

---

## QA Agent

Name example:
qa_1

Role: Software tester / quality engineer.

Responsibilities:

- Detect TODO comments
- Detect FIXME comments
- Detect suspicious strings
- Detect large files

Future responsibilities:

- Generate pytest tests
- Detect bugs
- Validate code output
- Run static analysis

Tools used:

- analyze_workspace

Future tools:

- run_tests
- generate_tests
- lint_code

---

## DevOps Agent

Name example:
devops

Role: CI/CD and reporting engineer.

Responsibilities:

- Generate system reports
- Save reports to workspace
- Manage artifacts

Current tasks:

- Write markdown report

Tools used:

- build_report_md
- write_report

Future tools:

- run_tests
- build_docker
- deploy_service

---

## Reviewer Agent

Name example:
reviewer

Role: Code reviewer.

Responsibilities:

- Review code diffs
- Approve or reject changes
- Evaluate code quality

Future tools:

- git_diff
- git_commit
- git_revert

Currently not implemented.

---

# Agent Communication

Agents do not talk directly to each other.

Communication happens through:

- tasks
- logs
- workspace artifacts

Example:

DeveloperAgent → creates code file  
QAAgent → tests file  
DevOpsAgent → reports results  

---

# Agent Rules

Agents must follow strict rules.

1. Never modify files outside `workspace/`
2. Use only registered tools
3. Always log actions
4. Return structured results
5. Avoid destructive operations
6. Never overwrite files unless instructed

---

# Agent Task Lifecycle

Task statuses:

pending
in_progress
completed
failed
rejected


Lifecycle:


pending → in_progress → completed


Failure:


pending → in_progress → failed


Agents must update task status.

---

# Future AI Integration

Later versions will integrate LLM agents.

Example:

DeveloperAgent will call:

Claude / GPT model

to generate code.

Example pipeline:

DeveloperAgent  
↓  
LLM generates code  
↓  
write_file tool saves module  
↓  
QAAgent tests it  
↓  
Reviewer approves  

---

# Long-Term Vision

The AI Dev Team will eventually be able to:

- analyze codebases
- generate new modules
- write tests
- fix bugs
- run CI pipelines
- deploy services

All autonomously.
