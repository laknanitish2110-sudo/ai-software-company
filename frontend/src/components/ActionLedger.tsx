"use client";

import { useState, useEffect } from "react";
import { getExecutionLedger, getLedgerSummary, type LedgerEntry, type LedgerSummary } from "@/lib/api";

const ACTION_ICONS: Record<string, string> = {
  execution_start: "▶",
  phase_transition: "→",
  llm_reasoning: "⚙",
  tool_execution: "⚡",
  sentinel_verification: "✔",
  delegation: "⇆",
  execution_complete: "█",
};

const ACTION_COLORS: Record<string, string> = {
  execution_start: "var(--brand)",
  phase_transition: "var(--info)",
  llm_reasoning: "var(--text-muted)",
  tool_execution: "var(--warning)",
  sentinel_verification: "var(--success)",
  delegation: "var(--brand-secondary, var(--brand))",
  execution_complete: "var(--success)",
};

const COMMIT_COLORS: Record<string, string> = {
  committed: "var(--success)",
  rolled_back: "var(--danger)",
  pending: "var(--warning)",
};

function formatMs(ms: number | null): string {
  if (!ms) return "--";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTokens(tokens: number): string {
  if (tokens < 1000) return String(tokens);
  if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
  return `${(tokens / 1000000).toFixed(2)}M`;
}

function SummaryBar({ summary }: { summary: LedgerSummary }) {
  const stats = [
    { label: "Actions", value: summary.total_entries, color: "var(--text)" },
    { label: "Committed", value: summary.committed, color: "var(--success)" },
    { label: "Rolled Back", value: summary.rolled_back, color: "var(--danger)" },
    { label: "Tools Used", value: summary.tool_executions, color: "var(--warning)" },
    { label: "Verifications", value: summary.verifications, color: "var(--info)" },
    { label: "Tokens", value: formatTokens(summary.total_tokens || 0), color: "var(--text-muted)" },
  ];

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))",
      gap: "8px",
      marginBottom: "16px",
    }}>
      {stats.map((s) => (
        <div key={s.label} style={{
          background: "var(--bg-secondary)",
          borderRadius: "8px",
          padding: "10px 12px",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "18px", fontWeight: 700, color: s.color }}>
            {s.value}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
            {s.label}
          </div>
        </div>
      ))}
    </div>
  );
}

function LedgerEntryRow({ entry, isLast }: { entry: LedgerEntry; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const icon = ACTION_ICONS[entry.action_type] || "•";
  const color = ACTION_COLORS[entry.action_type] || "var(--text-muted)";
  const commitColor = COMMIT_COLORS[entry.commit_decision] || "var(--text-muted)";

  const evidence = entry.evidence as Record<string, unknown> | null;
  const verification = entry.verification_result as Record<string, unknown> | null;

  return (
    <div style={{ display: "flex", gap: "12px", position: "relative" }}>
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        minWidth: "28px",
      }}>
        <div style={{
          width: "28px",
          height: "28px",
          borderRadius: "50%",
          background: color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "13px",
          color: "#fff",
          flexShrink: 0,
        }}>
          {icon}
        </div>
        {!isLast && (
          <div style={{
            width: "2px",
            flex: 1,
            background: "var(--border)",
            minHeight: "16px",
          }} />
        )}
      </div>

      <div style={{
        flex: 1,
        paddingBottom: isLast ? 0 : "12px",
        minWidth: 0,
      }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            cursor: "pointer",
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <span style={{ fontWeight: 600, fontSize: "13px", color: "var(--text)" }}>
            {entry.intent || entry.action_type}
          </span>
          <span style={{
            fontSize: "10px",
            padding: "1px 6px",
            borderRadius: "4px",
            background: commitColor,
            color: "#fff",
            fontWeight: 600,
            textTransform: "uppercase",
          }}>
            {entry.commit_decision}
          </span>
          {entry.duration_ms != null && (
            <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
              {formatMs(entry.duration_ms)}
            </span>
          )}
          <span style={{
            fontSize: "11px",
            color: "var(--text-muted)",
            marginLeft: "auto",
          }}>
            {expanded ? "▲" : "▼"}
          </span>
        </div>

        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
          {entry.actor && <span>{entry.actor} &middot; </span>}
          <span>{entry.phase}</span>
          {entry.tokens_used > 0 && <span> &middot; {formatTokens(entry.tokens_used)} tokens</span>}
        </div>

        {expanded && (
          <div style={{
            marginTop: "8px",
            padding: "10px",
            background: "var(--bg-secondary)",
            borderRadius: "6px",
            fontSize: "12px",
          }}>
            {entry.actual_effects && (
              <div style={{ marginBottom: "6px" }}>
                <strong style={{ color: "var(--text-muted)" }}>Effects: </strong>
                <span>{entry.actual_effects}</span>
              </div>
            )}
            {evidence && (
              <div style={{ marginBottom: "6px" }}>
                <strong style={{ color: "var(--text-muted)" }}>Evidence: </strong>
                <pre style={{
                  margin: "4px 0 0",
                  padding: "8px",
                  background: "var(--bg)",
                  borderRadius: "4px",
                  fontSize: "11px",
                  overflow: "auto",
                  maxHeight: "200px",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>
                  {JSON.stringify(evidence, null, 2)}
                </pre>
              </div>
            )}
            {verification && (
              <div style={{ marginBottom: "6px" }}>
                <strong style={{ color: "var(--text-muted)" }}>Verification: </strong>
                <pre style={{
                  margin: "4px 0 0",
                  padding: "8px",
                  background: "var(--bg)",
                  borderRadius: "4px",
                  fontSize: "11px",
                  overflow: "auto",
                  maxHeight: "200px",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>
                  {JSON.stringify(verification, null, 2)}
                </pre>
              </div>
            )}
            {entry.authority && (
              <div>
                <strong style={{ color: "var(--text-muted)" }}>Authority: </strong>
                <span>{entry.authority}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ActionLedgerPanel({ executionId }: { executionId: string }) {
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [summary, setSummary] = useState<LedgerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const [ledgerRes, summaryRes] = await Promise.all([
          getExecutionLedger(executionId),
          getLedgerSummary(executionId),
        ]);
        setEntries(ledgerRes.entries);
        setSummary(summaryRes.summary);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load ledger");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [executionId]);

  if (loading) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)" }}>
        Loading action ledger...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "var(--danger)" }}>
        {error}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)" }}>
        No ledger entries yet. Run an autonomous execution to generate causal records.
      </div>
    );
  }

  const filtered = filter === "all"
    ? entries
    : entries.filter((e) => e.action_type === filter);

  const filterOptions = [
    { value: "all", label: "All" },
    { value: "phase_transition", label: "Phases" },
    { value: "llm_reasoning", label: "Reasoning" },
    { value: "tool_execution", label: "Tools" },
    { value: "sentinel_verification", label: "Sentinel" },
  ];

  return (
    <div style={{
      background: "var(--bg)",
      borderRadius: "12px",
      border: "1px solid var(--border)",
      padding: "16px",
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: "12px",
      }}>
        <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "var(--text)" }}>
          Action Ledger
        </h3>
        <div style={{ display: "flex", gap: "4px" }}>
          {filterOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              style={{
                padding: "3px 8px",
                borderRadius: "4px",
                border: "none",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
                background: filter === opt.value ? "var(--brand)" : "var(--bg-secondary)",
                color: filter === opt.value ? "#fff" : "var(--text-muted)",
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {summary && <SummaryBar summary={summary} />}

      <div style={{ maxHeight: "500px", overflowY: "auto" }}>
        {filtered.map((entry, i) => (
          <LedgerEntryRow
            key={entry.id}
            entry={entry}
            isLast={i === filtered.length - 1}
          />
        ))}
      </div>
    </div>
  );
}
