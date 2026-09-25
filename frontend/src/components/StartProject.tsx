"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import Link from "next/link";
import { ROUTE_CONFIG, classifyTask, AGENT_CONFIG, getRouteGuardrail } from "@/lib/constants";
import { getActivityFeed, markActivitySeen, type ActivityItem } from "@/lib/api";

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
  onDeleteProject?: (id: string) => Promise<void>;
  onRenameProject?: (id: string, name: string) => Promise<void>;
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

const PIPELINE_AGENTS = [
  { icon: "👨‍💼", label: "CEO", color: "#635bff" },
  { icon: "📋", label: "BA", color: "#0bbf8c" },
  { icon: "🔍", label: "Researcher", color: "#f5a623" },
  { icon: "🏗️", label: "Architect", color: "#5e81f4" },
  { icon: "💻", label: "Engineer", color: "#ed5f74" },
  { icon: "📊", label: "Presenter", color: "#00b5d8" },
];

const TEAM_EMPLOYEES = [
  { icon: "🏗️", label: "Arc", color: "#8b5cf6" },
  { icon: "📋", label: "Sage", color: "#0bbf8c" },
  { icon: "🔍", label: "Scout", color: "#3b82f6" },
  { icon: "⚡", label: "Atlas", color: "#f59e0b" },
  { icon: "🛡️", label: "Sentinel", color: "#ef4444" },
  { icon: "✍️", label: "Scribe", color: "#06b6d4" },
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

function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function StartProject({ onStart, loading, recentProjects, hasDemo, onLoadDemo, onDeleteProject, onRenameProject }: Props) {
  const [problem, setProblem] = useState("");
  const [autoApprove, setAutoApprove] = useState(false);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [unseenCount, setUnseenCount] = useState(0);
  const [activityDismissed, setActivityDismissed] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState<string>("all");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadActivity = useCallback(async () => {
    try {
      const data = await getActivityFeed(20, true);
      setActivities(data.activities);
      setUnseenCount(data.unseen_count);
    } catch {}
  }, []);

  useEffect(() => { loadActivity(); }, [loadActivity]);

  const handleDismissActivity = async () => {
    try {
      await markActivitySeen();
      setActivityDismissed(true);
      setUnseenCount(0);
    } catch {}
  };

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
            <p className="text-base" style={{ color: "var(--text-muted)", maxWidth: 480, margin: "0 auto" }}>
              Two ways to work with your AI company
            </p>
          </div>

          {/* Two Mode Cards */}
          <div className="mode-grid grid gap-4 mb-8 animate-fade-in" style={{ gridTemplateColumns: "1fr 1fr", animationDelay: "0.05s" }}>
            {/* Pipeline Mode */}
            <div
              className="rounded-2xl p-5 transition-all"
              style={{
                background: "var(--bg-card)",
                border: "1.5px solid var(--accent)",
                boxShadow: "0 0 20px rgba(99,91,255,0.08)",
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span style={{ fontSize: 18 }}>&#9889;</span>
                <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>Build a Project</span>
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded ml-auto uppercase tracking-wider"
                      style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)" }}>
                  Pipeline
                </span>
              </div>
              <p className="text-xs mb-3" style={{ color: "var(--text-muted)", lineHeight: 1.5 }}>
                Describe an idea &mdash; 6 agents build it end-to-end in one shot. From analysis to working code to pitch deck.
              </p>
              <div className="flex items-center gap-0">
                {PIPELINE_AGENTS.map((a, i) => (
                  <div key={a.label} className="flex items-center">
                    <div className="flex flex-col items-center" style={{ minWidth: 44 }}>
                      <span style={{ fontSize: 16 }}>{a.icon}</span>
                      <span className="text-[9px] font-semibold" style={{ color: a.color }}>{a.label}</span>
                    </div>
                    {i < PIPELINE_AGENTS.length - 1 && (
                      <span className="text-xs font-bold" style={{ color: "var(--accent)", opacity: 0.6, margin: "0 2px" }}>&rarr;</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Team Mode */}
            <Link
              href="/employees"
              className="rounded-2xl p-5 transition-all"
              style={{
                background: "var(--bg-card)",
                border: "1.5px solid var(--border)",
                textDecoration: "none",
                display: "block",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "#0bbf8c";
                e.currentTarget.style.boxShadow = "0 0 20px rgba(11,191,140,0.08)";
                e.currentTarget.style.transform = "translateY(-2px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.boxShadow = "none";
                e.currentTarget.style.transform = "translateY(0)";
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span style={{ fontSize: 18 }}>&#129302;</span>
                <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>Your Team</span>
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded ml-auto uppercase tracking-wider"
                      style={{ background: "rgba(11,191,140,0.08)", color: "#0bbf8c", border: "1px solid rgba(11,191,140,0.2)" }}>
                  Employees
                </span>
              </div>
              <p className="text-xs mb-3" style={{ color: "var(--text-muted)", lineHeight: 1.5 }}>
                Chat with persistent AI employees who learn from every conversation, remember context, and collaborate via delegation.
              </p>
              <div className="flex items-center gap-1">
                {TEAM_EMPLOYEES.map((e) => (
                  <div key={e.label} className="flex flex-col items-center" style={{ minWidth: 44 }}>
                    <span style={{ fontSize: 16 }}>{e.icon}</span>
                    <span className="text-[9px] font-semibold" style={{ color: e.color }}>{e.label}</span>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-1 mt-3 text-xs font-medium" style={{ color: "#0bbf8c" }}>
                Chat with your team
                <span>&rarr;</span>
              </div>
            </Link>
          </div>

          {/* While You Were Away */}
          {!activityDismissed && activities.length > 0 && (
            <div className="card p-4 mb-6 animate-fade-in" style={{ animationDelay: "0.08s", border: "1.5px solid var(--accent-border)" }}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span style={{ fontSize: 14 }}>&#128276;</span>
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-primary)" }}>
                    While you were away
                  </span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                        style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-border)", minWidth: 20, textAlign: "center" }}>
                    {unseenCount}
                  </span>
                </div>
                <button
                  onClick={handleDismissActivity}
                  className="text-[10px] font-medium px-2 py-1 rounded-md transition-all"
                  style={{ color: "var(--text-muted)", background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent-border)"; e.currentTarget.style.color = "var(--accent)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}
                >
                  Dismiss all
                </button>
              </div>
              <div className="space-y-1.5" style={{ maxHeight: 200, overflowY: "auto" }}>
                {activities.map((a) => {
                  const eventConfig: Record<string, { icon: string; color: string }> = {
                    delegation_completed: { icon: "✅", color: "#0bbf8c" },
                    session_completed: { icon: "💬", color: "#635bff" },
                    skill_learned: { icon: "✨", color: "#f5a623" },
                  };
                  const cfg = eventConfig[a.event_type] || { icon: "•", color: "var(--text-muted)" };
                  const timeAgo = formatTimeAgo(a.created_at);
                  return (
                    <div key={a.id} className="flex items-start gap-2.5 px-2.5 py-2 rounded-lg" style={{ background: "var(--bg-elevated)" }}>
                      <span style={{ fontSize: 13, lineHeight: "18px" }}>{cfg.icon}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          {a.employee_name && (
                            <span className="text-[11px] font-bold" style={{ color: cfg.color }}>{a.employee_name}</span>
                          )}
                          <span className="text-[11px]" style={{ color: "var(--text-secondary)" }}>{a.title.replace(a.employee_name || "", "").trim()}</span>
                        </div>
                        {a.detail && (
                          <p className="text-[10px] mt-0.5 truncate" style={{ color: "var(--text-muted)", maxWidth: 400 }}>
                            {a.detail.length > 120 ? a.detail.slice(0, 120) + "..." : a.detail}
                          </p>
                        )}
                      </div>
                      <span className="text-[10px] shrink-0 mt-0.5" style={{ color: "var(--text-muted)" }}>{timeAgo}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

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

          {/* Project Management */}
          {recentProjects && recentProjects.length > 0 && (() => {
            const filtered = recentProjects.filter((p) => {
              if (projectFilter !== "all") {
                if (projectFilter === "active" && p.status === "completed") return false;
                if (projectFilter === "completed" && p.status !== "completed") return false;
              }
              if (projectSearch.trim()) {
                return p.problem_statement.toLowerCase().includes(projectSearch.toLowerCase());
              }
              return true;
            });
            return (
              <div className="mt-8 animate-fade-in" style={{ animationDelay: "0.15s" }}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                    Your Projects
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-elevated)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                    {recentProjects.length} total
                  </span>
                </div>

                {/* Search + filter bar */}
                <div className="flex gap-2 mb-3">
                  <input
                    type="text"
                    placeholder="Search projects..."
                    value={projectSearch}
                    onChange={(e) => setProjectSearch(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-lg text-xs"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)", outline: "none" }}
                  />
                  {(["all", "active", "completed"] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => setProjectFilter(f)}
                      className="px-3 py-1.5 rounded-lg text-[11px] font-semibold capitalize"
                      style={{
                        background: projectFilter === f ? "var(--accent-bg)" : "var(--bg-elevated)",
                        color: projectFilter === f ? "var(--accent)" : "var(--text-muted)",
                        border: `1px solid ${projectFilter === f ? "var(--accent-border)" : "var(--border)"}`,
                        cursor: "pointer",
                      }}
                    >{f}</button>
                  ))}
                </div>

                <div className="space-y-2">
                  {filtered.map((p) => {
                    const statusInfo = STATUS_DISPLAY[p.status] || { label: p.status, color: "#8898aa", icon: "⚪" };
                    const isEditing = editingId === p.id;
                    const isDeleting = confirmDeleteId === p.id;
                    return (
                      <div
                        key={p.id}
                        className="flex items-center gap-3 p-4 rounded-xl transition-all"
                        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}
                      >
                        <span className="text-sm shrink-0">{statusInfo.icon}</span>
                        {isEditing ? (
                          <input
                            autoFocus
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            onKeyDown={async (e) => {
                              if (e.key === "Enter" && editName.trim()) {
                                await onRenameProject?.(p.id, editName.trim());
                                setEditingId(null);
                              }
                              if (e.key === "Escape") setEditingId(null);
                            }}
                            onBlur={() => setEditingId(null)}
                            className="flex-1 text-sm px-2 py-1 rounded"
                            style={{ background: "var(--bg-base)", border: "1px solid var(--accent)", color: "var(--text-primary)", outline: "none" }}
                          />
                        ) : (
                          <Link
                            href={`/project/${p.id}`}
                            className="text-sm truncate flex-1"
                            style={{ color: "var(--text-secondary)", textDecoration: "none" }}
                          >
                            {p.problem_statement.length > 60 ? p.problem_statement.slice(0, 60) + "..." : p.problem_statement}
                          </Link>
                        )}
                        <span
                          className="text-[10px] font-semibold px-2 py-1 rounded-md shrink-0"
                          style={{ background: `${statusInfo.color}12`, color: statusInfo.color, border: `1px solid ${statusInfo.color}20` }}
                        >{statusInfo.label}</span>

                        {/* Actions */}
                        {!isEditing && !isDeleting && (
                          <div className="flex gap-1 shrink-0">
                            <button
                              onClick={() => { setEditingId(p.id); setEditName(p.problem_statement); }}
                              title="Rename"
                              className="p-1.5 rounded-md"
                              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", fontSize: 12 }}
                              onMouseEnter={(e) => e.currentTarget.style.color = "var(--accent)"}
                              onMouseLeave={(e) => e.currentTarget.style.color = "var(--text-muted)"}
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                              </svg>
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(p.id)}
                              title="Delete"
                              className="p-1.5 rounded-md"
                              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", fontSize: 12 }}
                              onMouseEnter={(e) => e.currentTarget.style.color = "var(--danger)"}
                              onMouseLeave={(e) => e.currentTarget.style.color = "var(--text-muted)"}
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                              </svg>
                            </button>
                          </div>
                        )}
                        {isDeleting && (
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[11px]" style={{ color: "var(--danger)" }}>Delete?</span>
                            <button
                              onClick={async () => { await onDeleteProject?.(p.id); setConfirmDeleteId(null); }}
                              className="text-[11px] font-semibold px-2 py-1 rounded"
                              style={{ background: "rgba(237,95,116,0.1)", color: "var(--danger)", border: "none", cursor: "pointer" }}
                            >Yes</button>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              className="text-[11px] font-semibold px-2 py-1 rounded"
                              style={{ background: "var(--bg-elevated)", color: "var(--text-muted)", border: "none", cursor: "pointer" }}
                            >No</button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {filtered.length === 0 && (
                    <div className="text-center py-6 text-xs" style={{ color: "var(--text-muted)" }}>
                      No projects match your search
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* Footer */}
      <div className="text-center py-6">
        <p className="text-[11px]" style={{ color: "var(--text-muted)", opacity: 0.5 }}>
          Pipeline: CEO &rarr; BA &rarr; Researcher &rarr; Architect &rarr; Engineer &rarr; Presenter
          &nbsp;&nbsp;|&nbsp;&nbsp;
          Team: Arc &bull; Sage &bull; Scout &bull; Atlas &bull; Sentinel &bull; Scribe
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
        @media (max-width: 640px) {
          .mode-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
