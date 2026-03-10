export interface Agent {
  name: string;
  role: string;
  status: "idle" | "working" | "done" | "failed";
  current_task_id: string | null;
  last_action: string | null;
}

export interface Task {
  id: string;
  title: string;
  task_type: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  assigned_agent: string;
  result: string | null;
}

export interface LogEntry {
  ts: number;
  level: string;
  source: string;
  message: string;
}

export interface AppState {
  run_in_progress: boolean;
  run_id: string | null;
  agents: Agent[];
  tasks: Task[];
  logs: LogEntry[];
}

export interface Repo {
  id: string;
  name: string;
  url: string | null;
  local_path: string;
  disk_bytes: number;
  cloned_at: string | null;
  last_run_id: string | null;
}

export interface Run {
  id: string;
  status: string;
  repo_url: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Artifact {
  id: string;
  name: string;
  size_bytes: number;
}
