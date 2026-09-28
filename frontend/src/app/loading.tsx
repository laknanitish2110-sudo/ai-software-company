export default function HomeLoading() {
  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base)", padding: "32px 20px",
    }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div className="skeleton skeleton-text" style={{ width: 200, height: 32, margin: "0 auto 12px" }} />
          <div className="skeleton skeleton-text" style={{ width: 320, height: 14, margin: "0 auto" }} />
        </div>

        {/* Action cards */}
        <div className="analytics-grid-2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 32 }}>
          <div className="skeleton-card" style={{ height: 140 }}>
            <div className="skeleton skeleton-text" style={{ width: 140, height: 18, marginBottom: 12 }} />
            <div className="skeleton skeleton-text" style={{ width: "80%", marginBottom: 8 }} />
            <div className="skeleton skeleton-text" style={{ width: "60%" }} />
          </div>
          <div className="skeleton-card" style={{ height: 140 }}>
            <div className="skeleton skeleton-text" style={{ width: 120, height: 18, marginBottom: 12 }} />
            <div className="skeleton skeleton-text" style={{ width: "75%", marginBottom: 8 }} />
            <div className="skeleton skeleton-text" style={{ width: "55%" }} />
          </div>
        </div>

        {/* Recent projects */}
        <div className="skeleton skeleton-text" style={{ width: 160, height: 18, marginBottom: 16 }} />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton-card" style={{ marginBottom: 10, padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div className="skeleton skeleton-text" style={{ width: "50%", height: 16 }} />
              <div className="skeleton skeleton-text-sm" style={{ width: 80 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
