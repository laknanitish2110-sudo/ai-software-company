"use client";

import { useState } from "react";
import { AGENT_CONFIG } from "@/lib/constants";
import AgentOutputCard from "./AgentOutput";

interface Output {
  id: string;
  role: string;
  content: Record<string, unknown>;
  status: string;
}

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
  overall_readiness?: string;
  hackathon_readiness?: string;
  team_note: string;
}

interface Props {
  stages: string[];
  outputs: Output[];
  currentStatus: string;
  streamingAgent: string | null;
  pendingOutput: Output | null;
  onApprove: (outputId: string) => void;
  onReject: (outputId: string, feedback: string) => void;
  onRevise: (role: string, feedback: string) => void;
  getPeerReview: (role: string) => PeerReview | null;
  liveStreamNode: React.ReactNode;
  validationNode: React.ReactNode;
}

const STAGE_NAMES: Record<string, string> = {
  ceo: "Product Brief",
  business_analyst: "Requirements",
  researcher: "Market Insights",
  architect: "System Design",
  engineer: "Product Build",
  ppt: "Deliverables",
};

const STATUS_TO_AGENT: Record<string, string> = {
  created: "ceo",
  ba_working: "business_analyst",
  ba_review: "business_analyst",
  research_working: "researcher",
  research_review: "researcher",
  architect_working: "architect",
  architect_review: "architect",
  engineer_working: "engineer",
  engineer_review: "engineer",
  ppt_working: "ppt",
};

function firstSentence(text: unknown, maxLen = 80): string {
  if (typeof text !== "string" || !text) return "";
  const clean = text.replace(/\n/g, " ").trim();
  const dot = clean.indexOf(".");
  const cut = dot > 0 && dot < maxLen ? dot + 1 : maxLen;
  const result = clean.slice(0, cut);
  return result.length < clean.length ? result + (dot > 0 && dot < maxLen ? "" : "...") : result;
}

function extractSummary(role: string, content: Record<string, unknown>): { headline: string; detail: string } {
  switch (role) {
    case "ceo": {
      const name = content.project_name as string || "";
      const vision = firstSentence(content.vision || content.problem_summary);
      return { headline: name, detail: vision };
    }
    case "business_analyst": {
      const funcReqs = Array.isArray(content.functional_requirements) ? content.functional_requirements : [];
      const nonFuncReqs = Array.isArray(content.non_functional_requirements) ? content.non_functional_requirements : [];
      const count = funcReqs.length + nonFuncReqs.length;
      const preview = funcReqs.slice(0, 3).map((r: unknown) => typeof r === "string" ? r.split(".")[0].split(",")[0].trim() : "").filter(Boolean).join(" · ");
      return {
        headline: `${count} requirement${count !== 1 ? "s" : ""} defined`,
        detail: preview,
      };
    }
    case "researcher": {
      const products = Array.isArray(content.existing_products) ? content.existing_products : [];
      const approach = firstSentence(content.recommended_approach);
      return {
        headline: products.length > 0 ? `${products.length} competitor${products.length !== 1 ? "s" : ""} analyzed` : "Research complete",
        detail: approach,
      };
    }
    case "architect": {
      const sysType = content.system_type as string || "";
      const stack = content.tech_stack;
      let stackStr = "";
      if (stack && typeof stack === "object" && !Array.isArray(stack)) {
        stackStr = Object.values(stack).flat().filter(v => typeof v === "string").slice(0, 4).join(", ");
      } else if (typeof stack === "string") {
        stackStr = firstSentence(stack, 60);
      }
      return { headline: sysType || "Architecture defined", detail: stackStr };
    }
    case "engineer": {
      const files = Array.isArray(content.files) ? content.files : [];
      const summary = firstSentence(content.implementation_summary);
      return {
        headline: files.length > 0 ? `${files.length} file${files.length !== 1 ? "s" : ""} generated` : "Code complete",
        detail: summary,
      };
    }
    case "ppt": {
      const slides = Array.isArray(content.slides) ? content.slides : [];
      const exec = firstSentence(content.executive_summary);
      return {
        headline: slides.length > 0 ? `${slides.length} slide${slides.length !== 1 ? "s" : ""} prepared` : "Documentation ready",
        detail: exec,
      };
    }
    default:
      return { headline: "Complete", detail: "" };
  }
}

type StageState = "future" | "active" | "review" | "done";

function getStageState(role: string, currentStatus: string, outputs: Output[], streamingAgent: string | null): StageState {
  const hasApproved = outputs.some(o => o.role === role && o.status === "approved");
  if (hasApproved) return "done";

  const hasPending = outputs.some(o => o.role === role && o.status === "pending");
  if (hasPending) return "review";

  if (streamingAgent === role) return "active";

  const activeAgent = STATUS_TO_AGENT[currentStatus];
  if (activeAgent === role) return "active";

  return "future";
}

export default function ProductJourney({
  stages,
  outputs,
  currentStatus,
  streamingAgent,
  pendingOutput,
  onApprove,
  onReject,
  onRevise,
  getPeerReview,
  liveStreamNode,
  validationNode,
}: Props) {
  const [expandedStage, setExpandedStage] = useState<string | null>(null);

  return (
    <div className="space-y-0">
      {/* Journey header */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
          Product Journey
        </span>
        <div style={{ height: 1, flex: 1, background: "var(--border)" }} />
      </div>

      {/* Stages */}
      <div style={{ position: "relative" }}>
        {/* Vertical line */}
        <div style={{
          position: "absolute",
          left: 11,
          top: 12,
          bottom: 12,
          width: 2,
          background: "var(--border)",
          borderRadius: 1,
        }} />

        <div className="space-y-1">
          {stages.map((role, idx) => {
            const state = getStageState(role, currentStatus, outputs, streamingAgent);
            const stageName = STAGE_NAMES[role] || AGENT_CONFIG[role]?.label || role;
            const config = AGENT_CONFIG[role];
            const output = outputs.find(o => o.role === role && (o.status === "approved" || o.status === "pending"));
            const isExpanded = expandedStage === role;
            const isPending = pendingOutput?.role === role;
            const summary = output ? extractSummary(role, output.content as Record<string, unknown>) : null;

            return (
              <div key={role} id={`stage-${role}`}>
                {/* Stage row */}
                <div
                  className="flex items-start gap-3 py-2 px-1 rounded-lg transition-colors"
                  style={{
                    cursor: state === "done" || state === "review" ? "pointer" : "default",
                    background: isPending ? "var(--warning-bg)" : isExpanded ? "var(--bg-elevated)" : "transparent",
                    border: isPending ? "1px solid var(--warning-border)" : "1px solid transparent",
                    borderRadius: 10,
                  }}
                  onClick={() => {
                    if (state === "done" || state === "review") {
                      setExpandedStage(isExpanded ? null : role);
                    }
                  }}
                >
                  {/* Stage indicator */}
                  <div style={{
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    fontSize: 12,
                    fontWeight: 700,
                    position: "relative",
                    zIndex: 1,
                    background: state === "done" ? "var(--success)"
                      : state === "active" ? config?.color || "var(--accent)"
                      : state === "review" ? "var(--warning)"
                      : "var(--bg-secondary)",
                    color: state === "future" ? "var(--text-muted)" : "white",
                    border: state === "future" ? "2px solid var(--border)" : "none",
                    boxShadow: state === "active" ? `0 0 12px ${config?.color || "var(--accent)"}40` : "none",
                  }}>
                    {state === "done" ? "✓" : state === "review" ? "!" : state === "active" ? (
                      <span style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: "white",
                        animation: "pulse 1.5s infinite",
                      }} />
                    ) : (
                      <span style={{ fontSize: 10 }}>{idx + 1}</span>
                    )}
                  </div>

                  {/* Stage content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="flex items-center gap-2">
                      <span style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: state === "future" ? "var(--text-muted)" : "var(--text-primary)",
                      }}>
                        {stageName}
                      </span>
                      {state === "review" && (
                        <span className="status-badge" style={{
                          background: "var(--warning-bg)", color: "var(--warning)",
                          border: "1px solid var(--warning-border)", fontSize: 10,
                        }}>
                          Awaiting Approval
                        </span>
                      )}
                      {state === "active" && (
                        <span style={{
                          fontSize: 10, color: config?.color || "var(--accent)",
                          fontWeight: 500,
                        }}>
                          In progress...
                        </span>
                      )}
                      {state === "done" && (isExpanded ? (
                        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>▲</span>
                      ) : (
                        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>▼</span>
                      ))}
                    </div>

                    {/* Summary line for completed stages */}
                    {state === "done" && summary && !isExpanded && (
                      <div style={{ marginTop: 2 }}>
                        {summary.headline && (
                          <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 500 }}>
                            {summary.headline}
                          </span>
                        )}
                        {summary.detail && (
                          <p style={{
                            fontSize: 11, color: "var(--text-muted)",
                            marginTop: 1, lineHeight: 1.4,
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                          }}>
                            {summary.detail}
                          </p>
                        )}
                      </div>
                    )}

                    {/* Active stage description */}
                    {state === "future" && (
                      <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 1 }}>
                        {config?.description || ""}
                      </p>
                    )}
                  </div>
                </div>

                {/* Live stream for active stage */}
                {state === "active" && streamingAgent === role && (
                  <div style={{ marginLeft: 36, marginTop: 4, marginBottom: 8 }}>
                    {liveStreamNode}
                  </div>
                )}

                {/* Expanded output for completed/review stages */}
                {(isExpanded || isPending) && output && (
                  <div style={{ marginLeft: 36, marginTop: 4, marginBottom: 8 }} className="animate-fade-in">
                    <AgentOutputCard
                      role={output.role}
                      content={output.content as Record<string, unknown>}
                      status={output.status}
                      outputId={output.id}
                      onApprove={onApprove}
                      onReject={onReject}
                      onRevise={onRevise}
                      showActions={isPending}
                      peerReview={getPeerReview(output.role)}
                    />
                    {role === "engineer" && validationNode}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
