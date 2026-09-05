"use client";

import { useEffect, useState } from "react";
import { getProjectCosts, CostSummary } from "@/lib/api";
import { AGENT_CONFIG } from "@/lib/constants";

interface Props {
  projectId: string;
  costEvent?: { role: string; tokens: number; totals?: Record<string, unknown> } | null;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function CostMonitor({ projectId, costEvent }: Props) {
  const [data, setData] = useState<CostSummary | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    getProjectCosts(projectId).then(setData).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    if (costEvent) {
      getProjectCosts(projectId).then(setData).catch(() => {});
    }
  }, [costEvent, projectId]);

  const totals = data?.totals;
  const perAgent = data?.per_agent || [];
  const budget = data?.budget;
  const totalTokens = totals?.total_tokens || 0;
  const maxTokens = budget?.max_tokens || 0;
  const callCount = totals?.total_calls || 0;
  const maxCalls = budget?.max_llm_calls || 50;
  const budgetPct = maxTokens > 0 ? Math.min(100, (totalTokens / maxTokens) * 100) : 0;
  const callPct = maxCalls > 0 ? Math.min(100, (callCount / maxCalls) * 100) : 0;

  const barColor = budgetPct > 80 ? "var(--danger)" : budgetPct > 50 ? "var(--warning)" : "var(--success)";
  const callBarColor = callPct > 80 ? "var(--danger)" : callPct > 50 ? "var(--warning)" : "var(--accent)";

  return (
    <div className="card p-4 animate-fade-in">
      <div
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }}
        onClick={() => setExpanded(!expanded)}
      >
        <h3
          className="font-semibold text-xs uppercase tracking-wider"
          style={{ color: "var(--text-muted)" }}
        >
          Cost Governor
        </h3>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: "var(--text-secondary)", fontFamily: "monospace" }}>
            {formatTokens(totalTokens)} tokens
          </span>
          <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
            {expanded ? "▲" : "▼"}
          </span>
        </div>
      </div>

      {/* Budget bars — always visible */}
      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
        {/* Token budget bar */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-muted)", marginBottom: 2 }}>
            <span>Tokens</span>
            <span>{formatTokens(totalTokens)}{maxTokens > 0 ? ` / ${formatTokens(maxTokens)}` : ""}</span>
          </div>
          <div style={{ height: 6, borderRadius: 3, background: "var(--bg-secondary)", overflow: "hidden" }}>
            <div style={{
              height: "100%", borderRadius: 3,
              background: barColor,
              width: maxTokens > 0 ? `${budgetPct}%` : `${Math.min(100, totalTokens / 5000)}%`,
              transition: "width 0.5s ease",
            }} />
          </div>
        </div>

        {/* LLM calls bar */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-muted)", marginBottom: 2 }}>
            <span>LLM Calls</span>
            <span>{callCount} / {maxCalls}</span>
          </div>
          <div style={{ height: 6, borderRadius: 3, background: "var(--bg-secondary)", overflow: "hidden" }}>
            <div style={{
              height: "100%", borderRadius: 3,
              background: callBarColor,
              width: `${callPct}%`,
              transition: "width 0.5s ease",
            }} />
          </div>
        </div>
      </div>

      {/* Expanded: per-agent breakdown */}
      {expanded && perAgent.length > 0 && (
        <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Per Agent
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {perAgent.map((agent) => {
              const config = AGENT_CONFIG[agent.role];
              const agentPct = totalTokens > 0 ? (agent.total_tokens / totalTokens) * 100 : 0;
              return (
                <div key={agent.role} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
                  <span style={{ width: 16, textAlign: "center" }}>{config?.icon || "?"}</span>
                  <span style={{ flex: 1, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {config?.label || agent.role}
                  </span>
                  <span style={{ fontFamily: "monospace", color: "var(--text-muted)", fontSize: 10, minWidth: 50, textAlign: "right" }}>
                    {formatTokens(agent.total_tokens)}
                  </span>
                  <div style={{ width: 40, height: 4, borderRadius: 2, background: "var(--bg-secondary)", overflow: "hidden" }}>
                    <div style={{
                      height: "100%", borderRadius: 2,
                      background: config?.color || "var(--accent)",
                      width: `${agentPct}%`,
                    }} />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Cost summary footer */}
          <div style={{
            marginTop: 10, paddingTop: 8, borderTop: "1px solid var(--border)",
            display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-muted)",
          }}>
            <span>Est. cost: ${(totals?.total_cost || 0).toFixed(4)}</span>
            <span>
              {budget?.budget_status === "OK" ? (
                <span style={{ color: "var(--success)" }}>Budget OK</span>
              ) : (
                <span style={{ color: "var(--danger)" }}>Budget Exceeded</span>
              )}
            </span>
          </div>
        </div>
      )}

      {expanded && perAgent.length === 0 && (
        <div style={{ marginTop: 10, fontSize: 11, color: "var(--text-muted)", textAlign: "center" }}>
          No LLM calls recorded yet
        </div>
      )}
    </div>
  );
}
