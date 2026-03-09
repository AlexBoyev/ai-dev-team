# Next Step Plan — GitHub URL Input + Repo Clone + Real Repository Analysis

## Current System

You already built a working multi-agent pipeline:

Agents
- manager
- dev_1 (Developer)
- qa_1 (Tester)
- reviewer
- devops

Architecture
- orchestrator → agents → tool registry → workspace
- UI dashboard with Run / Reset
- `/api/state` polling
- persistent state/logs
- artifacts written to workspace

Generated artifacts
- report.md
- code_summary.md
- qa_findings.md
- review.md
- final_summary.md
- repo_inventory.json
- selected_files.json

Current limitation:

The system expects a repo already inside `workspace/`, so analysis returns 0 files unless a repo exists locally.

---

# Goal of This Step

Allow the **user to enter a GitHub repository URL in the UI**.

The system should:

1. accept GitHub URL
2. clone repo automatically
3. analyze cloned repo
4. generate reports

---

# Target Execution Flow

User enters GitHub URL

→ Run button  
→ backend receives repo_url  
→ manager builds plan  
→ devops clones repo  
→ developer analyzes repo  
→ qa generates findings  
→ reviewer evaluates outputs  
→ devops writes artifacts  

All agents operate **only inside workspace/**.

---

# Workspace Layout After Run


workspace/
repos/
fastapi/
report.md
code_summary.md
qa_findings.md
review.md
final_summary.md
repo_inventory.json
selected_files.json


---

# Files To Modify

Backend

backend/
agents/
manager.py
devops_agent.py
core/
orchestrator.py
api/
routes.py
tools/
tool_registry.py


Frontend

frontend/
templates/index.html
static/app.js


---

# Step 1 — Add Git Clone Tool

File


backend/tools/tool_registry.py


Add a new tool:


clone_git_repo


Responsibilities

- accept repo_url
- clone repository into:


workspace/repos/<repo_name>


- return relative path:


repos/<repo_name>


Requirements

- use:


git clone --depth 1


- skip clone if repo already exists
- must remain inside workspace
- raise clear error on clone failure

---

# Step 2 — Extend DevOps Agent

File


backend/agents/devops_agent.py


Add new task:


clone_repository


Behavior

1. read repo_url from payload
2. call tool `clone_git_repo`
3. return result:


{
"repo_path": "repos/<repo_name>",
"result_message": "Repository cloned"
}


This prepares the repository before analysis tasks begin.

---

# Step 3 — Update Manager Agent

File


backend/agents/manager.py


Manager should now:

- accept optional `repo_url`
- use default repo if empty
- create clone task first

Example plan

1 Clone repository  
2 Inventory files  
3 Select key files  
4 Summarize files  
5 Scan repository structure  
6 Generate QA findings  
7 Review outputs  
8 Write artifacts  

Manager must extract repository name from the GitHub URL.

Example


https://github.com/tiangolo/fastapi


repo_name


fastapi


---

# Step 4 — Update Orchestrator

File


backend/core/orchestrator.py


Modify main run function:


demo_run(repo_url: str | None)


Pass repo_url to:


manager.build_plan(repo_url)


---

## Payload Injection

After cloning, devops returns:


artifacts["repo_path"]


Orchestrator must inject this into later tasks.

Tasks requiring repo path

- inventory_workspace
- select_key_files
- summarize_key_files
- scan_and_report
- build_qa_findings

Payload should include


payload["target_subdir"] = artifacts["repo_path"]


---

# Step 5 — Update API Route

File


backend/api/routes.py


Modify `/api/run`.

It should accept JSON body.

Example request


POST /api/run
{
"repo_url": "https://github.com/tiangolo/fastapi
"
}


Route should

1 read repo_url  
2 start background thread  
3 call


demo_run(repo_url)


Keep current behavior

- asynchronous run
- single run at a time
- UI polling unchanged

---

# Step 6 — Update UI

File


frontend/templates/index.html


Add input field above Run button.

Example


[ GitHub repository URL __________________ ]

[ Run ] [ Reset ]


Use id


repo-url-input


Placeholder


https://github.com/owner/repo


Do not redesign the UI layout.

---

# Step 7 — Update Frontend JavaScript

File


frontend/static/app.js


Modify Run button handler.

Steps

1 read value from input


document.getElementById("repo-url-input")


2 send POST request


/api/run


with body


{ "repo_url": "<value>" }


Example


fetch("/api/run", {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({ repo_url })
})


Keep polling logic unchanged.

---

# Step 8 — Testing

Test 1

Input


https://github.com/tiangolo/fastapi


Expected dashboard logs

- Repository cloned
- Indexed hundreds of files
- Selected key files
- Summarized files
- QA findings generated
- Review complete
- Artifacts written

---

Test 2

Empty input

Expected

Manager uses default repo.

---

Test 3

Invalid GitHub URL

Expected

- clone fails
- clear error logged
- run stops safely

---

# Step 9 — Done Criteria

This milestone is complete when

- UI accepts GitHub URL
- `/api/run` accepts JSON input
- manager builds clone-first plan
- devops clones repo
- developer analyzes repo
- qa generates findings
- reviewer evaluates outputs
- devops writes artifacts
- UI still works with polling
- no manual repo setup required

---

# Next Step After This

Future milestone


LLM-powered agents


Developer agent will:

- decide which tools to use
- explore repository
- propose improvements

This will turn the system into a **real autonomous dev-team simulator**.