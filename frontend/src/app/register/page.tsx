"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/Toast";
import SocialLoginButtons from "@/components/SocialLoginButtons";

const PASSWORD_RULES = [
  { test: (p: string) => p.length >= 8, label: "8+ characters" },
  { test: (p: string) => /[A-Z]/.test(p), label: "Uppercase letter" },
  { test: (p: string) => /[a-z]/.test(p), label: "Lowercase letter" },
  { test: (p: string) => /\d/.test(p), label: "Number" },
  { test: (p: string) => /[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;'/`~]/.test(p), label: "Special character" },
];

function getStrength(password: string): { score: number; label: string; color: string } {
  if (!password) return { score: 0, label: "", color: "transparent" };
  const passed = PASSWORD_RULES.filter(r => r.test(password)).length;
  if (passed <= 2) return { score: 1, label: "Weak", color: "var(--danger)" };
  if (passed <= 3) return { score: 2, label: "Fair", color: "var(--warning)" };
  if (passed <= 4) return { score: 3, label: "Good", color: "#3b82f6" };
  return { score: 4, label: "Strong", color: "var(--success)" };
}

function EyeIcon({ open }: { open: boolean }) {
  if (open) {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
    );
  }
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  );
}

const HIGHLIGHTS = [
  { text: "Persistent memory across sessions" },
  { text: "Learn skills from conversations" },
  { text: "Delegate tasks between employees" },
  { text: "Push code to GitHub with PR review" },
];

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const { register, user, pendingVerificationEmail } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const strength = useMemo(() => getStrength(password), [password]);
  const ruleResults = useMemo(() => PASSWORD_RULES.map(r => ({ ...r, passed: r.test(password) })), [password]);
  const allPassed = ruleResults.every(r => r.passed);

  useEffect(() => { if (user) router.push("/"); }, [user, router]);
  useEffect(() => { if (pendingVerificationEmail) router.push("/verify-email"); }, [pendingVerificationEmail, router]);
  if (user) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!allPassed) { toast("error", "Password too weak", "Please meet all password requirements."); return; }
    if (password !== confirm) { toast("error", "Passwords don't match", "Please re-enter your password."); return; }
    setLoading(true);
    try {
      await register(email, password);
    } catch (err) {
      toast("error", "Registration failed", err instanceof Error ? err.message : "Could not create account");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = {
    width: "100%", padding: "10px 14px", borderRadius: 10,
    border: "1px solid var(--border)", background: "var(--bg-card)",
    fontSize: 14, color: "var(--text-primary)", outline: "none",
    transition: "border-color 0.15s, box-shadow 0.15s",
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* Left branding panel */}
      <div className="auth-left-panel" style={{
        flex: "0 0 440px", background: "linear-gradient(160deg, #060918, #0f1130, #1a1350)",
        display: "flex", flexDirection: "column", justifyContent: "center",
        padding: "60px 48px", position: "relative", overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", top: -80, right: -80, width: 300, height: 300,
          borderRadius: "50%", background: "radial-gradient(circle, rgba(11,191,140,0.12), transparent 70%)",
        }} />

        <div style={{ position: "relative", zIndex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 40 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: "linear-gradient(135deg, #635bff, #7c3aed)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff", fontSize: 14, fontWeight: 800,
            }}>FA</div>
            <span style={{ fontSize: 20, fontWeight: 700, color: "#fff", letterSpacing: "-0.02em" }}>ForgeAI</span>
          </div>

          <h1 style={{
            fontSize: 32, fontWeight: 800, color: "#fff",
            lineHeight: 1.2, letterSpacing: "-0.03em", marginBottom: 16,
          }}>
            Build your AI<br />
            <span style={{ color: "#0bbf8c" }}>software team.</span>
          </h1>

          <p style={{ fontSize: 15, color: "rgba(255,255,255,0.55)", lineHeight: 1.7, marginBottom: 36, maxWidth: 340 }}>
            Six employees that persist, learn, and collaborate. No setup needed.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {HIGHLIGHTS.map((h) => (
              <div key={h.text} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{
                  width: 20, height: 20, borderRadius: 6,
                  background: "rgba(11,191,140,0.15)", border: "1px solid rgba(11,191,140,0.25)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 11, color: "#0bbf8c", flexShrink: 0,
                }}>&#10003;</div>
                <span style={{ fontSize: 13, color: "rgba(255,255,255,0.7)" }}>{h.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div style={{
        flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        padding: "40px 32px", background: "var(--bg-base)", overflowY: "auto",
      }}>
        <div style={{ width: "100%", maxWidth: 380 }}>
          <div style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", marginBottom: 6 }}>
              Create your account
            </h2>
            <p style={{ fontSize: 14, color: "var(--text-muted)" }}>
              Get started with your AI team in seconds
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label htmlFor="email" style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Email</label>
              <input id="email" type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)} style={inputStyle}
                onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
                onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Password</label>
              <div style={{ position: "relative" }}>
                <input id="password" type={showPassword ? "text" : "password"} required
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  style={{ ...inputStyle, paddingRight: 40 }}
                  onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
                  onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
                  placeholder="Create a strong password"
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--text-muted)", padding: 4, cursor: "pointer" }}>
                  <EyeIcon open={showPassword} />
                </button>
              </div>
              {password && (
                <>
                  <div style={{ display: "flex", gap: 3, marginTop: 6, marginBottom: 4 }}>
                    {[1, 2, 3, 4].map(level => (
                      <div key={level} style={{
                        flex: 1, height: 3, borderRadius: 2,
                        background: strength.score >= level ? strength.color : "var(--border)",
                        transition: "background 0.2s",
                      }} />
                    ))}
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 10px" }}>
                    {ruleResults.map(r => (
                      <span key={r.label} style={{ fontSize: 10, color: r.passed ? "var(--success)" : "var(--text-muted)", display: "flex", alignItems: "center", gap: 3 }}>
                        <span style={{ fontSize: 11 }}>{r.passed ? "✓" : "✗"}</span> {r.label}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div>
              <label htmlFor="confirm" style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Confirm Password</label>
              <div style={{ position: "relative" }}>
                <input id="confirm" type={showConfirm ? "text" : "password"} required
                  value={confirm} onChange={(e) => setConfirm(e.target.value)}
                  style={{ ...inputStyle, paddingRight: 40, borderColor: confirm && confirm !== password ? "var(--danger)" : undefined }}
                  onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
                  onBlur={(e) => { e.target.style.borderColor = confirm && confirm !== password ? "var(--danger)" : "var(--border)"; e.target.style.boxShadow = "none"; }}
                  placeholder="Re-enter your password"
                />
                <button type="button" onClick={() => setShowConfirm(!showConfirm)} tabIndex={-1}
                  aria-label={showConfirm ? "Hide password" : "Show password"}
                  style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--text-muted)", padding: 4, cursor: "pointer" }}>
                  <EyeIcon open={showConfirm} />
                </button>
              </div>
              {confirm && confirm !== password && (
                <span style={{ fontSize: 10, color: "var(--danger)", marginTop: 2, display: "block" }}>Passwords do not match</span>
              )}
            </div>

            <button
              type="submit" disabled={loading || !allPassed || password !== confirm}
              style={{
                width: "100%", padding: "11px 0", borderRadius: 10, border: "none",
                background: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600,
                cursor: loading || !allPassed ? "default" : "pointer",
                opacity: loading || !allPassed || password !== confirm ? 0.5 : 1,
                transition: "all 0.15s", boxShadow: "0 2px 8px rgba(99,91,255,0.25)",
              }}
              onMouseEnter={(e) => { if (!loading && allPassed) e.currentTarget.style.background = "var(--accent-light)"; }}
              onMouseLeave={(e) => e.currentTarget.style.background = "var(--accent)"}
            >
              {loading ? "Creating account..." : "Create Account"}
            </button>

            <SocialLoginButtons />
          </form>

          <p style={{ textAlign: "center", fontSize: 13, color: "var(--text-muted)", marginTop: 24 }}>
            Already have an account?{" "}
            <Link href="/login" style={{ color: "var(--accent)", fontWeight: 600, textDecoration: "none" }}>Sign in</Link>
          </p>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .auth-left-panel { display: none !important; }
        }
      `}</style>
    </div>
  );
}
