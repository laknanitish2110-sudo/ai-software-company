"use client";

import { useState, useEffect } from "react";
import { getEmployeeExperience, type ExperienceData, type CompiledProcedure } from "@/lib/api";

const LEVEL_CONFIG: Record<string, { color: string; label: string; pct: number }> = {
  novice: { color: "var(--text-muted)", label: "Novice", pct: 10 },
  learning: { color: "var(--info)", label: "Learning", pct: 30 },
  competent: { color: "var(--brand)", label: "Competent", pct: 50 },
  proficient: { color: "var(--warning)", label: "Proficient", pct: 75 },
  expert: { color: "var(--success)", label: "Expert", pct: 95 },
};

const PROC_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  success_pattern: { label: "Success Pattern", color: "var(--success)" },
  failure_avoidance: { label: "Failure Avoidance", color: "var(--danger)" },
  optimization: { label: "Optimization", color: "var(--info)" },
  pre_check: { label: "Pre-Check", color: "var(--warning)" },
};

function IntelligenceMeter({ level }: { level: string }) {
  const config = LEVEL_CONFIG[level] || LEVEL_CONFIG.novice;
  return (
    <div style={{ marginBottom: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
        <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)" }}>
          Intelligence Level
        </span>
        <span style={{
          fontSize: "10px",
          padding: "2px 8px",
          borderRadius: "3px",
          background: config.color,
          color: "#fff",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.5px",
        }}>
          {config.label}
        </span>
      </div>
      <div style={{
        height: "6px",
        borderRadius: "3px",
        background: "var(--surface-raised)",
        overflow: "hidden",
      }}>
        <div style={{
          height: "100%",
          width: `${config.pct}%`,
          borderRadius: "3px",
          background: config.color,
          transition: "width 0.6s ease",
        }} />
      </div>
    </div>
  );
}

function PatternBreakdown({ data }: { data: ExperienceData }) {
  const stats = [
    { label: "Patterns", value: data.patterns.total },
    { label: "Successes", value: data.patterns.successes, color: "var(--success)" },
    { label: "Failures", value: data.patterns.failures, color: "var(--danger)" },
    { label: "Procedures", value: data.procedures.active, color: "var(--brand)" },
    { label: "Applied", value: data.procedures.total_applications },
    { label: "Worked", value: data.procedures.total_successes, color: "var(--success)" },
  ];
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(3, 1fr)",
      gap: "8px",
      marginBottom: "16px",
    }}>
      {stats.map(s => (
        <div key={s.label} style={{
          padding: "8px",
          borderRadius: "6px",
          background: "var(--surface-raised)",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "16px", fontWeight: 700, color: s.color || "var(--text)" }}>
            {s.value}
          </div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>{s.label}</div>
        </div>
      ))}
    </div>
  );
}

function ProcedureCard({ proc }: { proc: CompiledProcedure }) {
  const [expanded, setExpanded] = useState(false);
  const typeConfig = PROC_TYPE_LABELS[proc.type] || { label: proc.type, color: "var(--text-muted)" };
  const confidencePct = Math.round(proc.confidence * 100);
  const steps = proc.steps as Record<string, string | number | string[] | undefined> | null;

  return (
    <div
      style={{
        padding: "10px",
        borderRadius: "6px",
        background: "var(--surface-raised)",
        marginBottom: "8px",
        cursor: "pointer",
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
        <span style={{
          fontSize: "9px",
          padding: "1px 5px",
          borderRadius: "3px",
          background: typeConfig.color,
          color: "#fff",
          fontWeight: 600,
          textTransform: "uppercase",
        }}>
          {typeConfig.label}
        </span>
        <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)", flex: 1, minWidth: 0 }}>
          {confidencePct}% confidence
        </span>
        {proc.times_applied > 0 && (
          <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
            {proc.times_succeeded}/{proc.times_applied} applied
          </span>
        )}
      </div>
      {expanded && steps && (
        <div style={{
          marginTop: "8px",
          padding: "8px",
          borderRadius: "4px",
          background: "var(--surface)",
          fontSize: "11px",
        }}>
          {steps.description && (
            <div style={{ marginBottom: "4px", color: "var(--text)" }}>
              {String(steps.description)}
            </div>
          )}
          {steps.recommendation && (
            <div style={{ color: "var(--text-muted)" }}>
              Recommendation: {String(steps.recommendation).replace(/_/g, " ")}
            </div>
          )}
          {steps.sequence && Array.isArray(steps.sequence) && (
            <div style={{ marginTop: "4px", color: "var(--text-muted)" }}>
              Sequence: {(steps.sequence as string[]).join(" → ")}
            </div>
          )}
          {steps.failure_type && (
            <div style={{ marginTop: "4px", color: "var(--danger)" }}>
              Failure type: {String(steps.failure_type)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ExperienceCompilerPanel({ employeeId }: { employeeId: string }) {
  const [data, setData] = useState<ExperienceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await getEmployeeExperience(employeeId);
        setData(res);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [employeeId]);

  if (loading) {
    return (
      <div style={{ padding: "16px", color: "var(--text-muted)", fontSize: "12px" }}>
        Loading experience data...
      </div>
    );
  }

  if (!data || (data.patterns.total === 0 && data.procedures.total === 0)) return null;

  return (
    <div style={{
      padding: "16px",
      borderRadius: "8px",
      background: "var(--surface)",
      border: "1px solid var(--border)",
      marginTop: "12px",
    }}>
      <h3 style={{
        margin: "0 0 12px",
        fontSize: "14px",
        fontWeight: 700,
        color: "var(--text)",
        display: "flex",
        alignItems: "center",
        gap: "6px",
      }}>
        <span style={{ fontSize: "16px" }}>&#x1f9e0;</span>
        Experience Compiler
      </h3>

      <IntelligenceMeter level={data.intelligence_level} />
      <PatternBreakdown data={data} />

      {data.procedures.avg_confidence > 0 && (
        <div style={{
          marginBottom: "12px",
          padding: "8px",
          borderRadius: "6px",
          background: "var(--surface-raised)",
          fontSize: "11px",
          color: "var(--text-muted)",
          display: "flex",
          justifyContent: "space-between",
        }}>
          <span>Avg Confidence: {Math.round(data.procedures.avg_confidence * 100)}%</span>
          <span>Avg Success: {Math.round(data.procedures.avg_success_rate * 100)}%</span>
          <span>Executions Analyzed: {data.patterns.executions_analyzed}</span>
        </div>
      )}

      {data.compiled_procedures.length > 0 && (
        <>
          <div style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-muted)",
            marginBottom: "8px",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}>
            Compiled Procedures
          </div>
          {data.compiled_procedures.map(proc => (
            <ProcedureCard key={proc.id} proc={proc} />
          ))}
        </>
      )}
    </div>
  );
}
