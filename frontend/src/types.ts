export interface Agent {
  name:            string;
  role:            string;
  status:          "idle" | "working" | "done" | "failed";
  current_task_id: string | null;
  last_action:     string | null;
}

export interface Task {
  id:             string;
  title:          string;
  task_type:      string;
  status:         "pending" | "in_progress" | "completed" | "failed";
  assigned_agent: string;
  result:         string | null;
  iteration:      number;
  approved:       boolean | null;
}

export interface LogEntry {
  ts:      number;
  level:   string;
  source:  string;
  message: string;
}

export interface AppState {
  run_in_progress: boolean;
  run_id:          string | null;
  agents:          Agent[];
  tasks:           Task[];
  logs:            LogEntry[];
}

export interface Repo {
  id:          string;
  name:        string;
  url:         string | null;
  local_path:  string;
  disk_bytes:  number;
  cloned_at:   string | null;
  last_run_id: string | null;
}

export interface Run {
  id:                string;
  status:            string;
  repo_url:          string | null;
  started_at:        string | null;
  finished_at:       string | null;
  current_iteration: number;
  awaiting_approval: boolean;
}

export interface Artifact {
  id:         string;
  name:       string;
  size_bytes: number;
}

export interface CostData {
  budget_usd:    number;
  spent_usd:     number;
  remaining_usd: number;
  percent_used:  number;
  total_tokens:  number;
  total_calls:   number;
  within_budget: boolean;
  period:        string;
  per_run: {
    run_id:   string;
    cost_usd: number;
    tokens:   number;
    calls:    number;
  }[];
  per_model: {
    model:    string;
    cost_usd: number;
    tokens:   number;
  }[];
}
