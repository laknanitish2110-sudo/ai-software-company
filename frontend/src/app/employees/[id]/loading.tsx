export default function EmployeeChatLoading() {
  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base)",
      display: "flex",
    }}>
      {/* Sidebar */}
      <div style={{
        width: 280, borderRight: "1px solid var(--border)",
        padding: "20px 16px", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <div className="skeleton skeleton-circle" style={{ width: 48, height: 48 }} />
          <div>
            <div className="skeleton skeleton-text" style={{ width: 100, marginBottom: 6 }} />
            <div className="skeleton skeleton-text-sm" style={{ width: 70 }} />
          </div>
        </div>
        {/* Tab bar */}
        <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ width: 56, height: 28, borderRadius: 6 }} />
          ))}
        </div>
        {/* Side content */}
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton-card" style={{ height: 48, marginBottom: 8 }}>
            <div className="skeleton skeleton-text" style={{ width: "80%" }} />
          </div>
        ))}
      </div>

      {/* Chat area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "20px 24px" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
          <div className="skeleton skeleton-circle" style={{ width: 36, height: 36 }} />
          <div>
            <div className="skeleton skeleton-text" style={{ width: 140, marginBottom: 4 }} />
            <div className="skeleton skeleton-text-sm" style={{ width: 90 }} />
          </div>
        </div>
        {/* Messages */}
        <div style={{ flex: 1 }}>
          {[false, true, false, true, false].map((isUser, i) => (
            <div key={i} style={{
              display: "flex", justifyContent: isUser ? "flex-end" : "flex-start",
              marginBottom: 16,
            }}>
              <div className="skeleton" style={{
                width: isUser ? "45%" : "60%",
                height: isUser ? 40 : 64,
                borderRadius: 14,
              }} />
            </div>
          ))}
        </div>
        {/* Input */}
        <div className="skeleton" style={{ width: "100%", height: 48, borderRadius: 12 }} />
      </div>
    </div>
  );
}
