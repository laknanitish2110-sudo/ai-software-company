"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getExecution, getExecutionLogs, getExecutionArtifacts, cancelExecution2,
  type AutonomousExecution, type ExecutionLog, type ExecutionArtifact,
} from "@/lib/api";

const STATES = [
  "PLANNING", "IMPLEMENTING", "EXECUTING", "OBSERVING",
  "REPAIRING", "TESTING", "QA", "DELIVERING", "COMPLETED",
];

const STATE_ICONS: Record<string, string> = {
  PLANNING: "📋", IMPLEMENTING: "💻", EXECUTING: "▶️", OBSERVING: "🔍",
  REPAIRING: "🔧", TESTING: "🧪", QA: "🛡️", DELIVERING: "📦",
  COMPLETED: "✅", FAILED: "❌", CANCELLED: "⏹️",
};

const STATE_COLORS: Record<string, string> = {
  PLANNING: "#3b82f6", IMPLEMENTING: "#f59e0b", EXECUTING: "#8b5cf6",
  OBSERVING: "#06b6d4", REPAIRING: "#ef4444", TESTING: "#10b981",
  QA: "#f97316", DELIVERING: "#6366f1", COMPLETED: "#22c55e",
  FAILED: "#ef4444", CANCELLED: "#6b7280",
};

interface Props {
  executionId: string;
  onDismiss?: () => void;
}

export default function ExecutionProgress({ executionId, onDismiss }: Props) {
  const [execution, setExecution] = useState<AutonomousExecution | null>(null);
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [artifacts, setArtifacts] = useState<ExecutionArtifact[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [showLogs, setShowLogs] = useState(false);
  const [showArtifacts, setShowArtifacts] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const poll = useCallback(async () => {
    try {
      const { execution: exec } = await getExecution(executionId);
      setExecution(exec);

      if (exec.status === "running" || exec.status === "completed") {
        const { logs: l } = await getExecutionLogs(executionId);
        setLogs(l);
      }
      if (exec.status === "completed") {
        const { artifacts: a } = await getExecutionArtifacts(executionId);
        setArtifacts(a);
      }
    } catch {
      // silently ignore poll errors
    }
  }, [executionId]);

  useEffect(() => {
    poll();
    const interval = setInterval(() => {
      poll();
    }, 3000);
    return () => clearInterval(interval);
  }, [poll]);

  useEffect(() => {
    if (execution && (execution.status === "completed" || execution.status === "failed" || execution.status === "cancelled")) {
      // final fetch
      getExecutionLogs(executionId).then(r => setLogs(r.logs)).catch(() => {});
      getExecutionArtifacts(executionId).then(r => setArtifacts(r.artifacts)).catch(() => {});
    }
  }, [execution?.status, executionId]);

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await cancelExecution2(executionId);
      await poll();
    } catch {
      // ignore
    }
    setCancelling(false);
  };

  if (!execution) {
    return (
      <div style={{
        padding: 16, background: "var(--bg-elevated, #1a1a2e)",
        borderRadius: 12, border: "1px solid var(--border, #2a2a3e)",
        marginBottom: 16,
      }}>
        <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>Loading execution...</div>
      </div>
    );
  }

  const isActive = execution.status === "running";
  const isDone = execution.status === "completed";
  const isFailed = execution.status === "failed";
  const currentStateIdx = STATES.indexOf(execution.state);
  const progress = execution.progress ? JSON.parse(execution.progress) : null;

  return (
    <div style={{
      background: "var(--bg-elevated, #1a1a2e)",
      borderRadius: 14,
      border: `1px solid ${isDone ? "rgba(34,197,94,0.3)" : isFailed ? "rgba(239,68,68,0.3)" : "rgba(99,91,255,0.3)"}`,
      marginBottom: 16,
      overflow: "hidden",
      boxShadow: isActive ? "0 0 20px rgba(99,91,255,0.1)" : "none",
      transition: "all 0.3s",
    }}>
      {/* Header */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: "14px 16px",
          display: "flex", alignItems: "center", gap: 10,
          cursor: "pointer",
          background: isActive ? "rgba(99,91,255,0.04)" : isDone ? "rgba(34,197,94,0.04)" : "transparent",
        }}
      >
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: `${STATE_COLORS[execution.state] || "#6366f1"}15`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 16,
        }}>
          {STATE_ICONS[execution.state] || "⚙️"}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: "var(--text-primary)",
            display: "flex", alignItems: "center", gap: 6,
          }}>
            Autonomous Execution
            {isActive && (
              <span style={{
                display: "inline-block", width: 6, height: 6, borderRadius: "50%",
                background: "#22c55e",
                animation: "pulse 2s ease-in-out infinite",
              }} />
            )}
          </div>
          <div style={{
            fontSize: 12, color: "var(--text-secondary)",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {execution.goal.length > 60 ? execution.goal.slice(0, 60) + "..." : execution.goal}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {isActive && (
            <button
              onClick={(e) => { e.stopPropagation(); handleCancel(); }}
              disabled={cancelling}
              style={{
                padding: "4px 10px", borderRadius: 6, border: "1px solid rgba(239,68,68,0.3)",
                background: "rgba(239,68,68,0.08)", color: "#ef4444",
                fontSize: 11, fontWeight: 600, cursor: "pointer",
                opacity: cancelling ? 0.5 : 1,
              }}
            >
              {cancelling ? "..." : "Cancel"}
            </button>
          )}
          <div style={{
            padding: "3px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600,
            background: `${STATE_COLORS[execution.state] || "#6366f1"}15`,
            color: STATE_COLORS[execution.state] || "#6366f1",
          }}>
            {execution.state}
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: "0 16px 16px" }}>
          {/* State machine pipeline */}
          <div style={{
            display: "flex", gap: 2, marginBottom: 14, overflowX: "auto",
            padding: "8px 0",
          }}>
            {STATES.map((s, i) => {
              const isPast = i < currentStateIdx;
              const isCurrent = s === execution.state;
              const color = STATE_COLORS[s] || "#6366f1";
              return (
                <div key={s} style={{
                  flex: 1, minWidth: 28,
                  height: 4, borderRadius: 2,
                  background: isCurrent
                    ? color
                    : isPast
                      ? `${color}80`
                      : "var(--border, #2a2a3e)",
                  transition: "background 0.3s",
                  position: "relative",
                }}>
                  {isCurrent && isActive && (
                    <div style={{
                      position: "absolute", top: -1, left: 0, right: 0,
                      height: 6, borderRadius: 3,
                      background: color,
                      animation: "pulse 2s ease-in-out infinite",
                    }} />
                  )}
                </div>
              );
            })}
          </div>

          {/* Stats row */}
          <div style={{
            display: "flex", gap: 16, fontSize: 12, color: "var(--text-secondary)",
            marginBottom: 12, flexWrap: "wrap",
          }}>
            <span>Iteration: <strong style={{ color: "var(--text-primary)" }}>{execution.iteration}/{execution.max_iterations}</strong></span>
            <span>Tokens: <strong style={{ color: "var(--text-primary)" }}>{(execution.tokens_used / 1000).toFixed(1)}k</strong></span>
            {progress?.elapsed_seconds != null && (
              <span>Time: <strong style={{ color: "var(--text-primary)" }}>{progress.elapsed_seconds}s</strong></span>
            )}
            <span>Status: <strong style={{ color: STATE_COLORS[execution.status === "completed" ? "COMPLETED" : execution.status === "failed" ? "FAILED" : execution.state] || "var(--text-primary)" }}>{execution.status}</strong></span>
          </div>

          {/* Error */}
          {execution.error && (
            <div style={{
              padding: "8px 12px", borderRadius: 8, marginBottom: 12,
              background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)",
              fontSize: 12, color: "#ef4444", fontFamily: "monospace",
              wordBreak: "break-word",
            }}>
              {execution.error}
            </div>
          )}

          {/* Result */}
          {execution.result && isDone && (
            <div style={{
              padding: "10px 12px", borderRadius: 8, marginBottom: 12,
              background: "rgba(34,197,94,0.06)", border: "1px solid rgba(34,197,94,0.15)",
              fontSize: 12, color: "var(--text-primary)", lineHeight: 1.5,
              maxHeight: 200, overflow: "auto",
              whiteSpace: "pre-wrap",
            }}>
              {execution.result.length > 1000 ? execution.result.slice(0, 1000) + "..." : execution.result}
            </div>
          )}

          {/* Logs toggle */}
          <div style={{ display: "flex", gap: 8, marginBottom: showLogs || showArtifacts ? 10 : 0 }}>
            <button
              onClick={() => { setShowLogs(!showLogs); setShowArtifacts(false); }}
              style={{
                padding: "5px 12px", borderRadius: 6, border: "1px solid var(--border)",
                background: showLogs ? "rgba(99,91,255,0.1)" : "transparent",
                color: showLogs ? "var(--accent, #6366f1)" : "var(--text-secondary)",
                fontSize: 11, fontWeight: 600, cursor: "pointer",
              }}
            >
              Logs ({logs.length})
            </button>
            {artifacts.length > 0 && (
              <button
                onClick={() => { setShowArtifacts(!showArtifacts); setShowLogs(false); }}
                style={{
                  padding: "5px 12px", borderRadius: 6, border: "1px solid var(--border)",
                  background: showArtifacts ? "rgba(99,91,255,0.1)" : "transparent",
                  color: showArtifacts ? "var(--accent, #6366f1)" : "var(--text-secondary)",
                  fontSize: 11, fontWeight: 600, cursor: "pointer",
                }}
              >
                Artifacts ({artifacts.length})
              </button>
            )}
            {onDismiss && !isActive && (
              <button
                onClick={onDismiss}
                style={{
                  marginLeft: "auto",
                  padding: "5px 12px", borderRadius: 6, border: "1px solid var(--border)",
                  background: "transparent", color: "var(--text-secondary)",
                  fontSize: 11, fontWeight: 600, cursor: "pointer",
                }}
              >
                Dismiss
              </button>
            )}
          </div>

          {/* Logs list */}
          {showLogs && logs.length > 0 && (
            <div style={{
              maxHeight: 250, overflow: "auto",
              borderRadius: 8, border: "1px solid var(--border)",
            }}>
              {logs.map((log, i) => (
                <div key={log.id} style={{
                  padding: "6px 10px",
                  borderBottom: i < logs.length - 1 ? "1px solid var(--border)" : "none",
                  fontSize: 11, display: "flex", gap: 8, alignItems: "center",
                }}>
                  <span style={{
                    width: 20, textAlign: "center",
                    color: "var(--text-muted)", fontFamily: "monospace",
                  }}>
                    {log.iteration}
                  </span>
                  <span style={{
                    padding: "1px 6px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                    background: `${STATE_COLORS[log.state] || "#6366f1"}15`,
                    color: STATE_COLORS[log.state] || "#6366f1",
                    minWidth: 70, textAlign: "center",
                  }}>
                    {log.state}
                  </span>
                  <span style={{
                    flex: 1, color: "var(--text-secondary)",
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>
                    {log.output_summary ? log.output_summary.slice(0, 80) : log.action}
                  </span>
                  {log.duration_ms != null && (
                    <span style={{ color: "var(--text-muted)", fontSize: 10 }}>
                      {(log.duration_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                  <span style={{
                    width: 14, height: 14, borderRadius: "50%",
                    background: log.success ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 8, color: log.success ? "#22c55e" : "#ef4444",
                  }}>
                    {log.success ? "✓" : "✗"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Artifacts list */}
          {showArtifacts && artifacts.length > 0 && (
            <div style={{
              maxHeight: 250, overflow: "auto",
              borderRadius: 8, border: "1px solid var(--border)",
            }}>
              {artifacts.map((artifact, i) => (
                <div key={artifact.id} style={{
                  padding: "8px 10px",
                  borderBottom: i < artifacts.length - 1 ? "1px solid var(--border)" : "none",
                  fontSize: 12, display: "flex", gap: 8, alignItems: "center",
                }}>
                  <span style={{ fontSize: 14 }}>📄</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{artifact.title}</div>
                    {artifact.path && (
                      <div style={{
                        fontSize: 11, color: "var(--text-secondary)", fontFamily: "monospace",
                      }}>
                        {artifact.path}
                      </div>
                    )}
                  </div>
                  {artifact.language && (
                    <span style={{
                      padding: "1px 6px", borderRadius: 4, fontSize: 10,
                      background: "var(--bg-card)", color: "var(--text-secondary)",
                    }}>
                      {artifact.language}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
