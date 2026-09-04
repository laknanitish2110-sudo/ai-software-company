"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ROUTE_CONFIG, classifyTask, AGENT_CONFIG } from "@/lib/constants";

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

const AGENTS = [
  { icon: "👨‍💼", label: "CEO", desc: "Plans & delegates", color: "#635bff" },
  { icon: "📋", label: "Business Analyst", desc: "Defines requirements", color: "#0bbf8c" },
  { icon: "🔍", label: "Researcher", desc: "Finds what exists", color: "#f5a623" },
  { icon: "🏗️", label: "Architect", desc: "Designs the system", color: "#5e81f4" },
  { icon: "💻", label: "Engineer", desc: "Writes the code", color: "#ed5f74" },
  { icon: "📊", label: "Presentation", desc: "Creates the pitch", color: "#00b5d8" },
];

const STATUS_DISPLAY: Record<string, { label: string; color: string }> = {
  completed: { label: "Completed", color: "#0bbf8c" },
  ba_review: { label: "BA Review", color: "#f5a623" },
  research_review: { label: "Research Review", color: "#f5a623" },
  architect_review: { label: "Architect Review", color: "#f5a623" },
  engineer_review: { label: "Engineer Review", color: "#f5a623" },
  ba_working: { label: "BA Working", color: "#635bff" },
  research_working: { label: "Researching", color: "#635bff" },
  architect_working: { label: "Architecting", color: "#635bff" },
  engineer_working: { label: "Engineering", color: "#635bff" },
  ppt_working: { label: "Presenting", color: "#635bff" },
  created: { label: "Starting", color: "#8898aa" },
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

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-2xl w-full">
          {/* Title */}
          <div className="text-center mb-10 animate-fade-in">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium mb-6"
                 style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", display: "inline-block" }} />
              6 AI agents ready to work
            </div>
            <h1 className="text-5xl font-bold mb-4 tracking-tight" style={{ color: "var(--text-primary)" }}>
              AI Software Company
            </h1>
            <p className="text-lg" style={{ color: "var(--text-muted)" }}>
              Paste a problem. Your AI team builds the product.
            </p>
          </div>

          {/* Input Card */}
          <div className="card p-6 animate-fade-in" style={{ animationDelay: "0.1s" }}>
            <label className="block text-sm font-medium mb-2" style={{ color: "var(--text-secondary)" }}>
              What do you want to build?
            </label>
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="Build a real-time collaboration tool for remote teams with video chat, shared whiteboards, and task tracking..."
              className="w-full h-36 rounded-xl p-4 text-[15px] leading-relaxed resize-none focus:outline-none transition-all"
              style={{
                background: "var(--bg-base)",
                border: "1px solid var(--border)",
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

            <div className="flex items-center gap-3 mt-4">
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
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-3">
                    <span className="spinner" style={{ borderTopColor: "white", borderColor: "rgba(255,255,255,0.3)" }} />
                    Starting your AI team...
                  </span>
                ) : (
                  <>{ROUTE_CONFIG[activeRoute]?.icon} Start {ROUTE_CONFIG[activeRoute]?.name || "Company"}{autoApprove ? " (Auto-pilot)" : ""}</>
                )}
              </button>
              {hasDemo && onLoadDemo && (
                <button
                  onClick={onLoadDemo}
                  disabled={loading}
                  className="btn-ghost text-[15px] px-5"
                  style={{ borderColor: "var(--success-border)", color: "var(--success)" }}
                >
                  Demo Mode
                </button>
              )}
            </div>
          </div>

          {/* Recent Projects */}
          {recentProjects && recentProjects.length > 0 && (
            <div className="mt-6 animate-fade-in" style={{ animationDelay: "0.15s" }}>
              <h3 className="text-xs font-medium uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>
                Recent Projects
              </h3>
              <div className="space-y-2">
                {recentProjects.map((p) => {
                  const statusInfo = STATUS_DISPLAY[p.status] || { label: p.status, color: "#8898aa" };
                  return (
                    <Link
                      key={p.id}
                      href={`/project/${p.id}`}
                      className="card card-hover flex items-center justify-between p-4 transition-all block"
                      style={{ borderRadius: 12, textDecoration: "none" }}
                    >
                      <span className="text-sm truncate mr-4" style={{ color: "var(--text-secondary)" }}>
                        {p.problem_statement.length > 80
                          ? p.problem_statement.slice(0, 80) + "..."
                          : p.problem_statement}
                      </span>
                      <span
                        className="status-badge shrink-0"
                        style={{ background: `${statusInfo.color}10`, color: statusInfo.color, border: `1px solid ${statusInfo.color}20` }}
                      >
                        {statusInfo.label}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {/* Agent Cards */}
          <div className="mt-10 grid grid-cols-3 gap-3 animate-fade-in" style={{ animationDelay: "0.2s" }}>
            {AGENTS.map((agent) => (
              <div
                key={agent.label}
                className="card p-4 text-center transition-all"
                style={{ cursor: "default" }}
              >
                <div className="text-2xl mb-2">{agent.icon}</div>
                <div className="text-sm font-semibold" style={{ color: agent.color }}>{agent.label}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{agent.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
