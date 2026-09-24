"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/Toast";
import SocialLoginButtons from "@/components/SocialLoginButtons";

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  no_email: "Could not get your email from the provider.",
  invalid_state: "Security check failed. Please try again.",
  token_exchange_failed: "Authentication failed. Please try again.",
  server_error: "An unexpected error occurred. Please try again.",
  callback_failed: "Could not complete sign in. Please try again.",
  email_not_verified: "Your email is not verified with this provider.",
  no_token: "No authentication token received. Please try again.",
  missing_params: "Authentication response was incomplete. Please try again.",
};

const TEAM = [
  { icon: "🏗️", label: "Architect", name: "Arc" },
  { icon: "📋", label: "Business Analyst", name: "Sage" },
  { icon: "🔍", label: "Researcher", name: "Scout" },
  { icon: "⚡", label: "Engineer", name: "Atlas" },
  { icon: "🛡️", label: "QA", name: "Sentinel" },
  { icon: "✍️", label: "Writer", name: "Scribe" },
];

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

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login, user, pendingVerificationEmail } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  useEffect(() => {
    const oauthError = searchParams.get("oauth_error");
    if (oauthError) {
      toast("error", "Sign in failed", OAUTH_ERROR_MESSAGES[oauthError] || oauthError);
    }
  }, [searchParams, toast]);

  useEffect(() => { if (user) router.push("/"); }, [user, router]);
  useEffect(() => { if (pendingVerificationEmail) router.push("/verify-email"); }, [pendingVerificationEmail, router]);
  if (user) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Invalid credentials";
      if (msg === "EMAIL_NOT_VERIFIED") { router.push("/verify-email"); return; }
      toast("error", "Login failed", msg);
    } finally {
      setLoading(false);
    }
  }

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
          borderRadius: "50%", background: "radial-gradient(circle, rgba(99,91,255,0.15), transparent 70%)",
        }} />
        <div style={{
          position: "absolute", bottom: -60, left: -60, width: 200, height: 200,
          borderRadius: "50%", background: "radial-gradient(circle, rgba(124,58,237,0.1), transparent 70%)",
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
            Your AI team,<br />
            <span style={{ color: "#635bff" }}>always ready.</span>
          </h1>

          <p style={{ fontSize: 15, color: "rgba(255,255,255,0.55)", lineHeight: 1.7, marginBottom: 40, maxWidth: 340 }}>
            Six persistent AI employees that learn, remember, and grow. From architecture to deployment.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
            {TEAM.map((t) => (
              <div key={t.name} style={{
                padding: "10px 12px", borderRadius: 10,
                background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)",
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <span style={{ fontSize: 16 }}>{t.icon}</span>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.85)" }}>{t.name}</div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)" }}>{t.label}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div style={{
        flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        padding: "40px 32px", background: "var(--bg-base)",
      }}>
        <div style={{ width: "100%", maxWidth: 380 }}>
          <div style={{ marginBottom: 32 }}>
            <h2 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em", marginBottom: 6 }}>
              Welcome back
            </h2>
            <p style={{ fontSize: 14, color: "var(--text-muted)" }}>
              Sign in to your workspace
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label htmlFor="email" style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Email</label>
              <input
                id="email" type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 10,
                  border: "1px solid var(--border)", background: "var(--bg-card)",
                  fontSize: 14, color: "var(--text-primary)", outline: "none",
                  transition: "border-color 0.15s, box-shadow 0.15s",
                }}
                onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
                onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label htmlFor="password" style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>Password</label>
              <div style={{ position: "relative" }}>
                <input
                  id="password" type={showPassword ? "text" : "password"} required
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  style={{
                    width: "100%", padding: "10px 14px", paddingRight: 40, borderRadius: 10,
                    border: "1px solid var(--border)", background: "var(--bg-card)",
                    fontSize: 14, color: "var(--text-primary)", outline: "none",
                    transition: "border-color 0.15s, box-shadow 0.15s",
                  }}
                  onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
                  onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
                  placeholder="Enter your password"
                />
                <button
                  type="button" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  style={{
                    position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                    background: "none", border: "none", color: "var(--text-muted)", padding: 4, cursor: "pointer",
                  }}
                >
                  <EyeIcon open={showPassword} />
                </button>
              </div>
            </div>

            <button
              type="submit" disabled={loading}
              style={{
                width: "100%", padding: "11px 0", borderRadius: 10, border: "none",
                background: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600,
                cursor: loading ? "default" : "pointer", opacity: loading ? 0.6 : 1,
                transition: "all 0.15s", boxShadow: "0 2px 8px rgba(99,91,255,0.25)",
              }}
              onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = "var(--accent-light)"; }}
              onMouseLeave={(e) => e.currentTarget.style.background = "var(--accent)"}
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>

            <SocialLoginButtons />
          </form>

          <p style={{ textAlign: "center", fontSize: 13, color: "var(--text-muted)", marginTop: 24 }}>
            Don&apos;t have an account?{" "}
            <Link href="/register" style={{ color: "var(--accent)", fontWeight: 600, textDecoration: "none" }}>Create one</Link>
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

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
