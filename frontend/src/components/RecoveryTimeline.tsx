"use client";

import { useState, useEffect } from "react";
import { getRecoveryHistory, type RecoveryCheckpoint, type RecoveryAttempt } from "@/lib/api";

const CHECKPOINT_COLORS: Record<string, string> = {
  sentinel_pass: "var(--success)",
  auto: "var(--info)",
  manual: "var(--brand)",
};

const OUTCOME_STYLES: Record<string, { bg: string; color: string }> = {
  recovered: { bg: "var(--success)", color: "#fff" },
  pending: { bg: "var(--warning)", color: "#000" },
  failed: { bg: "var(--danger)", color: "#fff" },
  aborted: { bg: "var(--text-muted)", color: "#fff" },
};

const STRATEGY_LABELS: Record<string, string> = {
  rollback_and_repair: "Rollback & Repair",
  retry_with_context: "Retry with Context",
  checkpoint_resume: "Resume from Checkpoint",
  retry_from_start: "Retry from Start",
  abort: "Abort",
};

function CheckpointNode({ cp }: { cp: RecoveryCheckpoint }) {
  const [expanded, setExpanded] = useState(false);
  const dotColor = CHECKPOINT_COLORS[cp.checkpoint_type] || "var(--info)";
  const claimCount = cp.verified_state?.count ?? 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "10px",
        cursor: "pointer",
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div style={{
        width: "12px",
        height: "12px",
        borderRadius: "50%",
        background: dotColor,
        border: "2px solid var(--bg)",
        boxShadow: `0 0 0 2px ${dotColor}`,
        flexShrink: 0,
        marginTop: "2px",
      }} />
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "12px", fontWeight: 600 }}>
            {cp.phase} (iter {cp.iteration})
          </span>
          <span style={{
            fontSize: "9px",
            padding: "1px 5px",
            borderRadius: "3px",
            background: "var(--bg-secondary)",
            color: "var(--text-muted)",
            fontWeight: 600,
            textTransform: "uppercase",
          }}>
            {cp.checkpoint_type.replace("_", " ")}
          </span>
          {claimCount > 0 && (
            <span style={{ fontSize: "10px", color: "var(--success)" }}>
              {claimCount} verified
            </span>
          )}
        </div>
        {expanded && cp.verified_state?.claims && (
          <div style={{
            marginTop: "6px",
            padding: "8px",
            background: "var(--bg-secondary)",
            borderRadius: "4px",
            fontSize: "11px",
          }}>
            {cp.verified_state.claims.slice(0, 10).map((claim, i) => (
              <div key={i} style={{
                display: "flex",
                gap: "6px",
                marginBottom: "3px",
                alignItems: "center",
              }}>
                <span style={{ color: "var(--success)", fontSize: "10px" }}>✓</span>
                <span style={{ color: "var(--text-muted)", minWidth: "80px", fontSize: "10px" }}>
                  {claim.key.split(":")[0]}
                </span>
                <span style={{ fontSize: "10px", color: "var(--text)" }}>
                  {Math.round(claim.confidence * 100)}% conf
                </span>
              </div>
            ))}
            {cp.verified_state.claims.length > 10 && (
              <div style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "4px" }}>
                +{cp.verified_state.claims.length - 10} more claims
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function AttemptNode({ attempt }: { attempt: RecoveryAttempt }) {
  const outcomeStyle = OUTCOME_STYLES[attempt.outcome] || OUTCOME_STYLES.pending;
  const strategyLabel = STRATEGY_LABELS[attempt.strategy] || attempt.strategy;

  return (
    <div style={{
      display: "flex",
      alignItems: "flex-start",
      gap: "10px",
    }}>
      <div style={{
        width: "12px",
        height: "12px",
        borderRadius: "2px",
        background: "var(--danger)",
        flexShrink: 0,
        marginTop: "2px",
        transform: "rotate(45deg)",
      }} />
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--danger)" }}>
            {attempt.failure_type.replace("_", " ")}
          </span>
          <span style={{
            fontSize: "9px",
            padding: "1px 5px",
            borderRadius: "3px",
            background: outcomeStyle.bg,
            color: outcomeStyle.color,
            fontWeight: 600,
            textTransform: "uppercase",
          }}>
            {attempt.outcome}
          </span>
        </div>
        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
          Strategy: {strategyLabel}
          {attempt.failure_phase && <span> at {attempt.failure_phase}</span>}
        </div>
        {attempt.failure_detail && (
          <div style={{
            fontSize: "10px",
            color: "var(--text-muted)",
            marginTop: "4px",
            padding: "4px 8px",
            background: "rgba(255,59,48,0.06)",
            borderRadius: "4px",
            maxHeight: "60px",
            overflow: "hidden",
          }}>
            {attempt.failure_detail.slice(0, 200)}
          </div>
        )}
      </div>
    </div>
  );
}

export default function RecoveryTimelinePanel({ executionId }: { executionId: string }) {
  const [checkpoints, setCheckpoints] = useState<RecoveryCheckpoint[]>([]);
  const [attempts, setAttempts] = useState<RecoveryAttempt[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const res = await getRecoveryHistory(executionId);
        setCheckpoints(res.checkpoints);
        setAttempts(res.recovery_attempts);
      } catch {
        setCheckpoints([]);
        setAttempts([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [executionId]);

  if (loading) return null;
  if (checkpoints.length === 0 && attempts.length === 0) return null;

  type TimelineItem =
    | { type: "checkpoint"; data: RecoveryCheckpoint; time: string }
    | { type: "attempt"; data: RecoveryAttempt; time: string };

  const timeline: TimelineItem[] = [
    ...checkpoints.map((cp): TimelineItem => ({ type: "checkpoint", data: cp, time: cp.created_at })),
    ...attempts.map((a): TimelineItem => ({ type: "attempt", data: a, time: a.created_at })),
  ].sort((a, b) => a.time.localeCompare(b.time));

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
        marginBottom: "12px",
      }}>
        <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "var(--text)" }}>
          Recovery Timeline
        </h3>
        <div style={{ display: "flex", gap: "8px", fontSize: "11px" }}>
          <span style={{ color: "var(--success)" }}>{checkpoints.length} checkpoints</span>
          {attempts.length > 0 && (
            <span style={{ color: "var(--danger)" }}>{attempts.length} recoveries</span>
          )}
        </div>
      </div>

      <div style={{
        position: "relative",
        paddingLeft: "6px",
        maxHeight: "350px",
        overflowY: "auto",
      }}>
        <div style={{
          position: "absolute",
          left: "11px",
          top: 0,
          bottom: 0,
          width: "2px",
          background: "var(--border)",
        }} />

        <div style={{ display: "flex", flexDirection: "column", gap: "12px", position: "relative" }}>
          {timeline.map((item, i) => (
            <div key={i}>
              {item.type === "checkpoint" ? (
                <CheckpointNode cp={item.data as RecoveryCheckpoint} />
              ) : (
                <AttemptNode attempt={item.data as RecoveryAttempt} />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
