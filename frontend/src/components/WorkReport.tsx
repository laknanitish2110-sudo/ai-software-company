"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { getWorkReport, type WorkReport, type WorkReportEmployee, type WorkReportExecution } from "@/lib/api";

const ROLE_ICONS: Record<string, string> = {
  "software engineer": "eng",
  researcher: "res",
  architect: "arc",
  "business analyst": "ba",
  "qa engineer": "qa",
  "technical writer": "tw",
};

const STATUS_COLORS: Record<string, string> = {
  completed: "var(--success)",
  failed: "var(--danger)",
  running: "var(--warning)",
  pending: "var(--text-muted)",
  cancelled: "var(--text-muted)",
};

function formatDuration(seconds: number | null): string {
  if (!seconds) return "--";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatTokens(tokens: number): string {
  if (tokens < 1000) return String(tokens);
  if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
  return `${(tokens / 1000000).toFixed(2)}M`;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ExecutionRow({ ex }: { ex: WorkReportExecution }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={{ marginBottom: 6 }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: "100%", textAlign: "left", background: "none", border: "none",
          padding: "8px 10px", borderRadius: 8, cursor: "pointer",
          display: "flex", alignItems: "center", gap: 8,
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = "var(--bg-hover)"}
        onMouseLeave={(e) => e.currentTarget.style.background = "none"}
      >
        <span style={{
          width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
          background: STATUS_COLORS[ex.status] || "var(--text-muted)",
        }} />
        <span style={{ flex: 1, fontSize: 12, fontWeight: 500, color: "var(--text-primary)", lineHeight: 1.4 }}>
          {ex.goal.length > 100 ? ex.goal.slice(0, 100) + "..." : ex.goal}
        </span>
        <span style={{ fontSize: 11, color: "var(--text-muted)", flexShrink: 0 }}>
          {formatDuration(ex.duration_seconds)}
        </span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{
          color: "var(--text-muted)", transform: expanded ? "rotate(180deg)" : "none",
          transition: "transform 0.15s", flexShrink: 0,
        }}>
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      {expanded && (
        <div style={{ padding: "4px 10px 8px 26px" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6 }}>
            <span style={{
              fontSize: 10, padding: "2px 8px", borderRadius: 4,
              background: ex.status === "completed" ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
              color: STATUS_COLORS[ex.status],
              fontWeight: 600, textTransform: "uppercase",
            }}>{ex.status}</span>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
              {ex.iteration} iterations
            </span>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
              {formatTokens(ex.tokens_used)} tokens
            </span>
          </div>
          {ex.phases_completed.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 6 }}>
              {ex.phases_completed.map((p, i) => (
                <span key={i} style={{
                  fontSize: 9, padding: "1px 6px", borderRadius: 3,
                  background: "var(--accent-bg)", color: "var(--accent)",
                  fontWeight: 500,
                }}>{p}</span>
              ))}
            </div>
          )}
          {ex.artifacts.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 3 }}>
                Artifacts ({ex.artifacts.length})
              </div>
              {ex.artifacts.map((a) => (
                <div key={a.id} style={{
                  fontSize: 11, color: "var(--text-secondary)", padding: "2px 0",
                  display: "flex", alignItems: "center", gap: 4,
                }}>
                  <span style={{ color: "var(--accent)", fontSize: 10 }}>+</span>
                  {a.title}
                  {a.language && <span style={{ fontSize: 9, color: "var(--text-muted)" }}>({a.language})</span>}
                </div>
              ))}
            </div>
          )}
          {ex.error && (
            <div style={{
              marginTop: 4, fontSize: 11, color: "var(--danger)",
              padding: "4px 8px", borderRadius: 4, background: "rgba(239,68,68,0.06)",
            }}>
              {ex.error.length > 200 ? ex.error.slice(0, 200) + "..." : ex.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EmployeeSection({ emp }: { emp: WorkReportEmployee }) {
  const icon = ROLE_ICONS[emp.employee_role.toLowerCase()] || "ai";

  return (
    <div style={{
      border: "1px solid var(--border)", borderRadius: 12,
      overflow: "hidden", marginBottom: 12,
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "12px 14px", borderBottom: "1px solid var(--border)",
        background: "var(--bg-card)",
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: "var(--accent-bg)", color: "var(--accent)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 10, fontWeight: 700, flexShrink: 0, textTransform: "uppercase",
        }}>{icon}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
            {emp.employee_name}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "capitalize" }}>
            {emp.employee_role}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            {emp.completed > 0 && (
              <span style={{ fontSize: 11, color: "var(--success)", fontWeight: 600 }}>
                {emp.completed} done
              </span>
            )}
            {emp.failed > 0 && (
              <span style={{ fontSize: 11, color: "var(--danger)", fontWeight: 600 }}>
                {emp.failed} failed
              </span>
            )}
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {formatTokens(emp.total_tokens)} tokens
            </span>
          </div>
        </div>
      </div>
      <div style={{ padding: "6px 4px" }}>
        {emp.executions.map((ex) => (
          <ExecutionRow key={ex.execution_id} ex={ex} />
        ))}
      </div>
    </div>
  );
}

interface Props {
  onDismiss?: () => void;
}

export default function WorkReportPanel({ onDismiss }: Props) {
  const [report, setReport] = useState<WorkReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [hours, setHours] = useState(24);
  const [showTimeline, setShowTimeline] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await getWorkReport(hours);
      setReport(r);
    } catch {
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [hours]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div style={{
        padding: 24, borderRadius: 16, border: "1px solid var(--border)",
        background: "var(--bg-card)", marginBottom: 20,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{
            width: 20, height: 20, border: "2px solid var(--border)",
            borderTopColor: "var(--accent)", borderRadius: "50%",
            animation: "spin 0.6s linear infinite",
          }} />
          <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Loading work report...</span>
        </div>
      </div>
    );
  }

  if (!report || !report.has_activity) return null;

  const { summary } = report;

  return (
    <div style={{
      borderRadius: 16, border: "1px solid var(--accent-border)",
      background: "var(--bg-card)", marginBottom: 20, overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        padding: "16px 20px", display: "flex", alignItems: "center", gap: 12,
        borderBottom: "1px solid var(--border)",
        background: "linear-gradient(135deg, var(--accent-bg), transparent)",
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: "var(--accent)", color: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 16, flexShrink: 0,
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
          </svg>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)" }}>
            While You Were Away
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
            Your team completed work in the last {hours} hours
          </div>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {[8, 24, 72].map((h) => (
            <button
              key={h}
              onClick={() => setHours(h)}
              style={{
                padding: "4px 10px", borderRadius: 6, border: "1px solid var(--border)",
                background: hours === h ? "var(--accent)" : "transparent",
                color: hours === h ? "#fff" : "var(--text-muted)",
                fontSize: 11, fontWeight: 600, cursor: "pointer",
                transition: "all 0.15s",
              }}
            >{h}h</button>
          ))}
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            style={{
              background: "none", border: "none", cursor: "pointer",
              color: "var(--text-muted)", padding: 4, borderRadius: 6,
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        )}
      </div>

      {/* Summary Stats */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
        gap: 1, background: "var(--border)",
      }}>
        {[
          { label: "Executions", value: String(summary.total_executions), color: "var(--text-primary)" },
          { label: "Completed", value: String(summary.completed), color: "var(--success)" },
          { label: "Failed", value: String(summary.failed), color: summary.failed > 0 ? "var(--danger)" : "var(--text-muted)" },
          { label: "Artifacts", value: String(summary.total_artifacts), color: "var(--accent)" },
          { label: "Tokens Used", value: formatTokens(summary.total_tokens), color: "var(--text-secondary)" },
          { label: "Employees", value: String(summary.active_employees || report.employees.length), color: "var(--text-secondary)" },
        ].map((stat) => (
          <div key={stat.label} style={{
            padding: "12px 16px", background: "var(--bg-card)",
            textAlign: "center",
          }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: stat.color }}>{stat.value}</div>
            <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Employee Sections */}
      <div style={{ padding: "16px 16px 8px" }}>
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          marginBottom: 12,
        }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
            Work by Employee
          </span>
          {report.timeline.length > 0 && (
            <button
              onClick={() => setShowTimeline(!showTimeline)}
              style={{
                fontSize: 11, color: "var(--accent)", background: "none",
                border: "none", cursor: "pointer", fontWeight: 500,
              }}
            >{showTimeline ? "Hide Timeline" : "Show Timeline"}</button>
          )}
        </div>

        {report.employees.map((emp) => (
          <EmployeeSection key={emp.employee_id} emp={emp} />
        ))}
      </div>

      {/* Timeline */}
      {showTimeline && report.timeline.length > 0 && (
        <div style={{
          padding: "0 16px 16px", borderTop: "1px solid var(--border)",
          marginTop: 4, paddingTop: 12,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 10 }}>
            Timeline
          </div>
          {report.timeline.map((t, i) => (
            <div key={i} style={{
              display: "flex", gap: 10, padding: "6px 0",
              borderBottom: i < report.timeline.length - 1 ? "1px solid var(--border)" : "none",
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: "50%", flexShrink: 0, marginTop: 4,
                background: STATUS_COLORS[t.status] || "var(--text-muted)",
              }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: "var(--text-primary)" }}>
                  <strong>{t.employee_name}</strong>: {t.event}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 1 }}>
                  {timeAgo(t.timestamp)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
