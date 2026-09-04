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
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">AI Software Company</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Create your account</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] p-6 space-y-4">
          <div>
            <label htmlFor="email" className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-base)] text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Password</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-base)] text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
              placeholder="At least 6 characters"
            />
          </div>
          <div>
            <label htmlFor="confirm" className="block text-xs font-medium text-[var(--text-secondary)] mb-1">Confirm Password</label>
            <input
              id="confirm"
              type="password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-base)] text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
              placeholder="Re-enter your password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-light)] disabled:opacity-50 transition-colors cursor-pointer"
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>
          <SocialLoginButtons />
        </form>
        <p className="text-center text-sm text-[var(--text-muted)] mt-4">
          Already have an account?{" "}
          <Link href="/login" className="text-[var(--accent)] hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
