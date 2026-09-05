"use client";

import { useState } from "react";

interface SecurityFinding {
  severity: string;
  category: string;
  file: string;
  line: number;
  message: string;
  snippet: string;
}

export interface SecurityScanEvent {
  status: "PASS" | "WARN" | "FAIL";
  summary: string;
  findings_count: number;
  critical_count: number;
  high_count?: number;
  medium_count?: number;
  low_count?: number;
  files_scanned: number;
  findings?: SecurityFinding[];
}

interface Props {
  scan: SecurityScanEvent;
}

const STATUS_CONFIG = {
  PASS: { bg: "rgba(16,185,129,0.10)", border: "rgba(16,185,129,0.3)", color: "#10b981", icon: "🛡️", label: "Secure" },
  WARN: { bg: "rgba(245,158,11,0.10)", border: "rgba(245,158,11,0.3)", color: "#f59e0b", icon: "⚠️", label: "Warnings" },
  FAIL: { bg: "rgba(239,68,68,0.10)", border: "rgba(239,68,68,0.3)", color: "#ef4444", icon: "🚨", label: "Critical" },
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#f59e0b",
  low: "#6b7280",
};

export default function SecurityBadge({ scan }: Props) {
  const [expanded, setExpanded] = useState(false);
  const config = STATUS_CONFIG[scan.status] || STATUS_CONFIG.PASS;
  const findings = scan.findings || [];

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
          Security Gate
        </h3>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 10,
            background: config.bg, color: config.color,
            border: `1px solid ${config.border}`,
          }}>
            {config.icon} {config.label}
          </span>
          <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
            {expanded ? "▲" : "▼"}
          </span>
        </div>
      </div>

      {/* Summary row */}
      <div style={{ marginTop: 8, display: "flex", gap: 12, fontSize: 11, color: "var(--text-secondary)" }}>
        <span>{scan.files_scanned} files scanned</span>
        <span style={{ color: config.color }}>{scan.findings_count} finding{scan.findings_count !== 1 ? "s" : ""}</span>
      </div>

      {/* Severity breakdown bar */}
      {scan.findings_count > 0 && (
        <div style={{ marginTop: 8, display: "flex", gap: 8, fontSize: 10 }}>
          {scan.critical_count ? (
            <span style={{ color: SEVERITY_COLORS.critical, fontWeight: 600 }}>
              {scan.critical_count} critical
            </span>
          ) : null}
          {scan.high_count ? (
            <span style={{ color: SEVERITY_COLORS.high, fontWeight: 600 }}>
              {scan.high_count} high
            </span>
          ) : null}
          {scan.medium_count ? (
            <span style={{ color: SEVERITY_COLORS.medium }}>
              {scan.medium_count} medium
            </span>
          ) : null}
          {scan.low_count ? (
            <span style={{ color: SEVERITY_COLORS.low }}>
              {scan.low_count} low
            </span>
          ) : null}
        </div>
      )}

      {/* Expanded: finding details */}
      {expanded && findings.length > 0 && (
        <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Findings
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 300, overflowY: "auto" }}>
            {findings.map((f, i) => (
              <div
                key={i}
                style={{
                  padding: "8px 10px", borderRadius: 8,
                  background: "var(--bg-secondary)",
                  borderLeft: `3px solid ${SEVERITY_COLORS[f.severity] || "var(--border)"}`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                  <span style={{
                    fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 4,
                    background: `${SEVERITY_COLORS[f.severity]}20`,
                    color: SEVERITY_COLORS[f.severity],
                    textTransform: "uppercase",
                  }}>
                    {f.severity}
                  </span>
                  <span style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase" }}>
                    {f.category}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "var(--text-primary)", marginBottom: 2 }}>
                  {f.message}
                </div>
                <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "monospace" }}>
                  {f.file}{f.line > 0 ? `:${f.line}` : ""}
                </div>
                {f.snippet && (
                  <div style={{
                    fontSize: 10, fontFamily: "monospace", color: "var(--text-secondary)",
                    marginTop: 4, padding: "4px 6px", borderRadius: 4,
                    background: "var(--bg-primary)", overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {f.snippet}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {expanded && findings.length === 0 && (
        <div style={{ marginTop: 10, fontSize: 11, color: "var(--success)", textAlign: "center" }}>
          All clear — no security issues detected
        </div>
      )}
    </div>
  );
}
