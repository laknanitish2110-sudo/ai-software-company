"use client";

export function EmptyState({
  icon,
  title,
  description,
  action,
  onAction,
}: {
  icon: string;
  title: string;
  description: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div style={{
      textAlign: "center", padding: "60px 24px",
      borderRadius: 16, border: "1px solid var(--border)",
      background: "var(--bg-card)",
    }}>
      <div style={{
        width: 64, height: 64, borderRadius: 20, margin: "0 auto 16px",
        background: "rgba(99,91,255,0.08)", border: "1px solid rgba(99,91,255,0.12)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 28,
      }}>
        {icon}
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
        {title}
      </div>
      <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: action ? 20 : 0, maxWidth: 320, margin: "0 auto" }}>
        {description}
      </div>
      {action && onAction && (
        <button
          onClick={onAction}
          style={{
            marginTop: 20, padding: "10px 22px", borderRadius: 10, border: "none",
            background: "var(--accent)", color: "#fff", fontSize: 13, fontWeight: 600,
            cursor: "pointer", transition: "all 0.15s",
          }}
        >
          {action}
        </button>
      )}
    </div>
  );
}

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div style={{
      padding: "14px 18px", borderRadius: 12, marginBottom: 16,
      background: "rgba(237,95,116,0.06)", border: "1px solid rgba(237,95,116,0.15)",
      display: "flex", alignItems: "center", gap: 12,
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: "rgba(237,95,116,0.1)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ed5f74" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{message}</div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: "6px 14px", borderRadius: 8, border: "1px solid rgba(237,95,116,0.2)",
            background: "transparent", color: "#ed5f74", fontSize: 12, fontWeight: 600,
            cursor: "pointer", flexShrink: 0,
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
