"use client";

import { useState, useEffect } from "react";
import { getExecutionState, type StateClaim } from "@/lib/api";

const STATUS_STYLES: Record<string, { bg: string; color: string; dot: string }> = {
  verified: { bg: "rgba(52,199,89,0.12)", color: "var(--success)", dot: "var(--success)" },
  unverified: { bg: "rgba(255,204,0,0.12)", color: "var(--warning)", dot: "var(--warning)" },
  stale: { bg: "rgba(142,142,147,0.12)", color: "var(--text-muted)", dot: "var(--text-muted)" },
  contradicted: { bg: "rgba(255,59,48,0.12)", color: "var(--danger)", dot: "var(--danger)" },
  superseded: { bg: "rgba(142,142,147,0.08)", color: "var(--text-muted)", dot: "var(--border)" },
};

function TrustMeter({ ratio }: { ratio: number }) {
  const pct = Math.round(ratio * 100);
  const color = pct >= 80 ? "var(--success)" : pct >= 50 ? "var(--warning)" : "var(--danger)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{
        flex: 1,
        height: "6px",
        borderRadius: "3px",
        background: "var(--border)",
        overflow: "hidden",
      }}>
        <div style={{
          width: `${pct}%`,
          height: "100%",
          borderRadius: "3px",
          background: color,
          transition: "width 0.3s ease",
        }} />
      </div>
      <span style={{ fontSize: "12px", fontWeight: 700, color, minWidth: "36px" }}>
        {pct}%
      </span>
    </div>
  );
}

function StatusBreakdown({ byStatus }: { byStatus: Record<string, number> }) {
  const total = Object.values(byStatus).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  return (
    <div style={{
      display: "flex",
      gap: "4px",
      height: "8px",
      borderRadius: "4px",
      overflow: "hidden",
      marginBottom: "12px",
    }}>
      {Object.entries(byStatus).map(([status, count]) => {
        if (count === 0) return null;
        const style = STATUS_STYLES[status] || STATUS_STYLES.unverified;
        return (
          <div
            key={status}
            title={`${count} ${status}`}
            style={{
              flex: count,
              background: style.dot,
              minWidth: "4px",
            }}
          />
        );
      })}
    </div>
  );
}

function ClaimRow({ claim }: { claim: StateClaim }) {
  const [expanded, setExpanded] = useState(false);
  const style = STATUS_STYLES[claim.status] || STATUS_STYLES.unverified;

  const keyParts = claim.claim_key.split(":");
  const toolName = keyParts[0] || claim.claim_key;

  return (
    <div style={{
      padding: "8px 10px",
      borderRadius: "6px",
      background: style.bg,
      marginBottom: "6px",
      cursor: "pointer",
    }} onClick={() => setExpanded(!expanded)}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: style.dot,
          flexShrink: 0,
        }} />
        <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)", flex: 1 }}>
          {toolName}
        </span>
        <span style={{
          fontSize: "10px",
          padding: "1px 6px",
          borderRadius: "3px",
          background: style.dot,
          color: "#fff",
          fontWeight: 600,
          textTransform: "uppercase",
        }}>
          {claim.status}
        </span>
        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
          {Math.round(claim.confidence * 100)}%
        </span>
      </div>

      {expanded && (
        <div style={{
          marginTop: "8px",
          padding: "8px",
          background: "var(--bg)",
          borderRadius: "4px",
          fontSize: "11px",
        }}>
          <div style={{ marginBottom: "4px" }}>
            <strong style={{ color: "var(--text-muted)" }}>Type: </strong>
            <span>{claim.claim_type}</span>
          </div>
          <div style={{ marginBottom: "4px" }}>
            <strong style={{ color: "var(--text-muted)" }}>Value: </strong>
            <pre style={{
              margin: "2px 0 0",
              padding: "6px",
              background: "var(--bg-secondary)",
              borderRadius: "4px",
              fontSize: "10px",
              overflow: "auto",
              maxHeight: "120px",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}>
              {claim.claim_value.length > 500
                ? claim.claim_value.slice(0, 500) + "..."
                : claim.claim_value}
            </pre>
          </div>
          {claim.verified_at && (
            <div style={{ marginTop: "4px" }}>
              <strong style={{ color: "var(--text-muted)" }}>Verified: </strong>
              <span>{new Date(claim.verified_at).toLocaleString()} by {claim.verified_by}</span>
            </div>
          )}
          {claim.expires_at && (
            <div style={{ marginTop: "4px" }}>
              <strong style={{ color: "var(--text-muted)" }}>Expires: </strong>
              <span>{new Date(claim.expires_at).toLocaleString()}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function StateTruthPanel({ executionId }: { executionId: string }) {
  const [claims, setClaims] = useState<StateClaim[]>([]);
  const [byStatus, setByStatus] = useState<Record<string, number>>({});
  const [trustRatio, setTrustRatio] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await getExecutionState(executionId);
        setClaims(res.claims);
        setByStatus(res.by_status);
        setTrustRatio(res.trust_ratio);
      } catch {
        setClaims([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [executionId]);

  if (loading) return null;
  if (claims.length === 0) return null;

  const filtered = filter === "all"
    ? claims
    : claims.filter((c) => c.status === filter);

  const filterOptions = [
    { value: "all", label: "All" },
    { value: "verified", label: "Verified" },
    { value: "unverified", label: "Unverified" },
    { value: "stale", label: "Stale" },
    { value: "contradicted", label: "Contradicted" },
  ];

  return (
    <div style={{
      background: "var(--bg)",
      borderRadius: "12px",
      border: "1px solid var(--border)",
      padding: "16px",
      marginTop: "12px",
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: "10px",
      }}>
        <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "var(--text)" }}>
          State Truth
        </h3>
        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          {claims.length} claims
        </span>
      </div>

      <div style={{ marginBottom: "10px" }}>
        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>
          Trust Ratio
        </div>
        <TrustMeter ratio={trustRatio} />
      </div>

      <StatusBreakdown byStatus={byStatus} />

      <div style={{ display: "flex", gap: "4px", marginBottom: "10px" }}>
        {filterOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setFilter(opt.value)}
            style={{
              padding: "3px 8px",
              borderRadius: "4px",
              border: "none",
              fontSize: "11px",
              fontWeight: 600,
              cursor: "pointer",
              background: filter === opt.value ? "var(--brand)" : "var(--bg-secondary)",
              color: filter === opt.value ? "#fff" : "var(--text-muted)",
            }}
          >
            {opt.label}
            {opt.value !== "all" && byStatus[opt.value] ? ` (${byStatus[opt.value]})` : ""}
          </button>
        ))}
      </div>

      <div style={{ maxHeight: "400px", overflowY: "auto" }}>
        {filtered.map((claim) => (
          <ClaimRow key={claim.id} claim={claim} />
        ))}
        {filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: "16px", color: "var(--text-muted)", fontSize: "12px" }}>
            No {filter} claims
          </div>
        )}
      </div>
    </div>
  );
}
