import { useState, useEffect } from "react";
import { DollarSign, Zap, AlertTriangle, CheckCircle } from "lucide-react";
import { fetchCosts } from "../api";
import type { CostData } from "../types";

interface Props {
  refreshTick: number;
}

export default function CostDashboard({ refreshTick }: Props) {
  const [data, setData] = useState<CostData | null>(null);

  useEffect(() => {
    fetchCosts().then(setData).catch(() => {});
  }, [refreshTick]);

  if (!data) return null;

  const barColor =
    data.percent_used >= 90 ? "var(--danger)"
    : data.percent_used >= 70 ? "var(--warning)"
    : "var(--primary)";

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <DollarSign size={15} /> LLM Cost
          <span style={{ fontWeight: 400, color: "var(--text-soft)", fontSize: 12 }}>
            &nbsp;{data.period}
          </span>
        </span>
        {data.within_budget ? (
          <span style={{ display: "flex", alignItems: "center", gap: 4,
                         fontSize: 11, color: "#16a34a" }}>
            <CheckCircle size={12} /> Within budget
          </span>
        ) : (
          <span style={{ display: "flex", alignItems: "center", gap: 4,
                         fontSize: 11, color: "var(--danger)", fontWeight: 600 }}>
            <AlertTriangle size={12} /> Budget exceeded!
          </span>
        )}
      </div>

      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>

        {/* Spend vs Budget progress bar */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between",
                        fontSize: 12, marginBottom: 6 }}>
            <span style={{ color: "var(--text-soft)" }}>
              ${data.spent_usd.toFixed(4)} spent
            </span>
            <span style={{ fontWeight: 600 }}>
              ${data.budget_usd.toFixed(2)} budget
            </span>
          </div>
          <div style={{ height: 8, background: "var(--border)",
                        borderRadius: 4, overflow: "hidden" }}>
            <div style={{
              height: "100%",
              width: `${Math.min(data.percent_used, 100)}%`,
              background: barColor,
              borderRadius: 4,
              transition: "width 0.4s ease",
            }} />
          </div>
          <div style={{ fontSize: 11, color: "var(--text-soft)", marginTop: 4 }}>
            {data.percent_used.toFixed(1)}% used &mdash; ${data.remaining_usd.toFixed(4)} remaining
          </div>
        </div>

        {/* Stats row */}
        <div style={{ display: "flex", gap: 12 }}>
          <div style={{ flex: 1, padding: "10px 12px", background: "var(--bg)",
                        borderRadius: 8, border: "1px solid var(--border)" }}>
            <div style={{ fontSize: 11, color: "var(--text-soft)" }}>Total tokens</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "var(--mono)" }}>
              {data.total_tokens.toLocaleString()}
            </div>
          </div>
          <div style={{ flex: 1, padding: "10px 12px", background: "var(--bg)",
                        borderRadius: 8, border: "1px solid var(--border)" }}>
            <div style={{ fontSize: 11, color: "var(--text-soft)" }}>API calls</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "var(--mono)" }}>
              {data.total_calls}
            </div>
          </div>
        </div>

        {/* Per-model breakdown — only shown once real calls exist */}
        {data.per_model.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-soft)",
                          textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 8 }}>
              By model
            </div>
            {data.per_model.map((m) => (
              <div key={m.model} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "5px 0", borderBottom: "1px solid var(--border)", fontSize: 12,
              }}>
                <span style={{ fontFamily: "var(--mono)", color: "var(--primary)" }}>
                  {m.model}
                </span>
                <span style={{ color: "var(--text-soft)" }}>
                  {m.tokens.toLocaleString()} tokens
                </span>
                <span style={{ fontWeight: 600 }}>${m.cost_usd.toFixed(4)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {data.total_calls === 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8,
                        fontSize: 12, color: "var(--text-soft)" }}>
            <Zap size={13} />
            No LLM calls yet — tracking starts when real agents run
          </div>
        )}

      </div>
    </div>
  );
}
