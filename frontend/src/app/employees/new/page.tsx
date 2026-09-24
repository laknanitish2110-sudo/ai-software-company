"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { createEmployee } from "@/lib/api";

const ROLE_PRESETS = [
  { role: "Software Engineer", persona: "You write clean, well-tested code. You follow best practices, consider edge cases, and explain your technical decisions clearly.", icon: "\u{1f4bb}" },
  { role: "Product Manager", persona: "You define product requirements, prioritize features based on user impact, and create clear specifications. You think in terms of user stories and outcomes.", icon: "\u{1f4cb}" },
  { role: "Designer", persona: "You create intuitive user interfaces and experiences. You think about accessibility, consistency, and visual hierarchy.", icon: "\u{1f3a8}" },
  { role: "Data Analyst", persona: "You analyze data to find insights, create visualizations, and make data-driven recommendations. You're rigorous about methodology.", icon: "\u{1f4ca}" },
  { role: "DevOps Engineer", persona: "You manage infrastructure, CI/CD pipelines, and deployment processes. You optimize for reliability, security, and performance.", icon: "\u{2699}\u{fe0f}" },
  { role: "Technical Writer", persona: "You create clear, comprehensive documentation. You explain complex concepts simply and organize information logically.", icon: "\u{1f4dd}" },
];

export default function NewEmployeePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [persona, setPersona] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-base)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ width: 32, height: 32, border: "3px solid rgba(99,91,255,0.2)", borderTopColor: "#635bff", borderRadius: "50%", animation: "spin 0.6s linear infinite" }} />
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !role.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const emp = await createEmployee({
        name: name.trim(),
        role: role.trim(),
        persona: persona.trim() || undefined,
      });
      router.push(`/employees/${emp.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create employee");
      setSubmitting(false);
    }
  }

  function applyPreset(preset: typeof ROLE_PRESETS[number]) {
    setRole(preset.role);
    setPersona(preset.persona);
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <div style={{ maxWidth: 640, margin: "0 auto", padding: "48px 24px" }}>
        <div className="flex items-center gap-3" style={{ marginBottom: 32 }}>
          <Link href="/employees" style={{ color: "var(--text-muted)", fontSize: 13, textDecoration: "none" }}>
            Team
          </Link>
          <span style={{ color: "var(--text-muted)", fontSize: 13 }}>/</span>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
            Hire Employee
          </h1>
        </div>

        <div style={{ marginBottom: 28 }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 10 }}>
            Quick start from a role
          </label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 8 }}>
            {ROLE_PRESETS.map((preset) => (
              <button
                key={preset.role}
                type="button"
                onClick={() => applyPreset(preset)}
                style={{
                  padding: "10px 14px", borderRadius: 10, border: "1px solid var(--border)",
                  background: role === preset.role ? "var(--accent-bg)" : "var(--bg-card)",
                  borderColor: role === preset.role ? "var(--accent-border)" : "var(--border)",
                  cursor: "pointer", textAlign: "left", transition: "border-color 0.15s",
                }}
              >
                <span style={{ fontSize: 18 }}>{preset.icon}</span>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginTop: 4 }}>
                  {preset.role}
                </div>
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ background: "var(--bg-card)", borderRadius: 14, border: "1px solid var(--border)", padding: 24 }}>
            <div style={{ marginBottom: 20 }}>
              <label htmlFor="emp-name" style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                Name *
              </label>
              <input
                id="emp-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Alex"
                required
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 10,
                  border: "1px solid var(--border)", background: "var(--bg-base)",
                  color: "var(--text-primary)", fontSize: 14, outline: "none",
                  transition: "border-color 0.15s",
                }}
                onFocus={(e) => e.target.style.borderColor = "var(--accent)"}
                onBlur={(e) => e.target.style.borderColor = "var(--border)"}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label htmlFor="emp-role" style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                Role *
              </label>
              <input
                id="emp-role"
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. Software Engineer"
                required
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 10,
                  border: "1px solid var(--border)", background: "var(--bg-base)",
                  color: "var(--text-primary)", fontSize: 14, outline: "none",
                  transition: "border-color 0.15s",
                }}
                onFocus={(e) => e.target.style.borderColor = "var(--accent)"}
                onBlur={(e) => e.target.style.borderColor = "var(--border)"}
              />
            </div>

            <div style={{ marginBottom: 4 }}>
              <label htmlFor="emp-persona" style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                Persona (system prompt)
              </label>
              <textarea
                id="emp-persona"
                value={persona}
                onChange={(e) => setPersona(e.target.value)}
                placeholder="Describe this employee's personality, expertise, and how they should behave..."
                rows={4}
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 10,
                  border: "1px solid var(--border)", background: "var(--bg-base)",
                  color: "var(--text-primary)", fontSize: 14, outline: "none",
                  resize: "vertical", fontFamily: "inherit",
                  transition: "border-color 0.15s",
                }}
                onFocus={(e) => e.target.style.borderColor = "var(--accent)"}
                onBlur={(e) => e.target.style.borderColor = "var(--border)"}
              />
              <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
                This becomes part of the employee&apos;s system prompt. The more specific you are, the better they perform.
              </p>
            </div>
          </div>

          {error && (
            <div style={{ marginTop: 16, padding: "12px 16px", borderRadius: 10, background: "rgba(237,95,116,0.08)", border: "1px solid rgba(237,95,116,0.2)", color: "#ed5f74", fontSize: 13 }}>
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-3" style={{ marginTop: 20 }}>
            <Link
              href="/employees"
              style={{
                padding: "10px 20px", borderRadius: 10, fontSize: 14,
                color: "var(--text-secondary)", textDecoration: "none",
                border: "1px solid var(--border)", background: "var(--bg-card)",
              }}
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting || !name.trim() || !role.trim()}
              style={{
                padding: "10px 24px", borderRadius: 10, fontSize: 14, fontWeight: 600,
                color: "#fff", background: "var(--accent)", border: "none", cursor: "pointer",
                opacity: submitting || !name.trim() || !role.trim() ? 0.5 : 1,
                transition: "opacity 0.15s",
              }}
            >
              {submitting ? "Creating..." : "Hire Employee"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
