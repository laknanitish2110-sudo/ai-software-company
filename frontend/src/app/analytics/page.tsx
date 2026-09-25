"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { getAnalytics, type AnalyticsData } from "@/lib/api";

const ROLE_COLORS: Record<string, string> = {
  "Architect": "#8b5cf6",
  "Business Analyst": "#0bbf8c",
  "Researcher": "#3b82f6",
  "Software Engineer": "#f59e0b",
  "QA Engineer": "#ef4444",
  "Technical Writer": "#06b6d4",
};

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{
      padding: "20px 24px", borderRadius: 14,
      background: "var(--bg-card)", border: "1px solid var(--border)",
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: color || "var(--text-primary)", letterSpacing: "-0.02em" }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      {sub && <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function BarChart({ data, maxVal }: { data: { label: string; value: number; color: string }[]; maxVal: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {data.map((d) => (
        <div key={d.label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 100, fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", textAlign: "right", flexShrink: 0 }}>
            {d.label}
          </div>
          <div style={{ flex: 1, height: 24, borderRadius: 6, background: "var(--bg-elevated)", overflow: "hidden" }}>
            <div style={{
              width: `${maxVal > 0 ? (d.value / maxVal) * 100 : 0}%`,
              height: "100%", borderRadius: 6,
              background: d.color,
              transition: "width 0.6s ease-out",
              minWidth: d.value > 0 ? 4 : 0,
            }} />
          </div>
          <div style={{ width: 48, fontSize: 12, fontWeight: 700, color: "var(--text-primary)", textAlign: "right", flexShrink: 0 }}>
            {d.value.toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(30);

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    getAnalytics(period)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user, period]);

  if (authLoading || !user) return null;

  if (loading || !data) {
    return (
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "48px 24px" }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", marginBottom: 24 }}>Analytics</h1>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton-card" style={{ height: 100 }} />
          ))}
        </div>
      </div>
    );
  }

  const totalSessions = data.employees.reduce((s, e) => s + e.session_count, 0);
  const totalMemories = data.employees.reduce((s, e) => s + e.memory_count, 0);
  const totalSkills = data.employees.reduce((s, e) => s + e.skill_count, 0);
  const maxSessions = Math.max(...data.employees.map((e) => e.session_count), 1);
  const maxMemories = Math.max(...data.employees.map((e) => e.memory_count), 1);

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "48px 24px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 4px" }}>Analytics</h1>
          <p style={{ fontSize: 14, color: "var(--text-secondary)", margin: 0 }}>
            Team activity and usage insights
          </p>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              style={{
                padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                background: period === d ? "var(--accent-bg)" : "transparent",
                color: period === d ? "var(--accent)" : "var(--text-muted)",
                border: `1px solid ${period === d ? "var(--accent-border)" : "var(--border)"}`,
                cursor: "pointer",
              }}
            >{d}d</button>
          ))}
        </div>
      </div>

      {/* Top stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14, marginBottom: 32 }}>
        <StatCard label="Total Tokens" value={data.usage.total_tokens} color="var(--accent)" />
        <StatCard label="Sessions" value={totalSessions} color="#3b82f6" />
        <StatCard label="Memories" value={totalMemories} color="#8b5cf6" />
        <StatCard label="Skills Learned" value={totalSkills} color="var(--success)" />
      </div>

      {/* Token usage */}
      <div style={{
        padding: 24, borderRadius: 16, marginBottom: 24,
        background: "var(--bg-card)", border: "1px solid var(--border)",
      }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", marginBottom: 16 }}>Token Usage</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>Input Tokens</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "var(--accent)" }}>{data.usage.total_input.toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>Output Tokens</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: "var(--success)" }}>{data.usage.total_output.toLocaleString()}</div>
          </div>
        </div>
        {data.usage.by_type && data.usage.by_type.length > 0 && (
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              By Type
            </div>
            <BarChart
              data={data.usage.by_type.map((t) => ({
                label: t.record_type.replace(/_/g, " "),
                value: (t.total_input || 0) + (t.total_output || 0),
                color: "var(--accent)",
              }))}
              maxVal={Math.max(...data.usage.by_type.map((t) => (t.total_input || 0) + (t.total_output || 0)), 1)}
            />
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
        {/* Sessions per employee */}
        <div style={{
          padding: 24, borderRadius: 16,
          background: "var(--bg-card)", border: "1px solid var(--border)",
        }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", marginBottom: 16 }}>Sessions per Employee</h3>
          <BarChart
            data={data.employees.map((e) => ({
              label: e.name,
              value: e.session_count,
              color: ROLE_COLORS[e.role] || "var(--accent)",
            }))}
            maxVal={maxSessions}
          />
        </div>

        {/* Memories per employee */}
        <div style={{
          padding: 24, borderRadius: 16,
          background: "var(--bg-card)", border: "1px solid var(--border)",
        }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", marginBottom: 16 }}>Memories per Employee</h3>
          <BarChart
            data={data.employees.map((e) => ({
              label: e.name,
              value: e.memory_count,
              color: ROLE_COLORS[e.role] || "#8b5cf6",
            }))}
            maxVal={maxMemories}
          />
        </div>
      </div>

      {/* Activity breakdown */}
      <div style={{
        padding: 24, borderRadius: 16, marginBottom: 24,
        background: "var(--bg-card)", border: "1px solid var(--border)",
      }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", marginBottom: 16 }}>Activity Summary</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
          {Object.entries(data.activity_summary).map(([type, count]) => {
            const labels: Record<string, { label: string; color: string }> = {
              delegation_completed: { label: "Delegations", color: "var(--success)" },
              session_completed: { label: "Sessions", color: "var(--accent)" },
              skill_learned: { label: "Skills Learned", color: "var(--warning)" },
              memory_created: { label: "Memories", color: "#8b5cf6" },
            };
            const cfg = labels[type] || { label: type.replace(/_/g, " "), color: "var(--text-muted)" };
            return (
              <div key={type} style={{
                padding: "14px 16px", borderRadius: 10,
                background: "var(--bg-elevated)", border: "1px solid var(--border)",
                textAlign: "center",
              }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: cfg.color }}>{count}</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2, textTransform: "capitalize" }}>
                  {cfg.label}
                </div>
              </div>
            );
          })}
          {Object.keys(data.activity_summary).length === 0 && (
            <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: 20, color: "var(--text-muted)", fontSize: 13 }}>
              No activity recorded yet
            </div>
          )}
        </div>
      </div>

      {/* Employee table */}
      <div style={{
        padding: 24, borderRadius: 16,
        background: "var(--bg-card)", border: "1px solid var(--border)",
      }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", marginBottom: 16 }}>Employee Overview</h3>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Employee", "Role", "Sessions", "Memories", "Skills", "Status"].map((h) => (
                <th key={h} style={{
                  textAlign: "left", padding: "8px 12px",
                  fontSize: 11, fontWeight: 700, color: "var(--text-muted)",
                  textTransform: "uppercase", letterSpacing: "0.05em",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.employees.map((emp) => (
              <tr key={emp.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "10px 12px", fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                  {emp.name}
                </td>
                <td style={{ padding: "10px 12px", fontSize: 12, color: ROLE_COLORS[emp.role] || "var(--text-secondary)" }}>
                  {emp.role}
                </td>
                <td style={{ padding: "10px 12px", fontSize: 13, color: "var(--text-secondary)" }}>
                  {emp.session_count}
                </td>
                <td style={{ padding: "10px 12px", fontSize: 13, color: "var(--text-secondary)" }}>
                  {emp.memory_count}
                </td>
                <td style={{ padding: "10px 12px", fontSize: 13, color: "var(--text-secondary)" }}>
                  {emp.skill_count}
                </td>
                <td style={{ padding: "10px 12px" }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
                    background: emp.status === "idle" ? "rgba(11,191,140,0.1)" : "var(--accent-bg)",
                    color: emp.status === "idle" ? "var(--success)" : "var(--accent)",
                    textTransform: "uppercase",
                  }}>{emp.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
