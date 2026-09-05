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
  { icon: "👨‍💼", label: "CEO" },
  { icon: "📋", label: "Analyst" },
  { icon: "🔍", label: "Research" },
  { icon: "🏗️", label: "Architect" },
  { icon: "💻", label: "Engineer" },
  { icon: "📊", label: "Presenter" },
];

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  useEffect(() => {
    const oauthError = searchParams.get("oauth_error");
    if (oauthError) {
      toast("error", "Sign in failed", OAUTH_ERROR_MESSAGES[oauthError] || oauthError);
    }
  }, [searchParams, toast]);

  if (user) {
    router.push("/");
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      toast("error", "Login failed", err instanceof Error ? err.message : "Invalid credentials");
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
             style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", display: "inline-block" }} />
          6 AI agents ready
        </div>
        <h1 className="text-3xl font-bold tracking-tight mb-2" style={{ color: "var(--text-primary)" }}>
          AI Software Company
        </h1>
        <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>
          Your AI team builds working software from a single idea.
        </p>

        {/* Team roster */}
        <div className="flex items-center justify-center gap-1 mt-5">
          {TEAM.map((t) => (
            <div key={t.label}
                 className="flex flex-col items-center gap-1 px-2 py-1.5 rounded-lg"
                 style={{ minWidth: 52 }}>
              <span className="text-lg">{t.icon}</span>
              <span className="text-[9px] font-medium" style={{ color: "var(--text-muted)" }}>{t.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Login card */}
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
              placeholder="Enter your password"
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
            {loading ? "Signing in..." : "Sign In"}
          </button>
          <SocialLoginButtons />
        </form>
        <p className="text-center text-sm mt-4" style={{ color: "var(--text-muted)" }}>
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-medium hover:underline" style={{ color: "var(--accent)" }}>Create one</Link>
        </p>
      </div>

      {/* Footer tagline */}
      <div className="mt-10 text-center animate-fade-in" style={{ animationDelay: "0.2s" }}>
        <p className="text-[11px]" style={{ color: "var(--text-muted)", opacity: 0.6 }}>
          Problem statement in, working software out.
        </p>
      </div>
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
