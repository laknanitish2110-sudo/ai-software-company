"use client";

import { useState, useEffect } from "react";
import { getExecutionTrustChain, type TrustProofTrail, type TrustChainLink } from "@/lib/api";

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  verified: { bg: "var(--success)", color: "#fff", label: "Verified" },
  pending: { bg: "var(--warning)", color: "#000", label: "Pending" },
  failed: { bg: "var(--danger)", color: "#fff", label: "Failed" },
};

const INTEGRITY_STYLES: Record<string, { bg: string; color: string }> = {
  intact: { bg: "var(--success)", color: "#fff" },
  partial: { bg: "var(--warning)", color: "#000" },
  broken: { bg: "var(--danger)", color: "#fff" },
};

function TrustMeter({ ratio, integrity }: { ratio: number; integrity: string }) {
  const pct = Math.round(ratio * 100);
  const intStyle = INTEGRITY_STYLES[integrity] || INTEGRITY_STYLES.partial;
  return (
    <div style={{ marginBottom: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
        <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)" }}>
          Chain Trust: {pct}%
        </span>
        <span style={{
          fontSize: "9px",
          padding: "2px 6px",
          borderRadius: "3px",
          background: intStyle.bg,
          color: intStyle.color,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.5px",
        }}>
          {integrity}
        </span>
      </div>
      <div style={{
        height: "6px",
        borderRadius: "3px",
        background: "var(--surface-raised)",
        overflow: "hidden",
      }}>
        <div style={{
          height: "100%",
          width: `${pct}%`,
          borderRadius: "3px",
          background: integrity === "broken" ? "var(--danger)"
            : integrity === "partial" ? "var(--warning)"
            : "var(--success)",
          transition: "width 0.4s ease",
        }} />
      </div>
    </div>
  );
}

function ChainStats({ trail }: { trail: TrustProofTrail }) {
  const stats = [
    { label: "Links", value: trail.total_links },
    { label: "Verified", value: trail.verified_links, color: "var(--success)" },
    { label: "Failed", value: trail.failed_links, color: "var(--danger)" },
    { label: "Pending", value: trail.pending_links, color: "var(--warning)" },
    { label: "Max Depth", value: trail.max_delegation_depth },
    { label: "Agents", value: trail.agents_involved.length },
  ];
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(3, 1fr)",
      gap: "8px",
      marginBottom: "16px",
    }}>
      {stats.map(s => (
        <div key={s.label} style={{
          padding: "8px",
          borderRadius: "6px",
          background: "var(--surface-raised)",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "16px", fontWeight: 700, color: s.color || "var(--text)" }}>
            {s.value}
          </div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>{s.label}</div>
        </div>
      ))}
    </div>
  );
}

function LinkNode({ link }: { link: TrustChainLink }) {
  const [expanded, setExpanded] = useState(false);
  const status = STATUS_STYLES[link.verification_status] || STATUS_STYLES.pending;
  const isSelfExec = link.from_agent_id === link.to_agent_id && link.action_type === "execution";
  const indent = link.depth * 20;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "10px",
        cursor: "pointer",
        marginLeft: `${indent}px`,
        paddingBottom: "10px",
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={{
        width: "10px",
        height: "10px",
        borderRadius: link.action_type === "delegation" ? "2px" : "50%",
        background: status.bg,
        marginTop: "4px",
        flexShrink: 0,
        border: link.action_type === "delegation" ? "none" : "2px solid var(--surface)",
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)" }}>
            {isSelfExec
              ? link.from_agent_name
              : `${link.from_agent_name} → ${link.to_agent_name}`}
          </span>
          <span style={{
            fontSize: "9px",
            padding: "1px 5px",
            borderRadius: "3px",
            background: status.bg,
            color: status.color,
            fontWeight: 600,
            textTransform: "uppercase",
          }}>
            {status.label}
          </span>
          {link.trust_score !== null && (
            <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
              trust: {(link.trust_score * 100).toFixed(0)}%
            </span>
          )}
        </div>
        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
          {link.action_type === "delegation" ? "Delegated" : "Executed"}
          {link.depth > 0 && <span> (depth {link.depth})</span>}
        </div>
        {expanded && (
          <div style={{
            marginTop: "6px",
            padding: "8px",
            borderRadius: "4px",
            background: "var(--surface-raised)",
            fontSize: "11px",
          }}>
            {link.task_description && (
              <div style={{ marginBottom: "4px" }}>
                <span style={{ fontWeight: 600 }}>Task:</span>{" "}
                {link.task_description.slice(0, 200)}
              </div>
            )}
            <div style={{ marginBottom: "4px" }}>
              <span style={{ fontWeight: 600 }}>Authority:</span>{" "}
              {link.authority_basis}
            </div>
            {link.verified_at && (
              <div style={{ color: "var(--text-muted)" }}>
                Verified at {new Date(link.verified_at).toLocaleTimeString()}
                {link.verified_by && <span> by {link.verified_by}</span>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function TrustChainPanel({ executionId }: { executionId: string }) {
  const [trail, setTrail] = useState<TrustProofTrail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await getExecutionTrustChain(executionId);
        setTrail(res);
      } catch {
        setTrail(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [executionId]);

  if (loading) {
    return (
      <div style={{ padding: "16px", color: "var(--text-muted)", fontSize: "12px" }}>
        Loading trust chain...
      </div>
    );
  }

  if (!trail || trail.total_links === 0) return null;

  const sortedLinks = [...trail.links].sort((a, b) => {
    if (a.depth !== b.depth) return a.depth - b.depth;
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });

  return (
    <div style={{
      padding: "16px",
      borderRadius: "8px",
      background: "var(--surface)",
      border: "1px solid var(--border)",
      marginTop: "12px",
    }}>
      <h3 style={{
        margin: "0 0 12px",
        fontSize: "14px",
        fontWeight: 700,
        color: "var(--text)",
        display: "flex",
        alignItems: "center",
        gap: "6px",
      }}>
        <span style={{ fontSize: "16px" }}>&#x1f517;</span>
        Trust Chain
      </h3>

      <TrustMeter ratio={trail.trust_ratio} integrity={trail.chain_integrity} />
      <ChainStats trail={trail} />

      {trail.agents_involved.length > 1 && (
        <div style={{
          marginBottom: "12px",
          padding: "8px",
          borderRadius: "6px",
          background: "var(--surface-raised)",
          fontSize: "11px",
          color: "var(--text-muted)",
        }}>
          Agents: {trail.agents_involved.join(" → ")}
        </div>
      )}

      <div style={{ borderLeft: "2px solid var(--border)", paddingLeft: "8px" }}>
        {sortedLinks.map(link => (
          <LinkNode key={link.id} link={link} />
        ))}
      </div>
    </div>
  );
}
