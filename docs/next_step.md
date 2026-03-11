# next_step.md — AI Dev Team

Last updated: 2026-03-11
Status: Phase 3 done. Phase 4 blocked — need agent source files.

---

## ✅ Phase 1 — Core Pipeline (DONE)
## ✅ Phase 2 — UI & Live Polling (DONE)
## ✅ Phase 3 — Cost Tracking + Prompt Versioning (DONE)
- Prompt YAMLs created: developer_scan.yaml, developer_summarize.yaml,
  qa_findings.yaml, reviewer.yaml
- PromptLoader built (backend/core/prompt_loader.py)
- Agents DO NOT use prompts yet — still rule-based

---

## 🔴 Phase 4 — LLM Integration (CURRENT)

### What's needed to start:
Upload these files in a NEW conversation:
  1. backend/agents/base_agent.py
  2. backend/agents/developer_agent.py
  3. backend/agents/qa_agent.py
  4. backend/agents/reviewer_agent.py
  5. backend/agents/devops_agent.py
  6. backend/core/orchestrator.py
  7. backend/core/prompt_loader.py   (if not yet shared)
  8. backend/prompts/*.yaml          (all 4 yamls)

### Steps once files are available:

Step 4.1 — base_agent.py: add _call_llm(prompt_name, context, db, run_id)
  - Load + render YAML prompt via PromptLoader
  - Call anthropic.Anthropic().messages.create(model, messages)
  - Write result to llm_calls table
  - Return response text string

Step 4.2 — developer_agent.py
  - summarize_key_files → use developer_summarize.yaml
    - ALSO FIX: skip binary files, open with errors="replace"
    - ALSO FIX: filter out .git/ paths from inventory
  - scan_and_report     → use developer_scan.yaml

Step 4.3 — qa_agent.py
  - build_qa_findings   → use qa_findings.yaml

Step 4.4 — reviewer_agent.py
  - review_outputs      → use reviewer.yaml

Step 4.5 — devops_agent.py
  - NO changes needed. Keep as-is.

Step 4.6 — orchestrator.py
  - Pass db + run_id into ToolContext (or agent constructor)
  - So _call_llm() can write cost rows to DB

Step 4.7 — verify end-to-end
  - Run full pipeline on any repo
  - Check /api/costs shows tokens + USD per agent
  - Confirm CostDashboard renders

---

## Known Bugs (fix in Phase 4)

| Bug | File | Fix |
|-----|------|-----|
| UTF-8 crash on binary files | developer_agent.py | open(..., errors="replace"), skip binary extensions |
| .git/ folder indexed | developer_agent.py | filter paths containing /.git/ |
| final_summary.md empty sections | devops_agent.py | resolves once LLM output has correct markdown headings |

---

## Phase 5 — Quality & Reliability (PLANNED)
- Retry logic on Claude failures (backoff, max 3)
- Per-run token budget cap
- Structured output parsing
- Fallback to rule-based if LLM fails
- prompt_version column in llm_calls table

## Phase 6 — Multi-Repo & Scheduling (PLANNED)
## Phase 7 — Agent Memory & Context (PLANNED)
