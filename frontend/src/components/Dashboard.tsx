"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import AgentCanvas from "./AgentCanvas";
import AgentIntrospection from "./AgentIntrospection";
import AgentOutputCard from "./AgentOutput";
import CallEmployee from "./CallEmployee";
import { useToast } from "./Toast";
import { DashboardSkeleton } from "./Skeleton";
import { ProjectState, WSMessage, connectWebSocket, getProjectState, approveOutput, downloadCode, downloadPptx, downloadDocx, shareProject, getIntegrationStatus, saveDemoCache } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/constants";

interface Props {
  projectId: string;
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
  const { toast } = useToast();

  const refreshState = useCallback(async () => {
    try {
      const s = await getProjectState(projectId);
      setState(s);
    } catch {
      toast("warning", "Connection issue", "Could not refresh project state from the backend.");
    }
  }, [projectId]);

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
        return;
      }

      if (msg.type === "agent_started") {
        setStreamingAgent(msg.data.role || null);
        setStreamTokens(0);
        setAgentStartTime(Date.now());
      }

      if (msg.type === "error") {
        toast("error", "Pipeline error", msg.data.message || "An agent encountered an error.");
      }

      if (msg.type === "approval_needed" || msg.type === "agent_completed" || msg.type === "project_completed") {
        setStreamingAgent(null);
        setStreamTokens(0);
        setAgentStartTime(null);
      }

      setEvents((prev) => [
        ...prev,
        {
          type: msg.type,
          message: msg.data.message || msg.type,
          time: new Date().toLocaleTimeString(),
        },
      ]);
      refreshState();
    });

    ws.addEventListener("open", () => setWsConnected(true));
    ws.addEventListener("close", () => setWsConnected(false));

    return () => ws.close();
  }, [projectId, refreshState]);

  async function handleApprove(outputId: string) {
    await approveOutput(projectId, outputId, true);
    refreshState();
  }

  async function handleReject(outputId: string, feedback: string) {
    await approveOutput(projectId, outputId, false, feedback);
    refreshState();
  }

  if (!state?.project) {
    return <DashboardSkeleton />;
  }

  useEffect(() => {
    if (!agentStartTime) { setElapsed(0); return; }
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - agentStartTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [agentStartTime]);

  const { project, outputs, memory } = state;
  const pendingOutput = outputs.find((o) => o.status === "pending");
  const statusLabel = STATUS_LABELS[project.status] || project.status;

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

        {/* Download Buttons */}
        {isCompleted && (
          <div className="flex gap-3 mt-5 animate-fade-in">
            <button onClick={() => downloadCode(projectId)}
                    className="btn-success text-sm py-2.5 px-5 flex items-center gap-2">
              <span>📦</span> Download Code (.zip)
            </button>
            <button onClick={() => downloadPptx(projectId)}
                    className="btn-primary text-sm py-2.5 px-5 flex items-center gap-2">
              <span>📊</span> Presentation (.pptx)
            </button>
            <button onClick={() => downloadDocx(projectId)}
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
                    {["CEO", "BA", "Research", "Architect", "Engineer", "PPT"].map((label, i) => (
                      <span
                        key={label}
                        className="text-xs px-2.5 py-1 rounded-full"
                        style={{
                          background: i === 0 && !streamingAgent ? "var(--accent-bg)" : "var(--bg-elevated)",
                          color: i === 0 && !streamingAgent ? "var(--accent)" : "var(--text-muted)",
                          border: `1px solid ${i === 0 && !streamingAgent ? "var(--accent-border)" : "var(--border)"}`,
                        }}
                      >
                        {label}
                      </span>
                    ))}
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
    </div>
  );
}
