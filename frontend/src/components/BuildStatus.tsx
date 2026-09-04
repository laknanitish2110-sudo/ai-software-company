"use client";

import { useState } from "react";

interface StageResult {
  status: string;
  exit_code: number | null;
  duration_ms: number;
  stdout_snippet: string;
  stderr_snippet: string;
}

interface RepairAttemptInfo {
  attempt: number;
  qa_status: string;
  failure_category: string;
  patch_status: string;
  reason: string;
}

export interface ValidationResult {
  attempts_used: number;
  final_status: string;
  reason: string;
  final_execution_result?: {
    overall_status: string;
    stages: Record<string, StageResult>;
    duration_ms: number;
    failed_stage?: string | null;
  };
  final_qa_report?: {
    status: string;
    severity: string;
    root_cause: string;
    failure_category: string;
  };
  repair_history?: RepairAttemptInfo[];
}

const STAGE_ORDER = ["SANDBOX_INIT", "INSTALL", "BUILD", "TEST", "START", "HEALTH_CHECK"];

const STAGE_LABELS: Record<string, string> = {
  SANDBOX_INIT: "Sandbox Init",
  INSTALL: "Install Deps",
  BUILD: "Build",
  TEST: "Run Tests",
  START: "Start App",
  HEALTH_CHECK: "Health Check",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function BuildStatus({ validationResult }: { validationResult: ValidationResult }) {
  const [expandedStage, setExpandedStage] = useState<string | null>(null);
  const [showRepairs, setShowRepairs] = useState(false);

  const { final_status, attempts_used, final_execution_result, repair_history } = validationResult;
  const passed = final_status === "VALIDATED";
  const stages = final_execution_result?.stages || {};
  const totalDuration = final_execution_result?.duration_ms || 0;

  return (
    <div
      className="card animate-fade-in"
      style={{
        border: `1px solid ${passed ? "var(--success-border)" : "var(--danger-border, rgba(237,95,116,0.3))"}`,
        background: passed ? "rgba(16,185,129,0.04)" : "rgba(237,95,116,0.04)",
        padding: 0,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: `1px solid ${passed ? "var(--success-border)" : "var(--danger-border, rgba(237,95,116,0.3))"}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 18 }}>{passed ? "✅" : "❌"}</span>
          <span style={{ fontWeight: 600, fontSize: 14, color: "var(--text-primary)" }}>
            Build {passed ? "Passed" : "Failed"}
          </span>
          <span
            className="status-badge"
            style={{
              background: passed ? "var(--success-bg)" : "rgba(237,95,116,0.1)",
              color: passed ? "var(--success)" : "var(--danger)",
              border: `1px solid ${passed ? "var(--success-border)" : "var(--danger-border, rgba(237,95,116,0.3))"}`,
              fontSize: 11,
            }}
          >
            {final_status}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 12, color: "var(--text-muted)" }}>
          {totalDuration > 0 && <span>{formatDuration(totalDuration)}</span>}
          {attempts_used > 1 && (
            <span
              style={{
                background: "rgba(245,158,11,0.1)",
                color: "#f59e0b",
                border: "1px solid rgba(245,158,11,0.3)",
                borderRadius: 12,
                padding: "2px 8px",
                fontSize: 11,
              }}
            >
              {attempts_used} attempts
            </span>
          )}
        </div>
      </div>

      {/* Stage pipeline */}
      <div style={{ padding: "12px 16px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {STAGE_ORDER.map((stageName) => {
            const stage = stages[stageName];
            if (!stage) return null;

            const isPassed = stage.status === "PASSED";
            const isFailed = stage.status === "FAILED";
            const isSkipped = stage.status === "SKIPPED";
            const hasError = isFailed && (stage.stderr_snippet || stage.stdout_snippet);
            const isExpanded = expandedStage === stageName;

            return (
              <div key={stageName}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "6px 8px",
                    borderRadius: 6,
                    cursor: hasError ? "pointer" : "default",
                    background: isExpanded ? "var(--bg-elevated)" : "transparent",
                  }}
                  onClick={() => hasError && setExpandedStage(isExpanded ? null : stageName)}
                >
                  {/* Status icon */}
                  <span
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 11,
                      fontWeight: 700,
                      flexShrink: 0,
                      background: isPassed ? "var(--success-bg)" : isFailed ? "rgba(237,95,116,0.1)" : "var(--bg-elevated)",
                      color: isPassed ? "var(--success)" : isFailed ? "var(--danger)" : "var(--text-muted)",
                      border: `1px solid ${isPassed ? "var(--success-border)" : isFailed ? "var(--danger-border, rgba(237,95,116,0.3))" : "var(--border)"}`,
                    }}
                  >
                    {isPassed ? "✓" : isFailed ? "✗" : "—"}
                  </span>

                  {/* Label */}
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 500,
                      flex: 1,
                      color: isSkipped ? "var(--text-muted)" : "var(--text-primary)",
                    }}
                  >
                    {STAGE_LABELS[stageName] || stageName}
                  </span>

                  {/* Duration */}
                  {stage.duration_ms > 0 && (
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {formatDuration(stage.duration_ms)}
                    </span>
                  )}

                  {/* Expand arrow */}
                  {hasError && (
                    <span style={{ fontSize: 10, color: "var(--text-muted)", transition: "transform 0.2s", transform: isExpanded ? "rotate(180deg)" : "rotate(0)" }}>
                      ▼
                    </span>
                  )}
                </div>

                {/* Error details */}
                {isExpanded && hasError && (
                  <div
                    style={{
                      margin: "4px 0 4px 38px",
                      padding: "8px 12px",
                      borderRadius: 6,
                      background: "var(--bg-primary, #111)",
                      border: "1px solid var(--border)",
                      fontSize: 11,
                      fontFamily: "monospace",
                      color: "var(--danger)",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      maxHeight: 200,
                      overflowY: "auto",
                    }}
                  >
                    {stage.stderr_snippet || stage.stdout_snippet}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Repair history */}
      {repair_history && repair_history.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border)", padding: "8px 16px" }}>
          <button
            onClick={() => setShowRepairs(!showRepairs)}
            style={{
              background: "none",
              border: "none",
              color: "#f59e0b",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: 0,
            }}
          >
            <span style={{ fontSize: 10, transition: "transform 0.2s", transform: showRepairs ? "rotate(180deg)" : "rotate(0)" }}>▼</span>
            Repair Attempts ({repair_history.length})
          </button>
          {showRepairs && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
              {repair_history.map((attempt) => (
                <div
                  key={attempt.attempt}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 6,
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    fontSize: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>Attempt {attempt.attempt}</span>
                    <span
                      style={{
                        fontSize: 10,
                        padding: "1px 6px",
                        borderRadius: 8,
                        background: attempt.patch_status === "APPLIED" ? "var(--success-bg)" : "rgba(237,95,116,0.1)",
                        color: attempt.patch_status === "APPLIED" ? "var(--success)" : "var(--danger)",
                      }}
                    >
                      {attempt.patch_status}
                    </span>
                    <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{attempt.failure_category}</span>
                  </div>
                  {attempt.reason && (
                    <div style={{ marginTop: 4, fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4 }}>
                      {attempt.reason.slice(0, 200)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
