"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { listEmployees, provisionTeam, seedDefaultSkills, type Employee } from "@/lib/api";
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

          {/* Stats + Footer */}
          <div style={{
            display: "flex", alignItems: "center", gap: 12,
            marginTop: 14, paddingTop: 12,
            borderTop: "1px solid var(--border)",
            fontSize: 12, color: "var(--text-muted)",
          }}>
            <span title="Sessions">{emp.session_count ?? 0} sessions</span>
            <span style={{ color: "var(--border)" }}>|</span>
            <span title="Memories">{emp.memory_count ?? 0} memories</span>
            <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4, color: "var(--accent)", fontWeight: 500 }}>
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
  const [provisioning, setProvisioning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const provisionAttempted = useRef(false);
  const skillSeedAttempted = useRef(false);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { router.push("/login"); return; }

    let active = true;
    const fetchEmployees = () =>
      listEmployees()
        .then(async (data) => {
          if (!active) return;
          if (data.length === 0 && !provisionAttempted.current) {
            provisionAttempted.current = true;
            setProvisioning(true);
            try {
              const result = await provisionTeam();
              if (result.provisioned > 0) {
                const refreshed = await listEmployees();
                if (active) setEmployees(refreshed);
              }
            } catch {
              // provisioning failed — show empty state
            } finally {
              if (active) setProvisioning(false);
            }
          } else {
            setEmployees(data);
            if (!skillSeedAttempted.current && data.length > 0) {
              skillSeedAttempted.current = true;
              seedDefaultSkills().catch(() => {});
            }
          }
        })
        .catch((e) => { if (active) setError(e.message); })
        .finally(() => { if (active) setLoading(false); });

    fetchEmployees();
    const interval = setInterval(() => {
      if (!provisionAttempted.current || employees.length > 0) {
        listEmployees()
          .then((data) => { if (active) setEmployees(data); })
          .catch(() => {});
      }
    }, 3000);
    return () => { active = false; clearInterval(interval); };
  }, [user, authLoading, router]);

  async function handleProvision() {
    setProvisioning(true);
    setError(null);
    try {
      await provisionTeam();
      const data = await listEmployees();
      setEmployees(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to provision team");
    } finally {
      setProvisioning(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-base)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <ThinkingOrb state="connecting" size={64} theme="auto" />
      </div>
    );
  }

  const teamCount = employees.length;
  const activeCount = employees.filter(e => e.status === "thinking" || e.status === "working" || e.status === "tool_execution").length;
  const totalSessions = employees.reduce((sum, e) => sum + (e.session_count ?? 0), 0);
  const totalMemories = employees.reduce((sum, e) => sum + (e.memory_count ?? 0), 0);

  const STATS = [
    { label: "Employees", value: teamCount, color: "var(--accent)" },
    { label: "Active Now", value: activeCount, color: "#0bbf8c" },
    { label: "Sessions", value: totalSessions, color: "#3b82f6" },
    { label: "Memories", value: totalMemories, color: "#8b5cf6" },
  ];

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "48px 24px" }}>
        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: "var(--text-primary)", margin: "0 0 4px", letterSpacing: "-0.02em" }}>
            Your Team
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: 14, margin: 0 }}>
            {teamCount > 0
              ? `${teamCount} AI employees that learn, remember, and grow`
              : "Your persistent AI employees"}
          </p>
        </div>

        {/* Stats bar */}
        {teamCount > 0 && (
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12,
            marginBottom: 28,
          }}>
            {STATS.map((s) => (
              <div key={s.label} style={{
                padding: "14px 16px", borderRadius: 12,
                background: "var(--bg-card)", border: "1px solid var(--border)",
              }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: s.color, letterSpacing: "-0.02em" }}>
                  {s.value}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 500, marginTop: 2 }}>
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        )}

        {(loading || provisioning) && (
          <div>
            {provisioning ? (
              <div style={{ textAlign: "center", padding: 80 }}>
                <ThinkingOrb state="working" size={64} theme="auto" />
                <p style={{ color: "var(--text-muted)", fontSize: 14, marginTop: 16 }}>
                  Setting up your AI team...
                </p>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
                {[0, 1, 2, 3, 4, 5].map((i) => (
                  <div key={i} style={{
                    borderRadius: 16, overflow: "hidden",
                    background: "var(--bg-card)", border: "1px solid var(--border)",
                    animation: `fadeIn 0.3s ease-out ${i * 0.05}s both`,
                  }}>
                    <div className="skeleton" style={{ height: 3, borderRadius: 0 }} />
                    <div style={{ padding: "20px 20px 16px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
                        <div className="skeleton skeleton-circle" style={{ width: 32, height: 32 }} />
                        <div style={{ flex: 1 }}>
                          <div className="skeleton skeleton-text" style={{ width: "60%", marginBottom: 6 }} />
                          <div className="skeleton skeleton-text-sm" style={{ width: "40%" }} />
                        </div>
                      </div>
                      <div className="skeleton skeleton-text" style={{ width: "90%" }} />
                      <div className="skeleton skeleton-text" style={{ width: "70%" }} />
                      <div style={{ borderTop: "1px solid var(--border)", marginTop: 14, paddingTop: 12 }}>
                        <div className="skeleton skeleton-text-sm" style={{ width: "50%" }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {error && (
          <div style={{
            padding: "16px 20px", borderRadius: 14, marginBottom: 16,
            background: "rgba(237,95,116,0.06)", border: "1px solid rgba(237,95,116,0.15)",
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10, flexShrink: 0,
              background: "rgba(237,95,116,0.1)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ed5f74" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#ed5f74", marginBottom: 2 }}>Connection Error</div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{error}</div>
            </div>
          </div>
        )}

        {!loading && !provisioning && !error && employees.length === 0 && (
          <div style={{
            textAlign: "center", padding: "80px 24px",
            borderRadius: 16, border: "1px solid var(--border)",
            background: "var(--bg-card)",
          }}>
            <div style={{
              width: 64, height: 64, borderRadius: 20, margin: "0 auto 20px",
              background: "var(--accent-bg)", border: "1px solid var(--accent-border)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 28,
            }}>
              🤖
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)", marginBottom: 8 }}>
              Your team isn&apos;t set up yet
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: 14, marginBottom: 24, maxWidth: 420, margin: "0 auto 24px", lineHeight: 1.6 }}>
              Provision your 6 AI employees — an Architect, Business Analyst, Researcher, Engineer, QA Engineer, and Technical Writer. They persist across sessions and learn from every conversation.
            </p>
            <button
              onClick={handleProvision}
              disabled={provisioning}
              style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                padding: "12px 28px", borderRadius: 10, border: "none",
                background: "var(--accent)", color: "#fff",
                fontSize: 15, fontWeight: 600, cursor: "pointer",
                boxShadow: "0 2px 12px rgba(99,91,255,0.3)",
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => e.currentTarget.style.transform = "translateY(-1px)"}
              onMouseLeave={(e) => e.currentTarget.style.transform = "translateY(0)"}
            >
              Set Up Your AI Team
            </button>
          </div>
        )}

        {!loading && !provisioning && employees.length > 0 && (
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
