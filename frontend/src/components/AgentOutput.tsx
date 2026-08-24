"use client";

import { useState } from "react";
import { AGENT_CONFIG } from "@/lib/constants";

interface PeerReview {
  reviewer: string;
  reviewer_label: string;
  reviewed: string;
  quality_score?: number;
  overall_assessment: string;
  strengths: string[];
  concerns: string[];
  suggestions: string[];
  alignment_check?: string;
  hackathon_readiness?: string;
  team_note: string;
}

interface Props {
  role: string;
  content: Record<string, unknown>;
  status: string;
  outputId: string;
  onApprove: (outputId: string) => void;
  onReject: (outputId: string, feedback: string) => void;
  onRevise?: (role: string, feedback: string) => void;
  showActions: boolean;
  readOnly?: boolean;
  peerReview?: PeerReview | null;
}

function renderValue(value: unknown, depth: number = 0): React.ReactNode {
  if (value === null || value === undefined) return <span style={{ color: "var(--text-muted)" }}>--</span>;
  if (typeof value === "boolean") return <span style={{ color: value ? "var(--success)" : "var(--danger)" }}>{String(value)}</span>;
  if (typeof value === "number") return <span style={{ color: "var(--accent)" }}>{value}</span>;

  if (typeof value === "string") {
    if (value.length > 300) {
      return <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{value}</p>;
    }
    return <span style={{ color: "var(--text-secondary)" }}>{value}</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span style={{ color: "var(--text-muted)" }}>None</span>;
    return (
      <ul className="space-y-1.5 ml-1">
        {value.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span className="mt-1.5 shrink-0" style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--accent)", display: "inline-block" }} />
            <div style={{ color: "var(--text-secondary)" }}>
              {typeof item === "object" && item !== null ? renderValue(item, depth + 1) : String(item)}
            </div>
          </li>
        ))}
      </ul>
    );
  }

  if (typeof value === "object") {
    return (
      <div className={`space-y-3 ${depth > 0 ? "ml-3 pl-3" : ""}`}
           style={depth > 0 ? { borderLeft: "2px solid var(--border)" } : {}}>
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k}>
            <div className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>
              {k.replace(/_/g, " ")}
            </div>
            <div className="text-sm">{renderValue(v, depth + 1)}</div>
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 8 ? "var(--success)" : score >= 6 ? "var(--accent)" : score >= 4 ? "var(--warning)" : "var(--danger)";
  const bg = score >= 8 ? "var(--success-bg)" : score >= 6 ? "var(--accent-bg)" : score >= 4 ? "var(--warning-bg)" : "rgba(237,95,116,0.06)";
  const border = score >= 8 ? "var(--success-border)" : score >= 6 ? "var(--accent-border)" : score >= 4 ? "var(--warning-border)" : "rgba(237,95,116,0.15)";
  const label = score >= 8 ? "Strong" : score >= 6 ? "Good" : score >= 4 ? "Needs work" : "Weak";

  return (
    <span className="status-badge" style={{ background: bg, color, border: `1px solid ${border}`, fontSize: 11 }}>
      {score}/10 {label}
    </span>
  );
}

function PeerReviewSection({ review }: { review: PeerReview }) {
  const reviewerConfig = AGENT_CONFIG[review.reviewer];

  return (
    <div className="mt-5 rounded-xl p-4" style={{ background: "var(--accent-bg)", border: "1px solid var(--accent-border)" }}>
      <div className="flex items-center gap-2 mb-3">
        <span>{reviewerConfig?.icon || "💬"}</span>
        <span className="text-sm font-semibold" style={{ color: "var(--accent)" }}>
          Peer Review by {review.reviewer_label}
        </span>
        {review.quality_score != null && <ScoreBadge score={review.quality_score} />}
      </div>

      {review.team_note && (
        <div className="mb-4 text-sm italic rounded-lg p-3" style={{
          color: "var(--text-secondary)",
          background: "var(--bg-elevated)",
          borderLeft: "3px solid var(--accent)"
        }}>
          &ldquo;{review.team_note}&rdquo;
        </div>
      )}

      <div className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>{review.overall_assessment}</div>

      <div className="grid grid-cols-1 gap-3">
        {review.strengths.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--success)" }}>Strengths</div>
            {review.strengths.map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-sm mb-1">
                <span style={{ color: "var(--success)" }} className="shrink-0 mt-0.5">+</span>
                <span style={{ color: "var(--text-secondary)" }}>{s}</span>
              </div>
            ))}
          </div>
        )}

        {review.concerns.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--warning)" }}>Concerns</div>
            {review.concerns.map((c, i) => (
              <div key={i} className="flex items-start gap-2 text-sm mb-1">
                <span style={{ color: "var(--warning)" }} className="shrink-0 mt-0.5">!</span>
                <span style={{ color: "var(--text-secondary)" }}>{c}</span>
              </div>
            ))}
          </div>
        )}

        {review.suggestions.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--info)" }}>Suggestions</div>
            {review.suggestions.map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-sm mb-1">
                <span style={{ color: "var(--info)" }} className="shrink-0 mt-0.5">~</span>
                <span style={{ color: "var(--text-secondary)" }}>{s}</span>
              </div>
            ))}
          </div>
        )}

        {(review.alignment_check || review.hackathon_readiness) && (
          <div className="mt-1 pt-3" style={{ borderTop: "1px solid var(--accent-border)" }}>
            {review.alignment_check && (
              <div className="mb-2">
                <div className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Alignment</div>
                <div className="text-sm" style={{ color: "var(--text-secondary)" }}>{review.alignment_check}</div>
              </div>
            )}
            {review.hackathon_readiness && (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Hackathon readiness</div>
                <div className="text-sm" style={{ color: "var(--text-secondary)" }}>{review.hackathon_readiness}</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AgentOutput({
  role,
  content,
  status,
  outputId,
  onApprove,
  onReject,
  onRevise,
  showActions,
  readOnly,
  peerReview,
}: Props) {
  const [feedback, setFeedback] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const [showRevise, setShowRevise] = useState(false);
  const [reviseFeedback, setReviseFeedback] = useState("");
  const [revising, setRevising] = useState(false);
  const [expanded, setExpanded] = useState(showActions);
  const config = AGENT_CONFIG[role];

  const hasParseError = "_parse_error" in content;
  const displayContent = hasParseError && "raw_response" in content
    ? { response: content.raw_response }
    : content;

  if (status === "superseded") return null;

  const statusStyle = status === "approved"
    ? { bg: "var(--success-bg)", color: "var(--success)", border: "var(--success-border)" }
    : status === "rejected"
    ? { bg: "rgba(237, 95, 116, 0.06)", color: "var(--danger)", border: "rgba(237, 95, 116, 0.15)" }
    : { bg: "var(--warning-bg)", color: "var(--warning)", border: "var(--warning-border)" };

  return (
    <div
      className="card overflow-hidden animate-fade-in transition-all"
      style={{
        borderColor: showActions ? "var(--warning-border)" : undefined,
        ...(showActions ? { boxShadow: "0 0 20px rgba(245, 166, 35, 0.08)" } : {}),
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
        style={{ background: expanded ? "var(--bg-elevated)" : "transparent" }}
        onMouseEnter={(e) => { if (!expanded) e.currentTarget.style.background = "var(--bg-card-hover)"; }}
        onMouseLeave={(e) => { if (!expanded) e.currentTarget.style.background = "transparent"; }}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">{config.icon}</span>
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="font-semibold text-[15px]" style={{ color: "var(--text-primary)" }}>{config.label}</span>
            <span
              className="status-badge"
              style={{ background: statusStyle.bg, color: statusStyle.color, border: `1px solid ${statusStyle.border}` }}
            >
              {status === "approved" ? "Approved" : status === "rejected" ? "Rejected" : "Needs Review"}
            </span>
            {peerReview && (
              <span
                className="status-badge"
                style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}
              >
                Reviewed by {AGENT_CONFIG[peerReview.reviewer]?.label || peerReview.reviewer_label}
              </span>
            )}
          </div>
        </div>
        <span
          className="transition-transform duration-200"
          style={{ color: "var(--text-muted)", transform: expanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block" }}
        >
          ▾
        </span>
      </div>

      {/* Content */}
      {expanded && (
        <div className="px-5 pb-5" style={{ borderTop: "1px solid var(--border)" }}>
          <div className="mt-4 space-y-4">
            {Object.entries(displayContent)
              .filter(([key]) => key !== "_parse_error")
              .map(([key, value]) => (
                <div key={key} className="animate-slide-in">
                  <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent)" }}>
                    {key.replace(/_/g, " ")}
                  </h4>
                  <div className="text-sm">{renderValue(value)}</div>
                </div>
              ))}
          </div>

          {peerReview && <PeerReviewSection review={peerReview} />}

          {/* Action Buttons */}
          {showActions && !readOnly && (
            <div className="mt-6 pt-5" style={{ borderTop: "1px solid var(--border)" }}>
              <div className="flex gap-3">
                <button onClick={() => onApprove(outputId)} className="btn-success flex-1 text-[15px]">
                  Approve
                </button>
                <button onClick={() => setShowFeedback(!showFeedback)} className="btn-ghost flex-1 text-[15px]">
                  Request Revision
                </button>
              </div>
              {showFeedback && (
                <div className="mt-3 animate-fade-in">
                  <textarea
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="What should be changed?"
                    className="w-full h-20 rounded-xl p-3 text-sm resize-none focus:outline-none transition-all"
                    style={{
                      background: "var(--bg-base)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                    onFocus={(e) => { e.target.style.borderColor = "var(--danger)"; e.target.style.boxShadow = "0 0 0 3px rgba(237, 95, 116, 0.1)"; }}
                    onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
                  />
                  <button
                    onClick={() => onReject(outputId, feedback)}
                    disabled={!feedback.trim()}
                    className="mt-2 w-full text-sm font-semibold py-2.5 px-4 rounded-xl transition-all cursor-pointer disabled:cursor-not-allowed"
                    style={{
                      background: feedback.trim() ? "var(--danger)" : "var(--bg-elevated)",
                      color: feedback.trim() ? "white" : "var(--text-muted)",
                      border: "none",
                    }}
                  >
                    Send Revision Request
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Revise Approved Output */}
          {status === "approved" && onRevise && !readOnly && !showActions && (
            <div className="mt-4 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
              {!showRevise ? (
                <button
                  onClick={() => setShowRevise(true)}
                  className="btn-ghost text-xs py-2 px-4 flex items-center gap-1.5"
                  style={{ color: "var(--accent)", borderColor: "var(--accent-border)" }}
                >
                  <span>↻</span> Revise this output
                </button>
              ) : (
                <div className="animate-fade-in">
                  <label className="text-xs font-medium mb-1.5 block" style={{ color: "var(--text-muted)" }}>
                    What should {config.label} change?
                  </label>
                  <textarea
                    value={reviseFeedback}
                    onChange={(e) => setReviseFeedback(e.target.value)}
                    placeholder="e.g. Make the architecture more microservices-oriented..."
                    className="w-full h-20 rounded-xl p-3 text-sm resize-none focus:outline-none transition-all"
                    style={{
                      background: "var(--bg-base)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                    onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
                    onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={async () => {
                        setRevising(true);
                        onRevise(role, reviseFeedback);
                        setReviseFeedback("");
                        setShowRevise(false);
                        setRevising(false);
                      }}
                      disabled={!reviseFeedback.trim() || revising}
                      className="flex-1 text-sm font-semibold py-2.5 px-4 rounded-xl transition-all cursor-pointer disabled:cursor-not-allowed"
                      style={{
                        background: reviseFeedback.trim() ? "var(--accent)" : "var(--bg-elevated)",
                        color: reviseFeedback.trim() ? "white" : "var(--text-muted)",
                        border: "none",
                      }}
                    >
                      {revising ? "Starting revision..." : "Start Revision"}
                    </button>
                    <button
                      onClick={() => { setShowRevise(false); setReviseFeedback(""); }}
                      className="btn-ghost text-sm py-2.5 px-4"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
