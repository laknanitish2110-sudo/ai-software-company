import Link from "next/link";

export default function NotFound() {
  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24,
    }}>
      <div style={{ textAlign: "center", maxWidth: 440 }}>
        <div style={{
          width: 80, height: 80, borderRadius: 24, margin: "0 auto 24px",
          background: "linear-gradient(135deg, rgba(99,91,255,0.1), rgba(124,58,237,0.1))",
          border: "1px solid rgba(99,91,255,0.15)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 36,
        }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M16 16s-1.5-2-4-2-4 2-4 2"/>
            <line x1="9" y1="9" x2="9.01" y2="9"/>
            <line x1="15" y1="9" x2="15.01" y2="9"/>
          </svg>
        </div>
        <div style={{
          fontSize: 56, fontWeight: 800, letterSpacing: "-0.04em",
          background: "linear-gradient(135deg, var(--accent), #7c3aed)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          lineHeight: 1, marginBottom: 12,
        }}>
          404
        </div>
        <h1 style={{
          fontSize: 22, fontWeight: 700, color: "var(--text-primary)",
          marginBottom: 8, letterSpacing: "-0.02em",
        }}>
          Page not found
        </h1>
        <p style={{
          fontSize: 15, color: "var(--text-secondary)", lineHeight: 1.6,
          marginBottom: 32,
        }}>
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <Link href="/" style={{
            padding: "11px 24px", borderRadius: 10, border: "none",
            background: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600,
            textDecoration: "none", boxShadow: "0 2px 12px rgba(99,91,255,0.3)",
            transition: "all 0.15s",
          }}>
            Go Home
          </Link>
          <Link href="/employees" style={{
            padding: "11px 24px", borderRadius: 10,
            border: "1px solid var(--border)", background: "var(--bg-card)",
            color: "var(--text-primary)", fontSize: 14, fontWeight: 600,
            textDecoration: "none", transition: "all 0.15s",
          }}>
            View Team
          </Link>
        </div>
      </div>
    </div>
  );
}
