"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/Toast";

export default function VerifyEmailPage() {
  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const { pendingVerificationEmail, verifyEmail, resendCode, clearPendingVerification } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    if (!pendingVerificationEmail) {
      router.push("/login");
    }
  }, [pendingVerificationEmail, router]);

  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  function handleChange(index: number, value: string) {
    if (!/^\d*$/.test(value)) return;
    const newCode = [...code];
    newCode[index] = value.slice(-1);
    setCode(newCode);
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent) {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length > 0) {
      const newCode = [...code];
      for (let i = 0; i < 6; i++) {
        newCode[i] = pasted[i] || "";
      }
      setCode(newCode);
      const focusIdx = Math.min(pasted.length, 5);
      inputRefs.current[focusIdx]?.focus();
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fullCode = code.join("");
    if (fullCode.length !== 6) {
      toast("error", "Incomplete code", "Please enter all 6 digits.");
      return;
    }
    if (!pendingVerificationEmail) return;
    setLoading(true);
    try {
      await verifyEmail(pendingVerificationEmail, fullCode);
      toast("success", "Email verified!", "Welcome to ForgeAI.");
      router.push("/");
    } catch (err) {
      toast("error", "Verification failed", err instanceof Error ? err.message : "Invalid code");
      setCode(["", "", "", "", "", ""]);
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (!pendingVerificationEmail || resendCooldown > 0) return;
    setResending(true);
    try {
      await resendCode(pendingVerificationEmail);
      toast("success", "Code sent", "Check your email for the new code.");
      setResendCooldown(60);
    } catch (err) {
      toast("error", "Resend failed", err instanceof Error ? err.message : "Could not send code");
    } finally {
      setResending(false);
    }
  }

  if (!pendingVerificationEmail) return null;

  const maskedEmail = pendingVerificationEmail.replace(/(.{2})(.*)(@.*)/, "$1***$3");

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-10"
         style={{ background: "linear-gradient(145deg, var(--bg-base), var(--bg-elevated))" }}>
      <div className="text-center mb-8 max-w-md animate-fade-in">
        <div className="text-4xl mb-4">&#x1F4E7;</div>
        <h1 className="text-2xl font-bold tracking-tight mb-2" style={{ color: "var(--text-primary)" }}>
          Verify your email
        </h1>
        <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>
          We sent a 6-digit code to <strong style={{ color: "var(--text-secondary)" }}>{maskedEmail}</strong>
        </p>
      </div>

      <div className="w-full max-w-sm animate-fade-in" style={{ animationDelay: "0.1s" }}>
        <form onSubmit={handleSubmit}
              className="rounded-xl p-6 space-y-5"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
          <div className="flex justify-center gap-2" onPaste={handlePaste}>
            {code.map((digit, i) => (
              <input
                key={i}
                ref={(el) => { inputRefs.current[i] = el; }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleChange(i, e.target.value)}
                onKeyDown={(e) => handleKeyDown(i, e)}
                className="w-11 h-13 text-center text-xl font-bold rounded-lg focus:outline-none transition-all"
                style={{
                  background: "var(--bg-base)",
                  border: digit ? "2px solid var(--accent)" : "1px solid var(--border)",
                  color: "var(--text-primary)",
                  boxShadow: digit ? "0 0 0 3px var(--accent-bg)" : "none",
                }}
                autoFocus={i === 0}
              />
            ))}
          </div>

          <button
            type="submit"
            disabled={loading || code.join("").length !== 6}
            className="w-full py-2.5 rounded-lg text-white text-sm font-medium disabled:opacity-50 transition-all cursor-pointer"
            style={{ background: "var(--accent)", boxShadow: "0 2px 8px rgba(99, 91, 255, 0.25)" }}
            onMouseOver={(e) => (e.currentTarget.style.background = "var(--accent-light)")}
            onMouseOut={(e) => (e.currentTarget.style.background = "var(--accent)")}
          >
            {loading ? "Verifying..." : "Verify Email"}
          </button>

          <div className="text-center">
            <button
              type="button"
              onClick={handleResend}
              disabled={resending || resendCooldown > 0}
              className="text-xs font-medium cursor-pointer disabled:opacity-50"
              style={{ color: "var(--accent)", background: "none", border: "none" }}
            >
              {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : resending ? "Sending..." : "Didn't get the code? Resend"}
            </button>
          </div>
        </form>

        <p className="text-center text-sm mt-4" style={{ color: "var(--text-muted)" }}>
          <button
            onClick={() => { clearPendingVerification(); router.push("/login"); }}
            className="font-medium hover:underline cursor-pointer"
            style={{ color: "var(--accent)", background: "none", border: "none" }}
          >
            Back to Sign In
          </button>
        </p>
      </div>
    </div>
  );
}
