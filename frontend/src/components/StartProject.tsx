"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ROUTE_CONFIG, classifyTask, AGENT_CONFIG, getRouteGuardrail } from "@/lib/constants";

interface RecentProject {
  id: string;
  problem_statement: string;
  status: string;
}

interface Props {
  onStart: (problem: string, autoApprove: boolean, domain?: string | null, route?: string) => void;
  loading: boolean;
  recentProjects?: RecentProject[];
  hasDemo?: boolean;
  onLoadDemo?: () => void;
}

const DOMAINS = [
  { id: "healthtech", label: "Healthtech", icon: "🏥", color: "#10b981" },
  { id: "fintech", label: "Fintech", icon: "💳", color: "#6366f1" },
  { id: "edtech", label: "Edtech", icon: "🎓", color: "#f59e0b" },
  { id: "e-commerce", label: "E-Commerce", icon: "🛒", color: "#ec4899" },
  { id: "saas", label: "SaaS", icon: "☁️", color: "#8b5cf6" },
  { id: "iot", label: "IoT", icon: "📡", color: "#14b8a6" },
  { id: "cybersecurity", label: "Security", icon: "🔐", color: "#ef4444" },
  { id: "sustainability", label: "Green Tech", icon: "🌱", color: "#22c55e" },
  { id: "logistics", label: "Logistics", icon: "🚚", color: "#f97316" },
  { id: "media", label: "Media", icon: "🎬", color: "#a855f7" },
] as const;

const TEAM_MEMBERS = [
  { icon: "👨‍💼", label: "CEO", desc: "Analyzes & delegates", color: "#635bff", status: "Plans strategy" },
  { icon: "📋", label: "Business Analyst", desc: "Requirements & stories", color: "#0bbf8c", status: "Defines scope" },
  { icon: "🔍", label: "Researcher", desc: "Market & tech research", color: "#f5a623", status: "Finds insights" },
  { icon: "🏗️", label: "Architect", desc: "System design & APIs", color: "#5e81f4", status: "Designs systems" },
  { icon: "💻", label: "Engineer", desc: "Full working code", color: "#ed5f74", status: "Writes code" },
  { icon: "📊", label: "Presenter", desc: "Pitch deck & slides", color: "#00b5d8", status: "Creates pitch" },
];

const STATUS_DISPLAY: Record<string, { label: string; color: string; icon: string }> = {
  completed: { label: "Shipped", color: "#0bbf8c", icon: "🟢" },
  ba_review: { label: "BA Review", color: "#f5a623", icon: "🟡" },
  research_review: { label: "Research Review", color: "#f5a623", icon: "🟡" },
  architect_review: { label: "Architect Review", color: "#f5a623", icon: "🟡" },
  engineer_review: { label: "Engineer Review", color: "#f5a623", icon: "🟡" },
  ba_working: { label: "Analyzing", color: "#635bff", icon: "🔵" },
  research_working: { label: "Researching", color: "#635bff", icon: "🔵" },
  architect_working: { label: "Designing", color: "#635bff", icon: "🔵" },
  engineer_working: { label: "Building", color: "#635bff", icon: "🔵" },
  ppt_working: { label: "Presenting", color: "#635bff", icon: "🔵" },
  created: { label: "Starting", color: "#8898aa", icon: "⚪" },
};

const ROUTE_ORDER = ["quick_build", "standard", "full", "research", "report"] as const;

export default function StartProject({ onStart, loading, recentProjects, hasDemo, onLoadDemo }: Props) {
  const [problem, setProblem] = useState("");
  const [autoApprove, setAutoApprove] = useState(false);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null);

  const suggestedRoute = useMemo(() => {
    if (problem.trim().length < 10) return "full";
    return classifyTask(problem);
  }, [problem]);

  const activeRoute = selectedRoute || suggestedRoute;

  const guardrailWarning = useMemo(() => {
    return getRouteGuardrail(selectedRoute, suggestedRoute);
  }, [selectedRoute, suggestedRoute]);

  return (
    <div className="min-h-screen flex flex-col"
         style={{ background: "linear-gradient(180deg, var(--bg-base) 0%, var(--bg-elevated) 100%)" }}>
      <div className="flex-1 flex items-start justify-center p-6 pt-12">
        <div className="max-w-2xl w-full">

          {/* Hero */}
          <div className="text-center mb-8 animate-fade-in">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium mb-6"
                 style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", display: "inline-block",
                             boxShadow: "0 0 6px var(--success)", animation: "pulse 2s infinite" }} />
              Your AI company is ready
            </div>
            <h1 className="text-4xl md:text-5xl font-bold mb-3 tracking-tight" style={{ color: "var(--text-primary)" }}>
              What are we building?
            </h1>
            <p className="text-base" style={{ color: "var(--text-muted)", maxWidth: 420, margin: "0 auto" }}>
              Describe an idea. Your 6-person AI team turns it into working software.
            </p>
          </div>

          {/* Team lineup */}
          <div className="flex items-center justify-center gap-1 mb-8 animate-fade-in" style={{ animationDelay: "0.05s" }}>
            {TEAM_MEMBERS.map((t, i) => (
              <div key={t.label}
                   className="flex flex-col items-center gap-1.5 px-2 py-2 rounded-xl transition-all"
                   style={{
                     minWidth: 72,
                     animation: `fadeSlideUp 0.4s ${i * 0.08}s both`,
                   }}>
                <div className="relative">
                  <span className="text-2xl">{t.icon}</span>
                  <span style={{
                    position: "absolute", bottom: -2, right: -4,
                    width: 8, height: 8, borderRadius: "50%",
                    background: t.color, border: "2px solid var(--bg-base)",
                  }} />
                </div>
                <span className="text-[10px] font-semibold" style={{ color: t.color }}>{t.label.split(" ")[0]}</span>
              </div>
            ))}
          </div>

          {/* Input Card */}
          <div className="card p-6 animate-fade-in" style={{
            animationDelay: "0.1s",
            boxShadow: "0 8px 32px rgba(0,0,0,0.08)",
          }}>
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="Build a real-time collaboration tool for remote teams with video chat, shared whiteboards, and task tracking..."
              className="w-full h-32 rounded-xl p-4 text-[15px] leading-relaxed resize-none focus:outline-none transition-all"
              style={{
                background: "var(--bg-base)",
                border: "1.5px solid var(--border)",
                color: "var(--text-primary)",
              }}
              onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
              onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
            />

            {/* Route Selector */}
            {problem.trim().length >= 10 && (
              <div className="mt-4 animate-fade-in">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Pipeline route</span>
                  {!selectedRoute && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}>
                      auto-detected
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {ROUTE_ORDER.map((routeKey) => {
                    const route = ROUTE_CONFIG[routeKey];
                    const isActive = activeRoute === routeKey;
                    const isSuggested = !selectedRoute && suggestedRoute === routeKey;
                    return (
                      <button
                        key={routeKey}
                        type="button"
                        onClick={() => setSelectedRoute(isActive && selectedRoute ? null : routeKey)}
                        className="flex flex-col items-start px-3 py-2 rounded-xl text-left transition-all"
                        style={{
                          background: isActive ? "var(--accent-bg)" : "var(--bg-elevated)",
                          color: isActive ? "var(--accent)" : "var(--text-muted)",
                          border: `1.5px solid ${isActive ? "var(--accent)" : "var(--border)"}`,
                          minWidth: 130,
                          transform: isActive ? "scale(1.02)" : "scale(1)",
                        }}
                      >
                        <div className="flex items-center gap-1.5 w-full">
                          <span className="text-sm">{route.icon}</span>
                          <span className="text-xs font-semibold">{route.name}</span>
                          {isSuggested && (
                            <span className="ml-auto text-[9px] px-1 py-0.5 rounded" style={{ background: "var(--success-bg)", color: "var(--success)" }}>
                              rec
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] mt-0.5 opacity-70">{route.agents.length} agents ~{route.estimatedMinutes}m</span>
                      </button>
                    );
                  })}
                </div>
                <div className="mt-2 flex items-center gap-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
                  <span>Agents:</span>
                  {ROUTE_CONFIG[activeRoute].agents.map((agent) => {
                    const config = AGENT_CONFIG[agent];
                    return (
                      <span key={agent} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                        <span className="text-[10px]">{config?.icon}</span>
                        <span>{config?.label?.split(" ")[0] || agent}</span>
                      </span>
                    );
                  })}
                </div>

                {guardrailWarning && (
                  <div
                    className="mt-2 flex items-start gap-2 px-3 py-2 rounded-lg text-xs animate-fade-in"
                    style={{
                      background: "var(--warning-bg, #fef3c7)",
                      color: "var(--warning, #d97706)",
                      border: "1px solid var(--warning-border, #fde68a)",
                    }}
                  >
                    <span className="shrink-0 mt-px">&#9888;</span>
                    <span>
                      {guardrailWarning}{" "}
                      <button
                        type="button"
                        onClick={() => setSelectedRoute(null)}
                        className="underline font-medium"
                        style={{ color: "inherit" }}
                      >
                        Use recommended
                      </button>
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Domain Vertical Selector */}
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Industry focus</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--bg-elevated)", color: "var(--text-muted)" }}>optional</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {DOMAINS.map((d) => {
                  const isSelected = selectedDomain === d.id;
                  return (
                    <button
                      key={d.id}
                      type="button"
                      onClick={() => setSelectedDomain(isSelected ? null : d.id)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
                      style={{
                        background: isSelected ? `${d.color}18` : "var(--bg-elevated)",
                        color: isSelected ? d.color : "var(--text-muted)",
                        border: `1.5px solid ${isSelected ? d.color : "var(--border)"}`,
                        transform: isSelected ? "scale(1.05)" : "scale(1)",
                      }}
                    >
                      <span>{d.icon}</span>
                      {d.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Launch button */}
            <div className="flex items-center gap-3 mt-5">
              <label className="flex items-center gap-2 cursor-pointer select-none shrink-0"
                     style={{ color: "var(--text-muted)" }}>
                <input
                  type="checkbox"
                  checked={autoApprove}
                  onChange={(e) => setAutoApprove(e.target.checked)}
                  className="rounded"
                  style={{ accentColor: "var(--accent)", width: 16, height: 16 }}
                />
                <span className="text-xs font-medium">Auto-pilot</span>
              </label>
              <button
                onClick={() => onStart(problem, autoApprove, selectedDomain, activeRoute)}
                disabled={!problem.trim() || loading}
                className="btn-primary flex-1 text-[15px]"
                style={{ boxShadow: problem.trim() ? "0 4px 14px rgba(99, 91, 255, 0.3)" : "none" }}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-3">
                    <span className="spinner" style={{ borderTopColor: "white", borderColor: "rgba(255,255,255,0.3)" }} />
                    Starting your AI team...
                  </span>
                ) : (
                  <>{ROUTE_CONFIG[activeRoute]?.icon} Start Company{autoApprove ? " (Auto-pilot)" : ""}</>
                )}
              </button>
              {hasDemo && onLoadDemo && (
                <button
                  onClick={onLoadDemo}
                  disabled={loading}
                  className="btn-ghost text-[15px] px-5"
                  style={{ borderColor: "var(--success-border)", color: "var(--success)" }}
                >
                  Demo
                </button>
              )}
            </div>
          </div>

          {/* Recent Projects */}
          {recentProjects && recentProjects.length > 0 && (
            <div className="mt-8 animate-fade-in" style={{ animationDelay: "0.15s" }}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                  Your Projects
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-elevated)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                  {recentProjects.length} recent
                </span>
              </div>
              <div className="space-y-2">
                {recentProjects.map((p) => {
                  const statusInfo = STATUS_DISPLAY[p.status] || { label: p.status, color: "#8898aa", icon: "⚪" };
                  return (
                    <Link
                      key={p.id}
                      href={`/project/${p.id}`}
                      className="flex items-center gap-3 p-4 rounded-xl transition-all"
                      style={{
                        background: "var(--bg-card)",
                        border: "1px solid var(--border)",
                        textDecoration: "none",
                      }}
                      onMouseOver={(e) => { e.currentTarget.style.borderColor = "var(--accent-border)"; e.currentTarget.style.transform = "translateY(-1px)"; }}
                      onMouseOut={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.transform = "translateY(0)"; }}
                    >
                      <span className="text-sm shrink-0">{statusInfo.icon}</span>
                      <span className="text-sm truncate flex-1" style={{ color: "var(--text-secondary)" }}>
                        {p.problem_statement.length > 70
                          ? p.problem_statement.slice(0, 70) + "..."
                          : p.problem_statement}
                      </span>
                      <span
                        className="text-[10px] font-semibold px-2 py-1 rounded-md shrink-0"
                        style={{ background: `${statusInfo.color}12`, color: statusInfo.color, border: `1px solid ${statusInfo.color}20` }}
                      >
                        {statusInfo.label}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="text-center py-6">
        <p className="text-[11px]" style={{ color: "var(--text-muted)", opacity: 0.5 }}>
          CEO &bull; Business Analyst &bull; Researcher &bull; Architect &bull; Engineer &bull; Presenter
        </p>
      </div>

      <style jsx>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
