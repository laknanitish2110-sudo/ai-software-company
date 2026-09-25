"use client";

import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("App error:", error);
  }, [error]);

  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24,
    }}>
      <div style={{ textAlign: "center", maxWidth: 440 }}>
        <div style={{
          width: 80, height: 80, borderRadius: 24, margin: "0 auto 24px",
          background: "rgba(237,95,116,0.08)",
          border: "1px solid rgba(237,95,116,0.15)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#ed5f74" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </div>
        <h1 style={{
          fontSize: 22, fontWeight: 700, color: "var(--text-primary)",
          marginBottom: 8, letterSpacing: "-0.02em",
        }}>
          Something went wrong
        </h1>
        <p style={{
          fontSize: 15, color: "var(--text-secondary)", lineHeight: 1.6,
          marginBottom: 12,
        }}>
          An unexpected error occurred. This has been logged automatically.
        </p>
        {error.message && (
          <div style={{
            padding: "8px 14px", borderRadius: 8, marginBottom: 24,
            background: "rgba(237,95,116,0.06)", border: "1px solid rgba(237,95,116,0.15)",
            fontSize: 13, color: "#ed5f74", fontFamily: "monospace",
            wordBreak: "break-word",
          }}>
            {error.message.length > 200 ? error.message.slice(0, 200) + "..." : error.message}
          </div>
        )}
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <button
            onClick={reset}
            style={{
              padding: "11px 24px", borderRadius: 10, border: "none",
              background: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600,
              cursor: "pointer", boxShadow: "0 2px 12px rgba(99,91,255,0.3)",
              transition: "all 0.15s",
            }}
          >
            Try Again
          </button>
          <a href="/" style={{
            padding: "11px 24px", borderRadius: 10,
            border: "1px solid var(--border)", background: "var(--bg-card)",
            color: "var(--text-primary)", fontSize: 14, fontWeight: 600,
            textDecoration: "none", transition: "all 0.15s",
            display: "inline-flex", alignItems: "center",
          }}>
            Go Home
          </a>
        </div>
      </div>
    </div>
  );
}
