"use client";

import { use, useState, useEffect } from "react";
import Link from "next/link";
import AgentOutputCard from "@/components/AgentOutput";
import { getSharedProject, ProjectState } from "@/lib/api";
import { AGENT_CONFIG, PIPELINE_ORDER } from "@/lib/constants";

function SharedSkeleton() {
  return (
    <div className="min-h-screen p-6 max-w-4xl mx-auto">
      <div className="animate-pulse space-y-6">
        <div className="h-8 rounded-lg" style={{ background: "var(--bg-elevated)", width: "60%" }} />
        <div className="h-4 rounded" style={{ background: "var(--bg-elevated)", width: "90%" }} />
        <div className="space-y-4 mt-8">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-xl" style={{ background: "var(--bg-elevated)" }} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function SharedProjectPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [state, setState] = useState<ProjectState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSharedProject(token)
      .then(setState)
      .catch(() => setError("This shared link is invalid or has expired."));
  }, [token]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card p-10 text-center max-w-md">
          <div className="text-4xl mb-4">🔗</div>
          <h2 className="text-xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>Link Not Found</h2>
          <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>{error}</p>
          <Link href="/" className="btn-primary text-sm px-6 py-2.5" style={{ textDecoration: "none" }}>
            Go to AI Software Company
          </Link>
        </div>
      </div>
    );
  }

  if (!state?.project) return <SharedSkeleton />;

  const { project, outputs } = state;
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

  const approvedOutputs = outputs.filter((o) => o.status === "approved");
  const orderedOutputs = PIPELINE_ORDER
    .map((role) => approvedOutputs.find((o) => o.role === role))
    .filter(Boolean) as typeof approvedOutputs;

  return (
    <div className="min-h-screen p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8 animate-fade-in">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs px-2.5 py-1 rounded-full font-medium"
                style={{ background: "var(--success-bg)", color: "var(--success)", border: "1px solid var(--success-border)" }}>
            Completed Project
          </span>
          {state.memory?.domain_vertical && (
            <span className="text-xs px-2.5 py-1 rounded-full font-medium"
                  style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}>
              {state.memory.domain_vertical.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
            </span>
          )}
        </div>
        <h1 className="text-3xl font-bold tracking-tight mb-3" style={{ color: "var(--text-primary)" }}>
          AI Software Company
        </h1>
        <div className="card p-4" style={{ borderLeft: "3px solid var(--accent)" }}>
          <div className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>
            Problem Statement
          </div>
          <p className="text-[15px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {project.problem_statement}
          </p>
        </div>
      </div>

      {/* Pipeline Summary */}
      <div className="mb-6 animate-fade-in" style={{ animationDelay: "0.05s" }}>
        <div className="flex items-center gap-2 flex-wrap">
          {PIPELINE_ORDER.map((role, i) => {
            const config = AGENT_CONFIG[role];
            const hasOutput = orderedOutputs.some((o) => o.role === role);
            return (
              <div key={role} className="flex items-center gap-2">
                {i > 0 && <div style={{ width: 20, height: 2, background: hasOutput ? "var(--success)" : "var(--border)", opacity: 0.5 }} />}
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium"
                     style={{
                       background: hasOutput ? "rgba(11,191,140,0.08)" : "var(--bg-elevated)",
                       color: hasOutput ? "var(--success)" : "var(--text-muted)",
                       border: `1px solid ${hasOutput ? "rgba(11,191,140,0.2)" : "var(--border)"}`,
                     }}>
                  <span>{config.icon}</span>
                  {hasOutput && <span style={{ fontSize: 10 }}>✓</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Download Buttons */}
      <div className="flex gap-3 mb-8 flex-wrap animate-fade-in" style={{ animationDelay: "0.1s" }}>
        <a href={`${API_BASE}/shared/${token}/download/code`}
           target="_blank" rel="noopener noreferrer"
           className="btn-success text-sm py-2.5 px-5 flex items-center gap-2"
           style={{ textDecoration: "none" }}>
          <span>📦</span> Download Code
        </a>
        <a href={`${API_BASE}/shared/${token}/download/pptx`}
           target="_blank" rel="noopener noreferrer"
           className="btn-primary text-sm py-2.5 px-5 flex items-center gap-2"
           style={{ textDecoration: "none" }}>
          <span>📊</span> Presentation
        </a>
        <a href={`${API_BASE}/shared/${token}/download/docx`}
           target="_blank" rel="noopener noreferrer"
           className="btn-ghost text-sm py-2.5 px-5 flex items-center gap-2"
           style={{ textDecoration: "none" }}>
          <span>📄</span> Report
        </a>
      </div>

      {/* Agent Outputs */}
      <div className="space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
          Agent Deliverables
        </h2>
        {orderedOutputs.map((output, i) => (
          <div key={output.id} className="animate-fade-in" style={{ animationDelay: `${0.15 + i * 0.05}s` }}>
            <AgentOutputCard
              role={output.role}
              content={output.content as Record<string, unknown>}
              status={output.status}
              outputId={output.id}
              onApprove={() => {}}
              onReject={() => {}}
              showActions={false}
              readOnly={true}
            />
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-12 mb-6 text-center animate-fade-in" style={{ animationDelay: "0.4s" }}>
        <div style={{ height: 1, background: "var(--border)", marginBottom: 24 }} />
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Built with <Link href="/" style={{ color: "var(--accent)", textDecoration: "none" }}>AI Software Company</Link> — 6 AI agents, one product.
        </p>
      </div>
    </div>
  );
}
