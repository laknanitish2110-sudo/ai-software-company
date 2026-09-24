"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { listEmployees, type Employee } from "@/lib/api";
import { ThinkingOrb, type OrbState } from "thinking-orbs";

const ROLE_META: Record<string, { icon: string; color: string; accent: string }> = {
  "Business Analyst": { icon: "📋", color: "#0bbf8c", accent: "rgba(11,191,140,0.08)" },
  "Researcher":       { icon: "🔍", color: "#3b82f6", accent: "rgba(59,130,246,0.08)" },
  "Architect":        { icon: "🏗️", color: "#8b5cf6", accent: "rgba(139,92,246,0.08)" },
  "Software Engineer":{ icon: "⚡", color: "#f59e0b", accent: "rgba(245,158,11,0.08)" },
  "QA Engineer":      { icon: "🛡️", color: "#ef4444", accent: "rgba(239,68,68,0.08)" },
  "Technical Writer": { icon: "✍️", color: "#06b6d4", accent: "rgba(6,182,212,0.08)" },
};

const STATUS_CONFIG: Record<string, { label: string; orbState: OrbState; color: string }> = {
  idle:           { label: "Ready",          orbState: "breathing", color: "#0bbf8c" },
  thinking:       { label: "Thinking...",    orbState: "solving",   color: "#635bff" },
  tool_execution: { label: "Executing...",   orbState: "working",   color: "#f59e0b" },
  working:        { label: "Working...",     orbState: "working",   color: "#635bff" },
  blocked:        { label: "Needs input",    orbState: "listening", color: "#f5a623" },
  paused:         { label: "Paused",         orbState: "breathing", color: "#8898aa" },
  archived:       { label: "Archived",       orbState: "breathing", color: "#8898aa" },
};

function getRoleMeta(role: string) {
  return ROLE_META[role] || { icon: "🤖", color: "#635bff", accent: "rgba(99,91,255,0.08)" };
}

function getStatus(status: string) {
  return STATUS_CONFIG[status] || STATUS_CONFIG.idle;
}

function EmployeeCard({ emp }: { emp: Employee }) {
  const role = getRoleMeta(emp.role);
  const st = getStatus(emp.status);
  const isActive = emp.status === "thinking" || emp.status === "tool_execution" || emp.status === "working";

  return (
    <Link
      href={`/employees/${emp.id}`}
      style={{ display: "block", textDecoration: "none" }}
    >
      <div
        style={{
          padding: 0, borderRadius: 16,
          background: "var(--bg-card)",
          border: `1px solid ${isActive ? "var(--accent-border)" : "var(--border)"}`,
          transition: "all 0.2s ease",
          overflow: "hidden",
          boxShadow: isActive ? "0 0 20px rgba(99,91,255,0.08)" : "none",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = role.color;
          e.currentTarget.style.boxShadow = `0 4px 20px ${role.color}15`;
          e.currentTarget.style.transform = "translateY(-2px)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = isActive ? "var(--accent-border)" : "var(--border)";
          e.currentTarget.style.boxShadow = isActive ? "0 0 20px rgba(99,91,255,0.08)" : "none";
          e.currentTarget.style.transform = "translateY(0)";
        }}
      >
        {/* Top accent bar */}
        <div style={{ height: 3, background: `linear-gradient(90deg, ${role.color}, ${role.color}66)` }} />

        <div style={{ padding: "20px 20px 16px" }}>
          {/* Header row: orb + name + status */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ position: "relative", flexShrink: 0 }}>
              {isActive ? (
                <ThinkingOrb state={st.orbState} size={32} theme="auto" />
              ) : (
                <div style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: role.accent,
                  border: `1.5px solid ${role.color}30`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 16,
                }}>
                  {role.icon}
                </div>
              )}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{
                  fontSize: 17, fontWeight: 700, color: "var(--text-primary)",
                  letterSpacing: "-0.01em",
                }}>
                  {emp.name}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
                  background: `${st.color}15`, color: st.color,
                  textTransform: "uppercase", letterSpacing: "0.05em",
                }}>
                  {st.label}
                </span>
              </div>
              <div style={{ fontSize: 13, color: role.color, fontWeight: 500, marginTop: 2 }}>
                {emp.role}
              </div>
            </div>
          </div>

          {/* Description */}
          {emp.persona && (
            <p style={{
              fontSize: 13, color: "var(--text-muted)", marginTop: 14,
              lineHeight: 1.6, overflow: "hidden", textOverflow: "ellipsis",
              display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
            }}>
              {emp.persona.length > 120
                ? emp.persona.substring(0, emp.persona.indexOf("\n\n") > 0 ? emp.persona.indexOf("\n\n") : 120)
                : emp.persona}
            </p>
          )}

          {/* Footer */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            marginTop: 14, paddingTop: 12,
            borderTop: "1px solid var(--border)",
            fontSize: 12, color: "var(--text-muted)",
          }}>
            <span>Since {new Date(emp.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 4,
              color: "var(--accent)", fontWeight: 500,
            }}>
              Chat →
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function EmployeesPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { router.push("/login"); return; }
    listEmployees()
      .then(setEmployees)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [user, authLoading, router]);

  if (authLoading || !user) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-base)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <ThinkingOrb state="connecting" size={64} theme="auto" />
      </div>
    );
  }

  const teamCount = employees.length;
  const activeCount = employees.filter(e => e.status === "thinking" || e.status === "working" || e.status === "tool_execution").length;

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "48px 24px" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 36 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <Link href="/" style={{ color: "var(--text-muted)", fontSize: 13, textDecoration: "none" }}>
                Home
              </Link>
              <span style={{ color: "var(--text-muted)", fontSize: 13 }}>/</span>
              <h1 style={{ fontSize: 26, fontWeight: 800, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.02em" }}>
                Your Team
              </h1>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: 14, margin: 0 }}>
              {teamCount > 0
                ? `${teamCount} AI employees${activeCount > 0 ? ` · ${activeCount} active now` : ""}`
                : "Your persistent AI employees"}
            </p>
          </div>
          <Link
            href="/employees/new"
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "10px 20px", borderRadius: 10,
              background: "var(--accent)", color: "#fff",
              fontSize: 14, fontWeight: 600, textDecoration: "none",
              transition: "opacity 0.15s",
            }}
          >
            + Hire Employee
          </Link>
        </div>

        {loading && (
          <div style={{ textAlign: "center", padding: 80 }}>
            <ThinkingOrb state="searching" size={64} theme="auto" />
            <p style={{ color: "var(--text-muted)", fontSize: 14, marginTop: 16 }}>Loading your team...</p>
          </div>
        )}

        {error && (
          <div style={{ padding: "16px 20px", borderRadius: 10, background: "rgba(237,95,116,0.08)", border: "1px solid rgba(237,95,116,0.2)", color: "#ed5f74", fontSize: 14 }}>
            {error}
          </div>
        )}

        {!loading && !error && employees.length === 0 && (
          <div style={{
            textAlign: "center", padding: "80px 24px",
            borderRadius: 16, border: "2px dashed var(--border)",
            background: "var(--bg-card)",
          }}>
            <ThinkingOrb state="listening" size={64} theme="auto" />
            <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)", marginTop: 20, marginBottom: 8 }}>
              No employees yet
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: 14, marginBottom: 24, maxWidth: 400, margin: "0 auto 24px" }}>
              Hire your first AI employee. They persist across sessions, learn from conversations, and build up skills over time.
            </p>
            <Link
              href="/employees/new"
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                padding: "10px 20px", borderRadius: 10,
                background: "var(--accent)", color: "#fff",
                fontSize: 14, fontWeight: 600, textDecoration: "none",
              }}
            >
              + Hire Your First Employee
            </Link>
          </div>
        )}

        {!loading && employees.length > 0 && (
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))",
            gap: 18,
          }}>
            {employees.map((emp) => (
              <EmployeeCard key={emp.id} emp={emp} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
