"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/Toast";
import SocialLoginButtons from "@/components/SocialLoginButtons";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const { register, user } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  if (user) {
    router.push("/");
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      toast("error", "Passwords don't match", "Please re-enter your password.");
      return;
    }
    if (password.length < 6) {
      toast("error", "Password too short", "Use at least 6 characters.");
      return;
    }
    setLoading(true);
    try {
      await register(email, password);
      router.push("/");
    } catch (err) {
      toast("error", "Registration failed", err instanceof Error ? err.message : "Could not create account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-10"
         style={{ background: "linear-gradient(145deg, var(--bg-base), var(--bg-elevated))" }}>
      {/* Hero branding */}
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

      {/* Register card */}
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
          <div>
            <label htmlFor="password" className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Password</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none transition-colors"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
              onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
              placeholder="At least 6 characters"
            />
          </div>
          <div>
            <label htmlFor="confirm" className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Confirm Password</label>
            <input
              id="confirm"
              type="password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none transition-colors"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
              onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
              placeholder="Re-enter your password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
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
