"use client";

import { useState, useEffect } from "react";
import { getExecutionScorecard, type VerificationScorecard } from "@/lib/api";

const VERDICT_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  pass: { bg: "var(--success)", color: "#fff", label: "PASSED" },
  fail: { bg: "var(--danger)", color: "#fff", label: "FAILED" },
  pass_with_warnings: { bg: "var(--warning)", color: "#000", label: "PASSED WITH WARNINGS" },
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--danger)",
  major: "var(--warning)",
  minor: "var(--text-muted)",
};

function ScoreGauge({ label, score, color }: { label: string; score: number | null; color: string }) {
  if (score === null || score === undefined) return null;
  const pct = Math.round(score * 100);
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{
        position: "relative",
        width: "72px",
        height: "72px",
        margin: "0 auto 6px",
      }}>
        <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%" }}>
          <path
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none"
            stroke="var(--border)"
            strokeWidth="3"
          />
          <path
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none"
            stroke={color}
            strokeWidth="3"
            strokeDasharray={`${pct}, 100`}
            strokeLinecap="round"
          />
        </svg>
        <div style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          fontSize: "14px",
          fontWeight: 700,
          color,
        }}>
          {pct}%
        </div>
      </div>
      <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{label}</div>
    </div>
  );
}

function SeverityBar({ counts }: { counts: Record<string, number> }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) return <span style={{ color: "var(--success)", fontSize: "13px", fontWeight: 600 }}>No issues</span>;

  return (
    <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
      {Object.entries(counts).map(([sev, count]) => (
        count > 0 && (
          <div key={sev} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <div style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: SEVERITY_COLORS[sev] || "var(--text-muted)",
            }} />
            <span style={{ fontSize: "12px", fontWeight: 600, color: SEVERITY_COLORS[sev] }}>
              {count} {sev}
            </span>
          </div>
        )
      ))}
    </div>
  );
}

function TierTimeline({ tiers }: { tiers: Record<string, { name: string; verdict: string; confidence: number; issues_found: number; summary: string }> }) {
  const entries = Object.entries(tiers).sort(([a], [b]) => a.localeCompare(b));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {entries.map(([key, tier]) => {
        const passed = tier.verdict === "PASS";
        return (
          <div key={key} style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "8px 12px",
            background: "var(--bg-secondary)",
            borderRadius: "6px",
            borderLeft: `3px solid ${passed ? "var(--success)" : "var(--danger)"}`,
          }}>
            <span style={{
              fontSize: "16px",
              width: "24px",
              textAlign: "center",
            }}>
              {passed ? "✓" : "✗"}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "13px", fontWeight: 600, textTransform: "capitalize" }}>
                {tier.name} Sentinel
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                {tier.summary}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{
                fontSize: "11px",
                fontWeight: 600,
                color: passed ? "var(--success)" : "var(--danger)",
              }}>
                {tier.verdict}
              </div>
              <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                {Math.round(tier.confidence * 100)}% conf
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CostSavings({
  verificationCost,
  bugCostSaved,
}: {
  verificationCost: number | null;
  bugCostSaved: number | null;
}) {
  if (!verificationCost && !bugCostSaved) return null;
  const roi = verificationCost && bugCostSaved
    ? (bugCostSaved / Math.max(verificationCost, 0.001)).toFixed(1)
    : null;

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: roi ? "1fr 1fr 1fr" : "1fr 1fr",
      gap: "8px",
    }}>
      {verificationCost !== null && (
        <div style={{
          background: "var(--bg-secondary)",
          borderRadius: "8px",
          padding: "10px",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--warning)" }}>
            ${verificationCost.toFixed(4)}
          </div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>Verification Cost</div>
        </div>
      )}
      {bugCostSaved !== null && (
        <div style={{
          background: "var(--bg-secondary)",
          borderRadius: "8px",
          padding: "10px",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--success)" }}>
            ${bugCostSaved.toFixed(2)}
          </div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>Bug Cost Saved</div>
        </div>
      )}
      {roi && (
        <div style={{
          background: "var(--bg-secondary)",
          borderRadius: "8px",
          padding: "10px",
          textAlign: "center",
        }}>
          <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--brand)" }}>
            {roi}x
          </div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>ROI</div>
        </div>
      )}
    </div>
  );
}

export default function VerificationScorecardPanel({ executionId }: { executionId: string }) {
  const [scorecard, setScorecard] = useState<VerificationScorecard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const res = await getExecutionScorecard(executionId);
        setScorecard(res.scorecard);
      } catch {
        setError(null);
        setScorecard(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [executionId]);

  if (loading) return null;
  if (error || !scorecard) return null;

  const verdictStyle = VERDICT_STYLES[scorecard.final_verdict || ""] || VERDICT_STYLES.pass;

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
        marginBottom: "16px",
      }}>
        <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "var(--text)" }}>
          Verification Proof
        </h3>
        <span style={{
          padding: "3px 10px",
          borderRadius: "4px",
          background: verdictStyle.bg,
          color: verdictStyle.color,
          fontSize: "11px",
          fontWeight: 700,
          letterSpacing: "0.5px",
        }}>
          {verdictStyle.label}
        </span>
      </div>

      {/* Quality Scores */}
      <div style={{
        display: "flex",
        justifyContent: "center",
        gap: "24px",
        marginBottom: "16px",
      }}>
        <ScoreGauge
          label="Raw Score"
          score={scorecard.raw_quality_score}
          color="var(--warning)"
        />
        <ScoreGauge
          label="Verified Score"
          score={scorecard.verified_quality_score}
          color="var(--success)"
        />
        {scorecard.quality_delta !== null && (
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
            <div style={{
              fontSize: "20px",
              fontWeight: 700,
              color: scorecard.quality_delta > 0 ? "var(--success)" : scorecard.quality_delta < 0 ? "var(--danger)" : "var(--text-muted)",
            }}>
              {scorecard.quality_delta > 0 ? "+" : ""}{Math.round(scorecard.quality_delta * 100)}%
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Quality Delta</div>
          </div>
        )}
      </div>

      {/* Would have shipped warning */}
      {scorecard.would_have_shipped_raw && (
        <div style={{
          background: "rgba(255, 59, 48, 0.1)",
          border: "1px solid var(--danger)",
          borderRadius: "6px",
          padding: "8px 12px",
          marginBottom: "12px",
          fontSize: "12px",
          color: "var(--danger)",
          fontWeight: 600,
          textAlign: "center",
        }}>
          Without Sentinel, this would have shipped with critical bugs
        </div>
      )}

      {/* Issues breakdown */}
      {scorecard.issues_by_severity && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "6px", fontWeight: 600 }}>
            Issues Caught ({scorecard.issues_caught})
          </div>
          <SeverityBar counts={scorecard.issues_by_severity} />
        </div>
      )}

      {/* Tier results */}
      {scorecard.tier_results && Object.keys(scorecard.tier_results).length > 0 && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "6px", fontWeight: 600 }}>
            Sentinel Tiers ({scorecard.sentinel_tiers_run} run)
          </div>
          <TierTimeline tiers={scorecard.tier_results} />
        </div>
      )}

      {/* Cost savings */}
      <CostSavings
        verificationCost={scorecard.verification_cost_usd}
        bugCostSaved={scorecard.estimated_bug_cost_saved}
      />
    </div>
  );
}
