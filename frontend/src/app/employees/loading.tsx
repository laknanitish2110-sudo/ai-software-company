export default function EmployeesLoading() {
  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base)", padding: "32px 20px",
    }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
          <div>
            <div className="skeleton skeleton-text" style={{ width: 180, height: 28, marginBottom: 8 }} />
            <div className="skeleton skeleton-text" style={{ width: 260, height: 14 }} />
          </div>
          <div className="skeleton" style={{ width: 130, height: 40, borderRadius: 10 }} />
        </div>

        {/* Employee grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: 16,
        }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton-card" style={{ height: 180 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div className="skeleton skeleton-circle" style={{ width: 44, height: 44 }} />
                <div>
                  <div className="skeleton skeleton-text" style={{ width: 120, marginBottom: 6 }} />
                  <div className="skeleton skeleton-text-sm" style={{ width: 80 }} />
                </div>
              </div>
              <div className="skeleton skeleton-text" style={{ width: "90%" }} />
              <div className="skeleton skeleton-text" style={{ width: "70%" }} />
              <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                <div className="skeleton" style={{ width: 60, height: 22, borderRadius: 6 }} />
                <div className="skeleton" style={{ width: 60, height: 22, borderRadius: 6 }} />
                <div className="skeleton" style={{ width: 60, height: 22, borderRadius: 6 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
