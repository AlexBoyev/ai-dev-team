import type { Agent } from "../types";
import { Bot } from "lucide-react";

const EMOJI: Record<string, string> = {
  manager: "🧠", dev_1: "💻", qa_1: "🔍", reviewer: "👁️", devops: "⚙️",
};

interface Props { agents: Agent[]; }

export default function AgentsPanel({ agents }: Props) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title"><Bot size={15} /> Agents</span>
      </div>
      <div className="card-body">
        <div className="agents-grid">
          {agents.map((a) => (
            <div key={a.name} className={`agent-card ${a.status}`}>
              <div className="agent-avatar">{EMOJI[a.name] ?? "🤖"}</div>
              <div className="agent-info">
                <div className="agent-name">{a.name}</div>
                <div className="agent-action">
                  {a.last_action ?? "Waiting..."}
                </div>
              </div>
              <span className={`badge badge-${a.status}`}>
                <span className={`dot ${a.status === "working" ? "dot-pulse" : ""}`} />
                {a.status}
              </span>
            </div>
          ))}
          {agents.length === 0 && <p className="empty">No agents active</p>}
        </div>
      </div>
    </div>
  );
}
