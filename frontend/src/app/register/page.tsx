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

  useEffect(() => {
    if (user) router.push("/");
  }, [user, router]);

  useEffect(() => {
    if (pendingVerificationEmail) router.push("/verify-email");
  }, [pendingVerificationEmail, router]);

  if (user) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!allPassed) {
      toast("error", "Password too weak", "Please meet all password requirements.");
      return;
    }
    if (password !== confirm) {
      toast("error", "Passwords don't match", "Please re-enter your password.");
      return;
    }
    setLoading(true);
    try {
      await register(email, password);
    } catch (err) {
      toast("error", "Registration failed", err instanceof Error ? err.message : "Could not create account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-10"
         style={{ background: "linear-gradient(145deg, var(--bg-base), var(--bg-elevated))" }}>
      <div className="text-center mb-8 max-w-md animate-fade-in">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] font-medium mb-5"
             style={{ background: "var(--success-bg)", color: "var(--success)", border: "1px solid var(--success-border)" }}>
          Start building in seconds
        </div>
        <h1 className="text-3xl font-bold tracking-tight mb-2" style={{ color: "var(--text-primary)" }}>
          AI Software Company
        </h1>
        <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>
          Create your account and start your AI software team.
        </p>
      </div>

      <div className="w-full max-w-sm animate-fade-in" style={{ animationDelay: "0.1s" }}>
        <form onSubmit={handleSubmit}
              className="rounded-xl p-6 space-y-4"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
          <div>
            <label htmlFor="email" className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none transition-colors"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
              onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
              placeholder="you@example.com"
            />
          </div>

          {/* Password with show/hide */}
          <div>
            <label htmlFor="password" className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Password</label>
            <div style={{ position: "relative" }}>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 pr-10 rounded-lg text-sm focus:outline-none transition-colors"
                style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
                onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
                placeholder="Create a strong password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="cursor-pointer"
                style={{
                  position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                  background: "none", border: "none", color: "var(--text-muted)", padding: 4,
                }}
                tabIndex={-1}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                <EyeIcon open={showPassword} />
              </button>
            </div>

            {/* Strength bar */}
            {password && (
              <div style={{ marginTop: 6 }}>
                <div style={{ display: "flex", gap: 3, marginBottom: 4 }}>
                  {[1, 2, 3, 4].map(level => (
                    <div key={level} style={{
                      flex: 1, height: 3, borderRadius: 2,
                      background: strength.score >= level ? strength.color : "var(--bg-secondary)",
                      transition: "background 0.2s",
                    }} />
                  ))}
                </div>
                <span style={{ fontSize: 10, color: strength.color, fontWeight: 600 }}>{strength.label}</span>
              </div>
            )}

            {/* Requirements checklist */}
            {password && (
              <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: "2px 10px" }}>
                {ruleResults.map(r => (
                  <span key={r.label} style={{
                    fontSize: 10,
                    color: r.passed ? "var(--success)" : "var(--text-muted)",
                    display: "flex", alignItems: "center", gap: 3,
                  }}>
                    <span style={{ fontSize: 11 }}>{r.passed ? "✓" : "✗"}</span>
                    {r.label}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Confirm password with show/hide */}
          <div>
            <label htmlFor="confirm" className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Confirm Password</label>
            <div style={{ position: "relative" }}>
              <input
                id="confirm"
                type={showConfirm ? "text" : "password"}
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full px-3 py-2.5 pr-10 rounded-lg text-sm focus:outline-none transition-colors"
                style={{
                  background: "var(--bg-base)",
                  border: `1px solid ${confirm && confirm !== password ? "var(--danger)" : "var(--border)"}`,
                  color: "var(--text-primary)",
                }}
                onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
                onBlur={(e) => { e.target.style.borderColor = confirm && confirm !== password ? "var(--danger)" : "var(--border)"; e.target.style.boxShadow = "none"; }}
                placeholder="Re-enter your password"
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="cursor-pointer"
                style={{
                  position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                  background: "none", border: "none", color: "var(--text-muted)", padding: 4,
                }}
                tabIndex={-1}
                aria-label={showConfirm ? "Hide password" : "Show password"}
              >
                <EyeIcon open={showConfirm} />
              </button>
            </div>
            {confirm && confirm !== password && (
              <span style={{ fontSize: 10, color: "var(--danger)", marginTop: 2, display: "block" }}>Passwords do not match</span>
            )}
          </div>

          <button
            type="submit"
            disabled={loading || !allPassed || password !== confirm}
            className="w-full py-2.5 rounded-lg text-white text-sm font-medium disabled:opacity-50 transition-all cursor-pointer"
            style={{ background: "var(--accent)", boxShadow: "0 2px 8px rgba(99, 91, 255, 0.25)" }}
            onMouseOver={(e) => (e.currentTarget.style.background = "var(--accent-light)")}
            onMouseOut={(e) => (e.currentTarget.style.background = "var(--accent)")}
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>
          <SocialLoginButtons />
        </form>
        <p className="text-center text-sm mt-4" style={{ color: "var(--text-muted)" }}>
          Already have an account?{" "}
          <Link href="/login" className="font-medium hover:underline" style={{ color: "var(--accent)" }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
