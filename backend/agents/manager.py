from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse

from backend.core.tasks import PlannedTask


class ManagerAgent:
    def __init__(self, agent_id: str = "manager") -> None:
        self.agent_id = agent_id

    def build_plan(self, repo_url: Optional[str] = None) -> List[PlannedTask]:
        repo_url = (repo_url or "").strip()

        if not repo_url:
            repo_url = "https://github.com/tiangolo/fastapi"

        repo_name = self._extract_repo_name(repo_url)

        # After clone, DevOps will store:
        # artifacts["repo_path"] = f"repos/{repo_name}"
        # and all downstream tasks will use that as target_subdir.
        return [
            PlannedTask(
                title="Clone target repository",
                task_type="clone_repository",
                assigned_agent="devops",
                payload={
                    "repo_url": repo_url,
                    "repo_name": repo_name,
                },
            ),
            PlannedTask(
                title="Inventory target repository files",
                task_type="inventory_workspace",
                assigned_agent="dev_1",
            ),
            PlannedTask(
                title="Select key files for analysis",
                task_type="select_key_files",
                assigned_agent="dev_1",
            ),
            PlannedTask(
                title="Summarize key files",
                task_type="summarize_key_files",
                assigned_agent="dev_1",
            ),
            PlannedTask(
                title="Analyze workspace structure and generate base report",
                task_type="scan_and_report",
                assigned_agent="dev_1",
            ),
            PlannedTask(
                title="Generate QA findings",
                task_type="build_qa_findings",
                assigned_agent="qa_1",
            ),
            PlannedTask(
                title="Review generated outputs",
                task_type="review_outputs",
                assigned_agent="reviewer",
            ),
            PlannedTask(
                title="Write artifacts to workspace",
                task_type="write_artifacts",
                assigned_agent="devops",
            ),
        ]

    def _extract_repo_name(self, repo_url: str) -> str:
        parsed = urlparse(repo_url)
        path = parsed.path.rstrip("/")

        if not path:
            raise ValueError(f"Invalid GitHub repository URL: {repo_url}")

        repo_name = path.split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        if not repo_name:
            raise ValueError(f"Could not extract repository name from URL: {repo_url}")

        return repo_name