"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { listEmployees, type Employee } from "@/lib/api";

const STATUS_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  idle: { bg: "rgba(11,191,140,0.1)", text: "#0bbf8c", label: "Idle" },
  working: { bg: "rgba(99,91,255,0.1)", text: "#635bff", label: "Working" },
  blocked: { bg: "rgba(245,166,35,0.1)", text: "#f5a623", label: "Blocked" },
  paused: { bg: "rgba(136,152,170,0.1)", text: "#8898aa", label: "Paused" },
  archived: { bg: "rgba(237,95,116,0.1)", text: "#ed5f74", label: "Archived" },
};

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
        <div style={{ width: 32, height: 32, border: "3px solid rgba(99,91,255,0.2)", borderTopColor: "#635bff", borderRadius: "50%", animation: "spin 0.6s linear infinite" }} />
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 24px" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 32 }}>
          <div>
            <div className="flex items-center gap-3">
              <Link href="/" style={{ color: "var(--text-muted)", fontSize: 13, textDecoration: "none" }}>
                Home
              </Link>
              <span style={{ color: "var(--text-muted)", fontSize: 13 }}>/</span>
              <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                Team
              </h1>
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: 14, marginTop: 4 }}>
              Your persistent AI employees
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
          <div style={{ textAlign: "center", padding: 60 }}>
            <div style={{ width: 28, height: 28, border: "3px solid rgba(99,91,255,0.2)", borderTopColor: "#635bff", borderRadius: "50%", animation: "spin 0.6s linear infinite", margin: "0 auto" }} />
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
            <div style={{ fontSize: 48, marginBottom: 16 }}>&#x1f465;</div>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 }}>
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
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
            {employees.map((emp) => {
              const st = STATUS_COLORS[emp.status] || STATUS_COLORS.idle;
              return (
                <Link
                  key={emp.id}
                  href={`/employees/${emp.id}`}
                  style={{
                    display: "block", textDecoration: "none",
                    padding: 20, borderRadius: 14,
                    background: "var(--bg-card)", border: "1px solid var(--border)",
                    transition: "border-color 0.15s, box-shadow 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "var(--accent-border)";
                    e.currentTarget.style.boxShadow = "0 2px 12px rgba(99,91,255,0.08)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--border)";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div style={{
                      width: 44, height: 44, borderRadius: 12,
                      background: "var(--accent-bg)", border: "1px solid var(--accent-border)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 20, flexShrink: 0,
                    }}>
                      {emp.avatar_url ? (
                        <img src={emp.avatar_url} alt="" style={{ width: 44, height: 44, borderRadius: 12 }} />
                      ) : (
                        emp.name.charAt(0).toUpperCase()
                      )}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="flex items-center gap-2">
                        <span style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)" }}>
                          {emp.name}
                        </span>
                        <span style={{
                          fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 6,
                          background: st.bg, color: st.text,
                        }}>
                          {st.label}
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 2 }}>
                        {emp.role}
                      </div>
                    </div>
                  </div>
                  {emp.persona && (
                    <p style={{
                      fontSize: 13, color: "var(--text-muted)", marginTop: 12,
                      lineHeight: 1.5, overflow: "hidden", textOverflow: "ellipsis",
                      display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
                    }}>
                      {emp.persona}
                    </p>
                  )}
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 12 }}>
                    Created {new Date(emp.created_at).toLocaleDateString()}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
