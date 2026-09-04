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

function safeText(v: unknown): string {
  if (typeof v === "string") return v;
  if (v && typeof v === "object") return Object.values(v).map(safeText).join(" — ");
  return String(v ?? "");
}

// --- Role-specific human-readable renderers ---

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent)" }}>{title}</h4>
      <div className="text-sm" style={{ color: "var(--text-secondary)" }}>{children}</div>
    </div>
  );
}

function TextBlock({ text }: { text: unknown }) {
  const s = safeText(text);
  if (!s || s === "undefined") return null;
  return <p className="leading-relaxed">{s}</p>;
}

function BulletList({ items }: { items: unknown }) {
  if (!Array.isArray(items) || items.length === 0) return <span style={{ color: "var(--text-muted)" }}>None</span>;
  return (
    <ul className="space-y-1 ml-1">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2">
          <span className="mt-1.5 shrink-0" style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent)", display: "inline-block" }} />
          <span>{typeof item === "object" && item !== null ? safeText(item) : String(item)}</span>
        </li>
      ))}
    </ul>
  );
}

function renderCEOOutput(c: Record<string, any>) {
  return (
    <div className="space-y-4">
      {c.project_name && <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{safeText(c.project_name)}</div>}
      {c.vision && <Section title="Vision"><TextBlock text={c.vision} /></Section>}
      {c.problem_summary && <Section title="Problem Summary"><TextBlock text={c.problem_summary} /></Section>}
      {c.problem_analysis && <Section title="Problem Analysis"><TextBlock text={c.problem_analysis} /></Section>}
      {c.target_users && <Section title="Target Users">{typeof c.target_users === "string" ? <TextBlock text={c.target_users} /> : <BulletList items={c.target_users} />}</Section>}
      {c.success_criteria && <Section title="Success Criteria"><BulletList items={c.success_criteria} /></Section>}
      {c.components && <Section title="Components"><BulletList items={c.components} /></Section>}
      {c.task_assignments && <Section title="Task Assignments">{renderValue(c.task_assignments)}</Section>}
      {c.priority && <Section title="Priority"><TextBlock text={c.priority} /></Section>}
      {c.deliverable_type && (
        <div className="inline-block px-3 py-1 rounded-full text-xs font-semibold" style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}>
          Deliverable: {safeText(c.deliverable_type)}
        </div>
      )}
    </div>
  );
}

function renderBAOutput(c: Record<string, any>) {
  return (
    <div className="space-y-4">
      {c.problem_analysis && <Section title="Problem Analysis"><TextBlock text={c.problem_analysis} /></Section>}
      {c.stakeholders && <Section title="Stakeholders"><BulletList items={c.stakeholders} /></Section>}
      {c.user_personas && <Section title="User Personas">{renderValue(c.user_personas)}</Section>}
      {c.objectives && <Section title="Objectives"><BulletList items={c.objectives} /></Section>}
      {c.scope && <Section title="Scope"><TextBlock text={c.scope} /></Section>}
      {c.functional_requirements && <Section title="Functional Requirements"><BulletList items={c.functional_requirements} /></Section>}
      {c.non_functional_requirements && <Section title="Non-Functional Requirements"><BulletList items={c.non_functional_requirements} /></Section>}
      {c.user_stories && <Section title="User Stories"><BulletList items={c.user_stories} /></Section>}
      {c.constraints && <Section title="Constraints"><BulletList items={c.constraints} /></Section>}
      {c.acceptance_criteria && <Section title="Acceptance Criteria"><BulletList items={c.acceptance_criteria} /></Section>}
      {c.risks && (
        <Section title="Risks">
          {Array.isArray(c.risks) ? (
            <div className="space-y-2">
              {(c.risks as unknown[]).map((risk, i) => (
                <div key={i} className="p-2 rounded-lg" style={{ background: "rgba(237,95,116,0.04)", border: "1px solid rgba(237,95,116,0.1)" }}>
                  {typeof risk === "object" && risk !== null ? renderValue(risk) : <span>{String(risk)}</span>}
                </div>
              ))}
            </div>
          ) : <TextBlock text={c.risks} />}
        </Section>
      )}
    </div>
  );
}

function renderResearcherOutput(c: Record<string, any>) {
  return (
    <div className="space-y-4">
      {c.existing_products && <Section title="Existing Products & Competitors">{renderValue(c.existing_products)}</Section>}
      {c.comparison_matrix && <Section title="Comparison Matrix">{renderValue(c.comparison_matrix)}</Section>}
      {c.relevant_apis && <Section title="Relevant APIs"><BulletList items={c.relevant_apis} /></Section>}
      {c.open_source_tools && <Section title="Open Source Tools"><BulletList items={c.open_source_tools} /></Section>}
      {c.ai_frameworks && <Section title="AI Frameworks"><BulletList items={c.ai_frameworks} /></Section>}
      {c.industry_best_practices && <Section title="Industry Best Practices"><BulletList items={c.industry_best_practices} /></Section>}
      {c.innovation_opportunities && <Section title="Innovation Opportunities"><BulletList items={c.innovation_opportunities} /></Section>}
      {c.recommended_approach && <Section title="Recommended Approach"><TextBlock text={c.recommended_approach} /></Section>}
    </div>
  );
}

function renderArchitectOutput(c: Record<string, any>) {
  return (
    <div className="space-y-4">
      {c.system_type && (
        <div className="inline-block px-3 py-1 rounded-full text-xs font-semibold mb-2" style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}>
          {safeText(c.system_type)}
        </div>
      )}
      {c.architecture_overview && <Section title="Architecture Overview"><TextBlock text={c.architecture_overview} /></Section>}
      {c.tech_stack && <Section title="Tech Stack">{renderValue(c.tech_stack)}</Section>}
      {c.frontend_architecture && <Section title="Frontend Architecture">{renderValue(c.frontend_architecture)}</Section>}
      {c.backend_architecture && <Section title="Backend Architecture">{renderValue(c.backend_architecture)}</Section>}
      {c.database_design && <Section title="Database Design">{renderValue(c.database_design)}</Section>}
      {c.api_design && <Section title="API Design">{renderValue(c.api_design)}</Section>}
      {c.folder_structure && <Section title="Folder Structure"><pre className="text-xs p-3 rounded-lg overflow-x-auto" style={{ background: "var(--bg-elevated)", color: "var(--text-secondary)" }}>{safeText(c.folder_structure)}</pre></Section>}
      {c.deployment_strategy && <Section title="Deployment Strategy"><TextBlock text={c.deployment_strategy} /></Section>}
      {c.security_considerations && <Section title="Security Considerations"><BulletList items={c.security_considerations} /></Section>}
      {c.additional_notes && <Section title="Additional Notes"><TextBlock text={c.additional_notes} /></Section>}
    </div>
  );
}

function renderEngineerOutput(c: Record<string, any>) {
  const files = c.files as Array<{ filename?: string; content?: string; language?: string }> | undefined;
  return (
    <div className="space-y-4">
      {c.implementation_summary && <Section title="Implementation Summary"><TextBlock text={c.implementation_summary} /></Section>}
      {c.setup_instructions && <Section title="Setup Instructions"><TextBlock text={c.setup_instructions} /></Section>}
      {files && Array.isArray(files) && (
        <Section title={`Generated Files (${files.length})`}>
          <div className="space-y-3">
            {files.map((file, i) => (
              <div key={i} className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
                <div className="px-3 py-1.5 text-xs font-mono font-semibold" style={{ background: "var(--bg-elevated)", color: "var(--accent)" }}>
                  {file.filename || `file-${i + 1}`}
                </div>
                {file.content && (
                  <pre className="text-xs p-3 overflow-x-auto max-h-60" style={{ background: "var(--bg-base)", color: "var(--text-secondary)", margin: 0 }}>
                    {file.content.length > 2000 ? file.content.slice(0, 2000) + "\n... (truncated)" : file.content}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
      {c.dependencies && <Section title="Dependencies">{renderValue(c.dependencies)}</Section>}
      {c.testing_notes && <Section title="Testing Notes"><TextBlock text={c.testing_notes} /></Section>}
    </div>
  );
}

function renderPPTOutput(c: Record<string, any>) {
  const slides = c.slides as Array<{ title?: string; content?: string; bullet_points?: string[] }> | undefined;
  return (
    <div className="space-y-4">
      {c.report_data && <Section title="Report">{renderValue(c.report_data)}</Section>}
      {slides && Array.isArray(slides) && (
        <Section title={`Presentation Slides (${slides.length})`}>
          <div className="grid gap-3">
            {slides.map((slide, i) => (
              <div key={i} className="p-3 rounded-lg" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                <div className="font-semibold text-sm mb-1" style={{ color: "var(--text-primary)" }}>
                  Slide {i + 1}: {slide.title || "Untitled"}
                </div>
                {slide.content && <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>{slide.content}</p>}
                {slide.bullet_points && <BulletList items={slide.bullet_points} />}
              </div>
            ))}
          </div>
        </Section>
      )}
      {c.executive_summary && <Section title="Executive Summary"><TextBlock text={c.executive_summary} /></Section>}
    </div>
  );
}

function renderRawResponse(raw: string) {
  const paragraphs = raw.split(/\n{2,}/).filter(p => p.trim());
  if (paragraphs.length <= 1) {
    return <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>{raw}</p>;
  }
  return (
    <div className="space-y-3">
      {paragraphs.map((p, i) => (
        <p key={i} className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>{p.trim()}</p>
      ))}
    </div>
  );
}

const ROLE_RENDERERS: Record<string, (c: Record<string, unknown>) => React.ReactNode> = {
  ceo: renderCEOOutput,
  business_analyst: renderBAOutput,
  researcher: renderResearcherOutput,
  architect: renderArchitectOutput,
  engineer: renderEngineerOutput,
  ppt: renderPPTOutput,
};

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
          &ldquo;{safeText(review.team_note)}&rdquo;
        </div>
      )}

      <div className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>{safeText(review.overall_assessment)}</div>

      <div className="grid grid-cols-1 gap-3">
        {review.strengths.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--success)" }}>Strengths</div>
            {review.strengths.map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-sm mb-1">
                <span style={{ color: "var(--success)" }} className="shrink-0 mt-0.5">+</span>
                <span style={{ color: "var(--text-secondary)" }}>{safeText(s)}</span>
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
                <span style={{ color: "var(--text-secondary)" }}>{safeText(c)}</span>
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
                <span style={{ color: "var(--text-secondary)" }}>{safeText(s)}</span>
              </div>
            ))}
          </div>
        )}

        {(review.alignment_check || review.hackathon_readiness) && (
          <div className="mt-1 pt-3" style={{ borderTop: "1px solid var(--accent-border)" }}>
            {review.alignment_check && (
              <div className="mb-2">
                <div className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Alignment</div>
                <div className="text-sm" style={{ color: "var(--text-secondary)" }}>{safeText(review.alignment_check)}</div>
              </div>
            )}
            {review.hackathon_readiness && (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Hackathon readiness</div>
                <div className="text-sm" style={{ color: "var(--text-secondary)" }}>{safeText(review.hackathon_readiness)}</div>
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
            {hasParseError && typeof content.raw_response === "string" && content.raw_response ? (
              <div className="animate-slide-in">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--warning-bg)", color: "var(--warning)", border: "1px solid var(--warning-border)" }}>
                    Unstructured response
                  </span>
                </div>
                {renderRawResponse(content.raw_response as string)}
              </div>
            ) : ROLE_RENDERERS[role] ? (
              <div className="animate-slide-in">{ROLE_RENDERERS[role](displayContent)}</div>
            ) : (
              Object.entries(displayContent)
                .filter(([key]) => key !== "_parse_error")
                .map(([key, value]) => (
                  <div key={key} className="animate-slide-in">
                    <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent)" }}>
                      {key.replace(/_/g, " ")}
                    </h4>
                    <div className="text-sm">{renderValue(value)}</div>
                  </div>
                ))
            )}
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
