"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import AgentCanvas from "./AgentCanvas";
import AgentIntrospection from "./AgentIntrospection";
import AgentOutputCard from "./AgentOutput";
import CallEmployee from "./CallEmployee";
import CodePreview from "./CodePreview";
import ArchitectureDiagram from "./ArchitectureDiagram";
import LiveStreamPanel from "./LiveStreamPanel";
import { useToast } from "./Toast";
import { DashboardSkeleton } from "./Skeleton";
import { ProjectState, WSMessage, connectWebSocket, getProjectState, approveOutput, downloadCode, downloadPptx, downloadDocx, downloadWorkflow, shareProject, getIntegrationStatus, saveDemoCache, reviseAgent, generateShareLink, ReconnectingWebSocket } from "@/lib/api";
import { STATUS_LABELS, AGENT_CONFIG, PIPELINE_ORDER, MODEL_LABELS, ROUTE_CONFIG } from "@/lib/constants";

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
  const { toast } = useToast();

  const refreshState = useCallback(async () => {
    try {
      const s = await getProjectState(projectId);
      setState(s);
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
    <div className="min-h-screen p-6 max-w-6xl mx-auto">
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

      {/* Header */}
      <div className="mb-6 animate-fade-in">
        <div className="flex items-center gap-3 mb-1">
          <Link href="/" className="text-sm transition-colors" style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}>
            ← Back
          </Link>
        </div>
        <div className="flex items-center justify-between mb-2 mt-3">
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>AI Software Company</h1>
          <span
            className="status-badge text-sm"
            style={{
              background: isCompleted ? "var(--success-bg)" : "var(--accent-bg)",
              color: isCompleted ? "var(--success)" : "var(--accent)",
              border: `1px solid ${isCompleted ? "var(--success-border)" : "var(--accent-border)"}`,
            }}
          >
            {isCompleted && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", display: "inline-block" }} />}
            {statusLabel}
          </span>
        </div>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{project.problem_statement}</p>

        {/* Pipeline Progress */}
        <div className="mt-4 animate-fade-in" style={{
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: "14px 20px",
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Pipeline
              </span>
              {routeInfo && routeName !== "full" && (
                <span style={{
                  fontSize: 10,
                  padding: "2px 8px",
                  borderRadius: 10,
                  background: "var(--accent-bg)",
                  color: "var(--accent)",
                  border: "1px solid var(--accent-border)",
                  fontWeight: 600,
                  letterSpacing: "0.02em",
                }}>
                  {routeInfo.icon} {routeInfo.name}
                </span>
              )}
              {isAutoPilot && (
                <span style={{
                  fontSize: 10,
                  padding: "2px 8px",
                  borderRadius: 10,
                  background: "rgba(99,91,255,0.12)",
                  color: "#7a73ff",
                  border: "1px solid rgba(99,91,255,0.25)",
                  fontWeight: 600,
                  letterSpacing: "0.02em",
                }}>
                  Auto-pilot
                </span>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 500 }}>
                {isCompleted ? "Complete" : stageInfo.label}
              </span>
              <span style={{
                fontSize: 12, fontWeight: 700, fontFamily: "monospace",
                color: isCompleted ? "var(--success)" : "var(--accent)",
              }}>
                {isCompleted ? `${routeAgents.length}/${routeAgents.length}` : `${stageInfo.current}/${routeAgents.length}`}
              </span>
              {pipelineElapsed > 0 && (
                <span style={{
                  fontSize: 11, fontFamily: "monospace",
                  color: "var(--text-muted)",
                  padding: "2px 8px",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                }}>
                  {formatPipelineTime(pipelineElapsed)}
                </span>
              )}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center" }}>
            {routeAgents.flatMap((role, i) => {
              const config = AGENT_CONFIG[role];
              if (!config) return [];
              const isDone = stageInfo.current > i + 1;
              const isActive = stageInfo.current === i + 1 && !isCompleted;
              const isReview = isActive && project.status.includes("_review");
              const dotBorder = isDone ? "#0bbf8c" : isReview ? "#f5a623" : isActive ? config.color : "var(--border)";
              const dotBg = isDone ? "rgba(11,191,140,0.12)" : isReview ? "rgba(245,166,35,0.12)" : isActive ? `${config.color}15` : "transparent";

              if (i > 0) {
                return [
                  <div key={`line-${i}`} style={{
                    flex: 1, height: 2,
                    background: isDone ? "#0bbf8c" : isActive ? `linear-gradient(90deg, #0bbf8c, ${dotBorder})` : "var(--border)",
                    opacity: isDone || isActive ? 0.6 : 0.15,
                    transition: "all 0.5s ease",
                  }} />,
                  <div key={role} title={config.label} style={{
                    width: 30, height: 30, borderRadius: "50%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    background: dotBg, border: `2px solid ${dotBorder}`,
                    transition: "all 0.3s ease", flexShrink: 0,
                  }}>
                    {isDone
                      ? <span style={{ color: "#0bbf8c", fontSize: 11, fontWeight: 700 }}>✓</span>
                      : <span style={{ fontSize: 14 }}>{config.icon}</span>}
                  </div>,
                ];
              }
              return [
                <div key={role} title={config.label} style={{
                  width: 30, height: 30, borderRadius: "50%",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: dotBg, border: `2px solid ${dotBorder}`,
                  transition: "all 0.3s ease", flexShrink: 0,
                }}>
                  {isDone
                    ? <span style={{ color: "#0bbf8c", fontSize: 11, fontWeight: 700 }}>✓</span>
                    : <span style={{ fontSize: 14 }}>{config.icon}</span>}
                </div>,
              ];
            })}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, padding: "0 2px" }}>
            {routeAgents.map((role, idx) => {
              const config = AGENT_CONFIG[role];
              if (!config) return null;
              const modelInfo = MODEL_LABELS[role];
              const isDone = stageInfo.current > idx + 1;
              const isActive = stageInfo.current === idx + 1 && !isCompleted;
              return (
                <div key={role} style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 56 }}>
                  <span style={{
                    fontSize: 9, fontWeight: 600,
                    color: isDone ? "var(--success)" : isActive ? "var(--text-secondary)" : "var(--text-muted)",
                    opacity: isDone || isActive ? 1 : 0.4,
                  }}>
                    {config.label.split(" ")[0]}
                  </span>
                  {modelInfo && (
                    <span style={{
                      fontSize: 8, fontWeight: 500, marginTop: 2,
                      color: modelInfo.providerColor,
                      opacity: isDone || isActive ? 0.8 : 0.3,
                      whiteSpace: "nowrap",
                    }}>
                      {modelInfo.model}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Download Buttons */}
        {isCompleted && (
          <div className="flex gap-3 mt-5 flex-wrap animate-fade-in">
            {(!deliverableType || deliverableType === "code" || deliverableType === "hybrid") && (
              <button onClick={async () => {
                try { await downloadCode(projectId); } catch (e) { toast("error", "Download failed", e instanceof Error ? e.message : "Could not download code."); }
              }}
                      className="btn-success text-sm py-2.5 px-5 flex items-center gap-2">
                <span>📦</span> Download Code (.zip)
              </button>
            )}
            {(deliverableType === "workflow" || deliverableType === "hybrid") && (
              <button onClick={async () => {
                try { await downloadWorkflow(projectId); } catch (e) { toast("warning", "Not available", e instanceof Error ? e.message : "Workflow not found."); }
              }}
                      className="btn-success text-sm py-2.5 px-5 flex items-center gap-2"
                      style={{ background: "var(--accent)", borderColor: "var(--accent-border)" }}>
                <span>⚡</span> n8n Workflow (.json)
              </button>
            )}
            <button onClick={async () => {
              try { await downloadPptx(projectId); } catch (e) { toast("error", "Download failed", e instanceof Error ? e.message : "Could not download presentation."); }
            }}
                    className="btn-primary text-sm py-2.5 px-5 flex items-center gap-2">
              <span>📊</span> Presentation (.pptx)
            </button>
            <button onClick={async () => {
              try { await downloadDocx(projectId); } catch (e) { toast("error", "Download failed", e instanceof Error ? e.message : "Could not download report."); }
            }}
                    className="btn-ghost text-sm py-2.5 px-5 flex items-center gap-2">
              <span>📄</span> Report (.docx)
            </button>
            <button onClick={async () => {
              try {
                await saveDemoCache(projectId);
                toast("success", "Demo saved", "You can now use Demo Mode from the start page.");
              } catch { toast("error", "Save failed", "Could not save demo cache."); }
            }}
                    className="btn-ghost text-sm py-2.5 px-5 flex items-center gap-2"
                    style={{ borderColor: "var(--warning-border)", color: "var(--warning)" }}>
              <span>💾</span> Save as Demo
            </button>
            {(!deliverableType || deliverableType === "code" || deliverableType === "hybrid") && (
              <button onClick={() => setShowCodePreview(true)}
                      className="btn-ghost text-sm py-2.5 px-5 flex items-center gap-2"
                      style={{ borderColor: "var(--accent-border)", color: "var(--accent)" }}>
                <span>👁️</span> View Code in Browser
              </button>
            )}
            {outputs.find((o) => o.role === "architect") && (
              <button onClick={() => setShowArchDiagram(true)}
                      className="btn-ghost text-sm py-2.5 px-5 flex items-center gap-2"
                      style={{ borderColor: "rgba(139,92,246,0.4)", color: "#8b5cf6" }}>
                <span>🏗️</span> Architecture Diagram
              </button>
            )}
            <button
              onClick={handleShareLink}
              disabled={copyingLink}
              className="btn-ghost text-sm py-2.5 px-5 flex items-center gap-2"
              style={{ borderColor: "rgba(99,91,255,0.4)", color: "#635bff" }}
            >
              {copyingLink ? (
                <span className="spinner" style={{ width: 14, height: 14 }} />
              ) : (
                <span>🔗</span>
              )}
              {shareLink ? "Link Copied!" : "Share Link"}
            </button>
          </div>
        )}

        {/* Share Buttons */}
        {isCompleted && (
          <div className="mt-3 animate-fade-in">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                Share via n8n
              </span>
              <span
                className="status-badge"
                style={{
                  background: n8nConnected ? "var(--success-bg)" : "var(--bg-elevated)",
                  color: n8nConnected ? "var(--success)" : "var(--text-muted)",
                  border: `1px solid ${n8nConnected ? "var(--success-border)" : "var(--border)"}`,
                  fontSize: 10,
                }}
              >
                {n8nConnected ? "Connected" : "Not configured"}
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleShare("drive")}
                disabled={!n8nConnected || sharing !== null}
                className="btn-ghost text-xs py-2 px-4 flex items-center gap-1.5"
              >
                {sharing === "drive" ? <span className="spinner" style={{ width: 12, height: 12 }} /> : "📁"}
                Google Drive
              </button>
              <button
                onClick={() => handleShare("sheets")}
                disabled={!n8nConnected || sharing !== null}
                className="btn-ghost text-xs py-2 px-4 flex items-center gap-1.5"
              >
                {sharing === "sheets" ? <span className="spinner" style={{ width: 12, height: 12 }} /> : "📊"}
                Google Sheets
              </button>
              <button
                onClick={() => handleShare("email")}
                disabled={!n8nConnected || sharing !== null}
                className="btn-ghost text-xs py-2 px-4 flex items-center gap-1.5"
              >
                {sharing === "email" ? <span className="spinner" style={{ width: 12, height: 12 }} /> : "📧"}
                Email Report
              </button>
              <button
                onClick={() => handleShare("all")}
                disabled={!n8nConnected || sharing !== null}
                className="btn-ghost text-xs py-2 px-4 flex items-center gap-1.5"
                style={n8nConnected ? { borderColor: "var(--accent-border)", color: "var(--accent)" } : {}}
              >
                {sharing === "all" ? <span className="spinner" style={{ width: 12, height: 12 }} /> : "🚀"}
                Share All
              </button>
            </div>
            {shareMsg && (
              <div className="mt-2 text-xs animate-fade-in" style={{ color: "var(--text-secondary)" }}>
                {shareMsg}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Live Stream Panel */}
      {streamingAgent && (
        <div className="mb-4 animate-fade-in">
          <LiveStreamPanel
            agentRole={streamingAgent}
            streamText={streamText}
            tokenCount={streamTokens}
            elapsed={elapsed}
          />
        </div>
      )}

      {/* Live Agent Canvas */}
      <div className="mb-6 animate-fade-in" style={{ animationDelay: "0.1s" }}>
        <AgentCanvas
          status={project.status}
          outputs={outputs}
          streamingAgent={streamingAgent}
          streamTokens={streamTokens}
          elapsed={elapsed}
          onNodeClick={(role) => setInspectingAgent(role)}
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 animate-fade-in" style={{ animationDelay: "0.15s" }}>
        {(["outputs", "chat"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-5 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer"
            style={{
              background: activeTab === tab ? "var(--accent-bg)" : "transparent",
              color: activeTab === tab ? "var(--accent)" : "var(--text-muted)",
              border: activeTab === tab ? "1px solid var(--accent-border)" : "1px solid transparent",
            }}
          >
            {tab === "outputs" ? "Employee Outputs" : "Call Employee"}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2">
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

            </div>
          ) : (
            <CallEmployee projectId={projectId} />
          )}
        </div>

        {/* Activity feed */}
        <div className="lg:col-span-1">
          <div className="card p-4 sticky top-6">
            <h3 className="font-semibold mb-4 text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
              Activity
            </h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {events.length === 0 && (
                <div className="text-sm" style={{ color: "var(--text-muted)" }}>No activity yet...</div>
              )}
              {events.map((event, i) => {
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
                    className="flex gap-3 text-sm py-2 pl-3 animate-slide-in"
                    style={{ borderLeft: `2px solid ${color}` }}
                  >
                    <div>
                      <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>{event.message}</div>
                      <div style={{ color: "var(--text-muted)", fontSize: 11 }}>{event.time}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {inspectingAgent && (
        <AgentIntrospection
          projectId={projectId}
          role={inspectingAgent}
          onClose={() => setInspectingAgent(null)}
        />
      )}

      {showCodePreview && (
        <CodePreview
          projectId={projectId}
          onClose={() => setShowCodePreview(false)}
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
