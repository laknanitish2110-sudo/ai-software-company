export default function GoalsLoading() {
  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base)", padding: "32px 20px",
    }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
          <div>
            <div className="skeleton skeleton-text" style={{ width: 120, height: 28, marginBottom: 8 }} />
            <div className="skeleton skeleton-text" style={{ width: 220, height: 14 }} />
          </div>
          <div className="skeleton" style={{ width: 120, height: 40, borderRadius: 10 }} />
        </div>

        {/* Goal cards */}
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton-card" style={{ marginBottom: 12, padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <div className="skeleton skeleton-text" style={{ width: "60%", height: 18, marginBottom: 8 }} />
                <div className="skeleton skeleton-text-sm" style={{ width: "40%" }} />
              </div>
              <div className="skeleton" style={{ width: 70, height: 24, borderRadius: 6 }} />
            </div>
            {/* Progress bar */}
            <div className="skeleton" style={{ width: "100%", height: 6, borderRadius: 3, marginBottom: 12 }} />
            <div style={{ display: "flex", gap: 12 }}>
              <div className="skeleton skeleton-text-sm" style={{ width: 80 }} />
              <div className="skeleton skeleton-text-sm" style={{ width: 100 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
