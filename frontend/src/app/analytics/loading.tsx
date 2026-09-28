export default function AnalyticsLoading() {
  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base)", padding: "32px 20px",
    }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div className="skeleton skeleton-text" style={{ width: 140, height: 28, marginBottom: 8 }} />
          <div className="skeleton skeleton-text" style={{ width: 280, height: 14 }} />
        </div>

        {/* Stat cards row */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
          gap: 16,
          marginBottom: 32,
        }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="skeleton-card" style={{ padding: 20 }}>
              <div className="skeleton skeleton-text-sm" style={{ width: 80, marginBottom: 12 }} />
              <div className="skeleton skeleton-text" style={{ width: 60, height: 28, marginBottom: 8 }} />
              <div className="skeleton skeleton-text-sm" style={{ width: 100 }} />
            </div>
          ))}
        </div>

        {/* Chart area */}
        <div className="analytics-grid-2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="skeleton-card" style={{ height: 280, padding: 20 }}>
            <div className="skeleton skeleton-text" style={{ width: 160, height: 16, marginBottom: 16 }} />
            <div className="skeleton" style={{ width: "100%", height: 200, borderRadius: 8 }} />
          </div>
          <div className="skeleton-card" style={{ height: 280, padding: 20 }}>
            <div className="skeleton skeleton-text" style={{ width: 140, height: 16, marginBottom: 16 }} />
            <div className="skeleton" style={{ width: "100%", height: 200, borderRadius: 8 }} />
          </div>
        </div>
      </div>
    </div>
  );
}
