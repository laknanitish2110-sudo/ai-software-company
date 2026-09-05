"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import AgentCanvas from "./AgentCanvas";
import AgentIntrospection from "./AgentIntrospection";
import AgentOutputCard from "./AgentOutput";
import BuildStatus, { ValidationResult } from "./BuildStatus";
import CallEmployee from "./CallEmployee";
import CodePreview from "./CodePreview";
import GitHubPush from "./GitHubPush";
import VersionTimeline from "./VersionTimeline";
import QuickImprove from "./QuickImprove";
import ArchitectureDiagram from "./ArchitectureDiagram";
import LiveStreamPanel from "./LiveStreamPanel";
import { useToast } from "./Toast";
import { DashboardSkeleton } from "./Skeleton";
import { ProjectState, WSMessage, connectWebSocket, getProjectState, approveOutput, downloadCode, downloadPptx, downloadDocx, downloadWorkflow, downloadBundle, shareProject, getIntegrationStatus, getModelConfig, saveDemoCache, reviseAgent, generateShareLink, getPreviewStatus, stopPreview, ReconnectingWebSocket } from "@/lib/api";
import { STATUS_LABELS, AGENT_CONFIG, PIPELINE_ORDER, MODEL_LABELS, ROUTE_CONFIG, updateModelLabels } from "@/lib/constants";

interface Props {
  projectId: string;
}

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

function getStageInfo(status: string, routeAgents: string[]): { current: number; label: string } {
  if (status === "completed") {
    return { current: routeAgents.length + 1, label: "All Complete" };
  }
  const agent = STATUS_TO_AGENT[status];
  if (!agent) return { current: 0, label: status };
  const idx = routeAgents.indexOf(agent);
  if (idx < 0) return { current: 0, label: status };
  const isReview = status.includes("_review");
  const config = AGENT_CONFIG[agent];
  const label = config?.label || agent;
  return { current: idx + 1, label: isReview ? `${label} Review` : label };
}

function formatPipelineTime(seconds: number): string {
  if (seconds >= 3600) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function Dashboard({ projectId }: Props) {
  const [state, setState] = useState<ProjectState | null>(null);
  const [events, setEvents] = useState<{ type: string; message: string; time: string }[]>([]);
  const [activeTab, setActiveTab] = useState<"outputs" | "chat">("outputs");
  const [n8nConnected, setN8nConnected] = useState(false);
  const [sharing, setSharing] = useState<string | null>(null);
  const [shareMsg, setShareMsg] = useState<string | null>(null);
  const [streamingAgent, setStreamingAgent] = useState<string | null>(null);
  const [streamTokens, setStreamTokens] = useState(0);
  const [agentStartTime, setAgentStartTime] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [inspectingAgent, setInspectingAgent] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(true);
  const [showCodePreview, setShowCodePreview] = useState(false);
  const [showArchDiagram, setShowArchDiagram] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [pipelineElapsed, setPipelineElapsed] = useState(0);
  const [shareLink, setShareLink] = useState<string | null>(null);
  const [copyingLink, setCopyingLink] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [showGitHubPush, setShowGitHubPush] = useState(false);
  const [shipOpen, setShipOpen] = useState(false);
  const { toast } = useToast();

  const refreshState = useCallback(async () => {
    try {
      const s = await getProjectState(projectId);
      setState(s);
      if (s.memory?.final_validation_result) {
        try { setValidationResult(JSON.parse(s.memory.final_validation_result)); } catch {}
      }
      getPreviewStatus(projectId).then(p => {
        if (p.active && p.preview_url) setPreviewUrl(p.preview_url);
        else setPreviewUrl(null);
      }).catch(() => {});
    } catch {
      toast("warning", "Connection issue", "Could not refresh project state from the backend.");
    }
  }, [projectId]);

  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debouncedRefresh = useCallback(() => {
    if (refreshTimer.current) return;
    refreshTimer.current = setTimeout(() => {
      refreshTimer.current = null;
      refreshState();
    }, 1000);
  }, [refreshState]);

  useEffect(() => {
    getIntegrationStatus()
      .then((s) => setN8nConnected(s.n8n_connected))
      .catch(() => {});
    getModelConfig()
      .then((cfg) => updateModelLabels(cfg.agents))
      .catch(() => {});
  }, []);

  async function handleShare(type: "drive" | "sheets" | "email" | "all") {
    setSharing(type);
    setShareMsg(null);
    try {
      const res = await shareProject(projectId, type);
      setShareMsg(res.message);
    } catch (e: unknown) {
      setShareMsg(e instanceof Error ? e.message : "Share failed");
    } finally {
      setSharing(null);
      setTimeout(() => setShareMsg(null), 4000);
    }
  }

  useEffect(() => {
    refreshState();

    const ws = connectWebSocket(projectId, (msg: WSMessage) => {
      if (msg.type === "agent_stream") {
        setStreamTokens(msg.data.token_count || 0);
        if (msg.data.token) {
          setStreamText((prev) => {
            if (prev.length > 30000) return prev.slice(-20000) + msg.data.token;
            return prev + msg.data.token;
          });
        }
        return;
      }

      if (msg.type === "agent_started") {
        setStreamingAgent(msg.data.role || null);
        setStreamTokens(0);
        setStreamText("");
        setAgentStartTime(Date.now());
      }

      if (msg.type === "error") {
        toast("error", "Pipeline error", msg.data.message || "An agent encountered an error.");
      }

      if (msg.type === "approval_needed" || msg.type === "agent_completed" || msg.type === "project_completed") {
        setStreamingAgent(null);
        setStreamTokens(0);
        setStreamText("");
        setAgentStartTime(null);
      }

      if (msg.type === "sandbox_completed" && (msg.data as Record<string, unknown>).validation_result) {
        setValidationResult((msg.data as Record<string, unknown>).validation_result as ValidationResult);
      }

      if (msg.type === "sandbox_preview_ready" && (msg.data as Record<string, unknown>).preview_url) {
        setPreviewUrl((msg.data as Record<string, unknown>).preview_url as string);
      }

      setEvents((prev) => {
        const next = [
          ...prev,
          {
            type: msg.type,
            message: msg.data.message || msg.type,
            time: new Date().toLocaleTimeString(),
          },
        ];
        return next.length > 100 ? next.slice(-80) : next;
      });
      debouncedRefresh();
    }, (connected) => setWsConnected(connected));

    const pollInterval = setInterval(() => {
      refreshState();
    }, 8000);

    return () => {
      ws.close();
      clearInterval(pollInterval);
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [projectId, refreshState, debouncedRefresh]);

  async function handleApprove(outputId: string) {
    try {
      await approveOutput(projectId, outputId, true);
      refreshState();
    } catch {
      toast("error", "Approval failed", "Could not approve — backend may be restarting. Try again.");
    }
  }

  async function handleReject(outputId: string, feedback: string) {
    try {
      await approveOutput(projectId, outputId, false, feedback);
      refreshState();
    } catch {
      toast("error", "Rejection failed", "Could not send feedback — backend may be restarting. Try again.");
    }
  }

  async function handleRevise(role: string, feedback: string) {
    try {
      await reviseAgent(projectId, role, feedback);
      toast("success", "Revision started", `${role.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())} is reworking with your feedback.`);
      refreshState();
    } catch {
      toast("error", "Revision failed", "Could not start revision — backend may be restarting.");
    }
  }

  async function handleShareLink() {
    setCopyingLink(true);
    try {
      const { token } = await generateShareLink(projectId);
      const url = `${window.location.origin}/shared/${token}`;
      setShareLink(url);
      await navigator.clipboard.writeText(url);
      toast("success", "Link copied!", "Share this link with anyone — no login required.");
    } catch {
      toast("error", "Share failed", "Could not generate share link.");
    } finally {
      setCopyingLink(false);
    }
  }

  useEffect(() => {
    if (!agentStartTime) { setElapsed(0); return; }
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - agentStartTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [agentStartTime]);

  useEffect(() => {
    if (!state?.project?.created_at) return;
    const created = new Date(state.project.created_at).getTime();
    if (isNaN(created)) return;
    if (state.project.status === "completed") {
      const end = state.project.updated_at ? new Date(state.project.updated_at).getTime() : Date.now();
      setPipelineElapsed(Math.floor(((isNaN(end) ? Date.now() : end) - created) / 1000));
      return;
    }
    setPipelineElapsed(Math.floor((Date.now() - created) / 1000));
    const interval = setInterval(() => {
      setPipelineElapsed(Math.floor((Date.now() - created) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [state?.project?.created_at, state?.project?.status, state?.project?.updated_at]);

  if (!state?.project) {
    return <DashboardSkeleton />;
  }

  const { project, outputs, memory } = state;
  const pendingOutput = outputs.find((o) => o.status === "pending");
  const statusLabel = STATUS_LABELS[project.status] || project.status;
  const routeName = memory?.pipeline_route || "full";
  const routeAgents = ROUTE_CONFIG[routeName]?.agents || PIPELINE_ORDER;
  const routeInfo = ROUTE_CONFIG[routeName];
  const stageInfo = getStageInfo(project.status, routeAgents);
  const isAutoPilot = memory?.auto_approve === "true";

  function getPeerReview(role: string) {
    const key = `peer_review_${role}`;
    const raw = memory?.[key];
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  const isCompleted = project.status === "completed";
  const deliverableType = state.memory?.deliverable_type || "code";

  return (
    <div className="min-h-screen p-4 lg:p-6" style={{ maxWidth: 1400, margin: "0 auto" }}>
      {/* Connection banner */}
      {!wsConnected && (
        <div
          className="animate-fade-in"
          style={{
            background: "rgba(237,95,116,0.08)",
            border: "1px solid rgba(237,95,116,0.2)",
            borderRadius: 10,
            padding: "10px 16px",
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            gap: 10,
            fontSize: 13,
            color: "var(--danger)",
          }}
        >
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--danger)", flexShrink: 0 }} />
          <span>
            <strong>Disconnected</strong> — live updates paused. The backend may be down or restarting.
          </span>
        </div>
      )}

      {/* Compact Header */}
      <div className="mb-5 animate-fade-in">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-sm transition-colors" style={{ color: "var(--text-muted)" }}
                  onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}>
              ← HQ
            </Link>
            <span style={{ color: "var(--border)" }}>|</span>
            <h1 className="text-lg font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>Build Room</h1>
            {routeInfo && routeName !== "full" && (
              <span style={{
                fontSize: 10, padding: "2px 8px", borderRadius: 10,
                background: "var(--accent-bg)", color: "var(--accent)",
                border: "1px solid var(--accent-border)", fontWeight: 600,
              }}>
                {routeInfo.icon} {routeInfo.name}
              </span>
            )}
            {isAutoPilot && (
              <span style={{
                fontSize: 10, padding: "2px 8px", borderRadius: 10,
                background: "rgba(99,91,255,0.12)", color: "#7a73ff",
                border: "1px solid rgba(99,91,255,0.25)", fontWeight: 600,
              }}>
                Auto-pilot
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span
              className="status-badge text-xs"
              style={{
                background: isCompleted ? "var(--success-bg)" : "var(--accent-bg)",
                color: isCompleted ? "var(--success)" : "var(--accent)",
                border: `1px solid ${isCompleted ? "var(--success-border)" : "var(--accent-border)"}`,
              }}
            >
              {isCompleted && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", display: "inline-block" }} />}
              {statusLabel}
            </span>
            {pipelineElapsed > 0 && (
              <span style={{
                fontSize: 11, fontFamily: "monospace", color: "var(--text-muted)",
                padding: "2px 8px", borderRadius: 6, border: "1px solid var(--border)",
              }}>
                {formatPipelineTime(pipelineElapsed)}
              </span>
            )}
          </div>
        </div>
        <p className="text-sm mt-1 truncate" style={{ color: "var(--text-secondary)", maxWidth: 700 }}>{project.problem_statement}</p>
      </div>

      {/* ===== Two-column Build Room layout ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

        {/* LEFT COLUMN — Canvas + Stream + Outputs */}
        <div className="lg:col-span-8 space-y-5">
          {/* Agent Canvas */}
          <div className="animate-fade-in">
            <AgentCanvas
              status={project.status}
              outputs={outputs}
              streamingAgent={streamingAgent}
              streamTokens={streamTokens}
              elapsed={elapsed}
              onNodeClick={(role) => setInspectingAgent(role)}
            />
          </div>

          {/* Live Stream Panel */}
          {streamingAgent && (
            <div className="animate-fade-in">
              <LiveStreamPanel
                agentRole={streamingAgent}
                streamText={streamText}
                tokenCount={streamTokens}
                elapsed={elapsed}
              />
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-1 animate-fade-in">
            {(["outputs", "chat"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className="px-5 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer"
                style={{
                  background: activeTab === tab ? "var(--accent-bg)" : "transparent",
                  color: activeTab === tab ? "var(--accent)" : "var(--text-muted)",
                  border: activeTab === tab ? "1px solid var(--accent-border)" : "1px solid transparent",
                }}
              >
                {tab === "outputs" ? "Departments" : "Call Employee"}
              </button>
            ))}
          </div>

          {/* Outputs / Chat */}
          {activeTab === "outputs" ? (
            <div className="space-y-4">
              {outputs.length === 0 && (
                <div className="card p-10 text-center animate-fade-in">
                  <div className="text-4xl mb-4">
                    {streamingAgent ? "🔄" : "🏢"}
                  </div>
                  <div className="text-[15px] font-medium mb-1" style={{ color: "var(--text-primary)" }}>
                    {streamingAgent ? "Your AI team is working..." : "Assembling your team"}
                  </div>
                  <div className="text-sm mb-5" style={{ color: "var(--text-muted)" }}>
                    {streamingAgent
                      ? `${streamingAgent.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())} is preparing their deliverable`
                      : "The CEO is reviewing your problem statement"}
                  </div>
                  <div className="flex justify-center gap-2">
                    {routeAgents.map((role, i) => {
                      const config = AGENT_CONFIG[role];
                      const label = config?.label?.split(" ")[0] || role;
                      return (
                        <span
                          key={role}
                          className="text-xs px-2.5 py-1 rounded-full"
                          style={{
                            background: i === 0 && !streamingAgent ? "var(--accent-bg)" : "var(--bg-elevated)",
                            color: i === 0 && !streamingAgent ? "var(--accent)" : "var(--text-muted)",
                            border: `1px solid ${i === 0 && !streamingAgent ? "var(--accent-border)" : "var(--border)"}`,
                          }}
                        >
                          {label}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}
              {outputs.map((output, i) => (
                <div key={output.id} style={{ animationDelay: `${i * 0.05}s` }}>
                  <AgentOutputCard
                    role={output.role}
                    content={output.content as Record<string, unknown>}
                    status={output.status}
                    outputId={output.id}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    onRevise={handleRevise}
                    showActions={output.status === "pending" && output.id === pendingOutput?.id}
                    peerReview={getPeerReview(output.role)}
                  />
                </div>
              ))}

              {validationResult && (
                <div className="mt-4 animate-fade-in">
                  <BuildStatus validationResult={validationResult} />
                  {previewUrl && !isCompleted && (
                    <button onClick={() => setShowPreview(true)}
                            className="mt-2 btn-success text-sm py-2 px-4 flex items-center gap-2"
                            style={{ background: "#10b981", borderColor: "#059669" }}>
                      <span>🌐</span> Live Preview
                    </button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <CallEmployee projectId={projectId} />
          )}
        </div>

        {/* RIGHT COLUMN — Activity Feed + Pipeline + Ship */}
        <div className="lg:col-span-4 space-y-5">
          {/* Pipeline Progress (compact) */}
          <div className="card p-4 animate-fade-in">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Pipeline
              </span>
              <span style={{
                fontSize: 11, fontWeight: 700, fontFamily: "monospace",
                color: isCompleted ? "var(--success)" : "var(--accent)",
              }}>
                {isCompleted ? `${routeAgents.length}/${routeAgents.length}` : `${stageInfo.current}/${routeAgents.length}`}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
              {routeAgents.map((role, i) => {
                const config = AGENT_CONFIG[role];
                if (!config) return null;
                const isDone = stageInfo.current > i + 1;
                const isActive = stageInfo.current === i + 1 && !isCompleted;
                const isReview = isActive && project.status.includes("_review");
                return (
                  <div key={role} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                    <div style={{
                      height: 4, width: "100%", borderRadius: 2,
                      background: isDone ? "#0bbf8c" : isReview ? "#f5a623" : isActive ? config.color : "var(--border)",
                      opacity: isDone || isActive || isReview ? 0.8 : 0.15,
                      transition: "all 0.5s ease",
                    }} />
                    <span style={{
                      fontSize: 8, fontWeight: 600,
                      color: isDone ? "var(--success)" : isActive ? "var(--text-secondary)" : "var(--text-muted)",
                      opacity: isDone || isActive ? 1 : 0.4,
                    }}>
                      {config.icon}
                    </span>
                  </div>
                );
              })}
            </div>
            {!isCompleted && (
              <div style={{ marginTop: 8, fontSize: 11, color: "var(--text-secondary)" }}>
                {stageInfo.label}
              </div>
            )}
          </div>

          {/* Activity Feed */}
          <div className="card p-4 sticky top-6 animate-fade-in">
            <h3 className="font-semibold mb-3 text-xs uppercase tracking-wider flex items-center gap-2" style={{ color: "var(--text-muted)" }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%",
                background: streamingAgent ? "var(--accent)" : events.length > 0 ? "var(--success)" : "var(--border)",
                display: "inline-block",
              }} />
              Activity Feed
            </h3>
            <div className="space-y-1.5" style={{ maxHeight: 380, overflowY: "auto" }}>
              {events.length === 0 && (
                <div className="text-sm py-4 text-center" style={{ color: "var(--text-muted)" }}>Waiting for activity...</div>
              )}
              {events.slice(-30).reverse().map((event, i) => {
                const color =
                  event.type === "approval_needed" ? "var(--warning)"
                  : event.type === "agent_completed" || event.type === "project_completed" ? "var(--success)"
                  : event.type === "error" ? "var(--danger)"
                  : event.type === "peer_review_completed" ? "var(--accent)"
                  : event.type === "sandbox_started" || event.type === "sandbox_completed" ? "#f59e0b"
                  : event.type === "domain_memory" ? "#8b5cf6"
                  : event.type === "route_selected" ? "#6366f1"
                  : "var(--text-muted)";

                return (
                  <div
                    key={i}
                    className="flex gap-2 text-xs py-1.5 pl-3 animate-slide-in"
                    style={{ borderLeft: `2px solid ${color}` }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ color: "var(--text-secondary)", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{event.message}</div>
                      <div style={{ color: "var(--text-muted)", fontSize: 10 }}>{event.time}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Version Timeline */}
          <VersionTimeline
            events={events}
            projectStatus={project.status}
            createdAt={project.created_at}
          />

          {/* Quick Improve */}
          {isCompleted && (
            <QuickImprove
              projectId={projectId}
              onImprove={handleRevise}
            />
          )}

          {/* Ship Section (collapsible) */}
          {isCompleted && (
            <div className="card animate-fade-in" style={{ overflow: "hidden" }}>
              <button
                onClick={() => setShipOpen(!shipOpen)}
                className="w-full cursor-pointer"
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "12px 16px", background: "none", border: "none",
                  color: "var(--text-primary)", fontSize: 13, fontWeight: 600,
                }}
              >
                <span className="flex items-center gap-2">
                  <span style={{ fontSize: 14 }}>🚀</span> Ship & Share
                </span>
                <span style={{
                  transform: shipOpen ? "rotate(180deg)" : "rotate(0)",
                  transition: "transform 0.2s", fontSize: 12, color: "var(--text-muted)",
                }}>▼</span>
              </button>
              {shipOpen && (
                <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
                  {(!deliverableType || deliverableType === "code" || deliverableType === "hybrid") && (
                    <button onClick={async () => {
                      try { await downloadCode(projectId); } catch (e) { toast("error", "Download failed", e instanceof Error ? e.message : "Could not download code."); }
                    }}
                      className="btn-success text-xs py-2 px-4 flex items-center gap-2 w-full justify-center">
                      <span>📦</span> Download Code (.zip)
                    </button>
                  )}
                  {(!deliverableType || deliverableType === "code" || deliverableType === "hybrid") && validationResult?.final_status === "VALIDATED" && (
                    <button onClick={async () => {
                      try { await downloadBundle(projectId); } catch (e) { toast("warning", "Not available", e instanceof Error ? e.message : "No deployable bundle found."); }
                    }}
                      className="btn-success text-xs py-2 px-4 flex items-center gap-2 w-full justify-center"
                      style={{ background: "#8b5cf6", borderColor: "#7c3aed" }}>
                      <span>🚀</span> Deployable Bundle
                    </button>
                  )}
                  {(deliverableType === "workflow" || deliverableType === "hybrid") && (
                    <button onClick={async () => {
                      try { await downloadWorkflow(projectId); } catch (e) { toast("warning", "Not available", e instanceof Error ? e.message : "Workflow not found."); }
                    }}
                      className="btn-success text-xs py-2 px-4 flex items-center gap-2 w-full justify-center"
                      style={{ background: "var(--accent)", borderColor: "var(--accent-border)" }}>
                      <span>⚡</span> n8n Workflow
                    </button>
                  )}
                  <div className="flex gap-2">
                    <button onClick={async () => {
                      try { await downloadPptx(projectId); } catch (e) { toast("error", "Download failed", e instanceof Error ? e.message : "Could not download presentation."); }
                    }}
                      className="btn-primary text-xs py-2 px-3 flex items-center gap-1.5 flex-1 justify-center">
                      <span>📊</span> PPTX
                    </button>
                    <button onClick={async () => {
                      try { await downloadDocx(projectId); } catch (e) { toast("error", "Download failed", e instanceof Error ? e.message : "Could not download report."); }
                    }}
                      className="btn-ghost text-xs py-2 px-3 flex items-center gap-1.5 flex-1 justify-center">
                      <span>📄</span> DOCX
                    </button>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={async () => {
                      try {
                        await saveDemoCache(projectId);
                        toast("success", "Demo saved", "You can now use Demo Mode from the start page.");
                      } catch { toast("error", "Save failed", "Could not save demo cache."); }
                    }}
                      className="btn-ghost text-xs py-2 px-3 flex items-center gap-1.5 flex-1 justify-center"
                      style={{ borderColor: "var(--warning-border)", color: "var(--warning)" }}>
                      <span>💾</span> Demo
                    </button>
                    <button
                      onClick={handleShareLink}
                      disabled={copyingLink}
                      className="btn-ghost text-xs py-2 px-3 flex items-center gap-1.5 flex-1 justify-center"
                      style={{ borderColor: "rgba(99,91,255,0.4)", color: "#635bff" }}
                    >
                      {copyingLink ? <span className="spinner" style={{ width: 12, height: 12 }} /> : <span>🔗</span>}
                      {shareLink ? "Copied!" : "Share"}
                    </button>
                  </div>
                  {(!deliverableType || deliverableType === "code" || deliverableType === "hybrid") && (
                    <div className="flex gap-2">
                      <button onClick={() => setShowCodePreview(true)}
                        className="btn-ghost text-xs py-2 px-3 flex items-center gap-1.5 flex-1 justify-center"
                        style={{ borderColor: "var(--accent-border)", color: "var(--accent)" }}>
                        <span>👁️</span> View Code
                      </button>
                      <button onClick={() => setShowGitHubPush(true)}
                        className="btn-ghost text-xs py-2 px-3 flex items-center gap-1.5 flex-1 justify-center"
                        style={{ borderColor: "rgba(36,41,47,0.4)", color: "var(--text-primary)" }}>
                        <span>🐙</span> GitHub
                      </button>
                    </div>
                  )}
                  {previewUrl && (
                    <button onClick={() => setShowPreview(true)}
                      className="btn-success text-xs py-2 px-4 flex items-center gap-2 w-full justify-center"
                      style={{ background: "#10b981", borderColor: "#059669" }}>
                      <span>🌐</span> Live Preview
                    </button>
                  )}
                  {outputs.find((o) => o.role === "architect") && (
                    <button onClick={() => setShowArchDiagram(true)}
                      className="btn-ghost text-xs py-2 px-3 flex items-center gap-1.5 w-full justify-center"
                      style={{ borderColor: "rgba(139,92,246,0.4)", color: "#8b5cf6" }}>
                      <span>🏗️</span> Architecture Diagram
                    </button>
                  )}

                  {/* n8n Share row */}
                  <div style={{ borderTop: "1px solid var(--border)", paddingTop: 8, marginTop: 4 }}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-[9px] font-medium uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                        n8n
                      </span>
                      <span style={{
                        fontSize: 9, padding: "1px 6px", borderRadius: 8,
                        background: n8nConnected ? "var(--success-bg)" : "var(--bg-elevated)",
                        color: n8nConnected ? "var(--success)" : "var(--text-muted)",
                        border: `1px solid ${n8nConnected ? "var(--success-border)" : "var(--border)"}`,
                      }}>
                        {n8nConnected ? "On" : "Off"}
                      </span>
                    </div>
                    <div className="flex gap-1.5 flex-wrap">
                      {(["drive", "sheets", "email", "all"] as const).map((t) => (
                        <button
                          key={t}
                          onClick={() => handleShare(t)}
                          disabled={!n8nConnected || sharing !== null}
                          className="btn-ghost text-[10px] py-1.5 px-2.5 flex items-center gap-1"
                        >
                          {sharing === t ? <span className="spinner" style={{ width: 10, height: 10 }} /> :
                            t === "drive" ? "📁" : t === "sheets" ? "📊" : t === "email" ? "📧" : "🚀"}
                          {t === "drive" ? "Drive" : t === "sheets" ? "Sheets" : t === "email" ? "Email" : "All"}
                        </button>
                      ))}
                    </div>
                    {shareMsg && (
                      <div className="mt-1.5 text-[10px] animate-fade-in" style={{ color: "var(--text-secondary)" }}>
                        {shareMsg}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {inspectingAgent && (
        <AgentIntrospection
          projectId={projectId}
          role={inspectingAgent}
          onClose={() => setInspectingAgent(null)}
        />
      )}

      {showPreview && previewUrl && (
        <div className="card animate-fade-in" style={{ padding: 0, overflow: "hidden", marginBottom: 16 }}>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "10px 16px", borderBottom: "1px solid var(--border)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--success)", animation: "pulse 2s infinite" }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Live Preview</span>
              <a href={previewUrl} target="_blank" rel="noopener noreferrer"
                 style={{ fontSize: 11, color: "var(--accent)", textDecoration: "none" }}>
                Open in new tab ↗
              </a>
            </div>
            <button onClick={async () => {
              setShowPreview(false);
              try { await stopPreview(projectId); } catch {}
              setPreviewUrl(null);
            }}
              style={{ fontSize: 12, color: "var(--danger)", background: "none", border: "none", cursor: "pointer", fontWeight: 500 }}>
              Stop Preview
            </button>
          </div>
          <iframe src={previewUrl} style={{ width: "100%", height: 500, border: "none" }}
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups" />
        </div>
      )}

      {showCodePreview && (
        <CodePreview
          projectId={projectId}
          onClose={() => setShowCodePreview(false)}
        />
      )}

      {showGitHubPush && (
        <GitHubPush
          projectId={projectId}
          problemStatement={project.problem_statement}
          onClose={() => setShowGitHubPush(false)}
        />
      )}

      {showArchDiagram && (() => {
        const archOutput = outputs.find((o) => o.role === "architect");
        if (!archOutput) return null;
        return (
          <ArchitectureDiagram
            architectOutput={archOutput.content as Record<string, unknown>}
            onClose={() => setShowArchDiagram(false)}
          />
        );
      })()}
    </div>
  );
}
