"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import AgentCanvas from "./AgentCanvas";
import AgentIntrospection from "./AgentIntrospection";
import BuildStatus, { ValidationResult } from "./BuildStatus";
import AgentOutputCard from "./AgentOutput";
import CallEmployee from "./CallEmployee";
import CodePreview from "./CodePreview";
import GitHubPush from "./GitHubPush";
import CostMonitor from "./CostMonitor";
import SecurityBadge, { SecurityScanEvent } from "./SecurityBadge";
import ArchitectureDiagram from "./ArchitectureDiagram";
import LiveStreamPanel from "./LiveStreamPanel";
import { useToast } from "./Toast";
import { DashboardSkeleton } from "./Skeleton";
import { ProjectState, WSMessage, connectWebSocket, getProjectState, approveOutput, downloadCode, downloadPptx, downloadDocx, downloadWorkflow, downloadBundle, getModelConfig, saveDemoCache, reviseAgent, generateShareLink, getPreviewStatus, getStaticPreviewUrl, stopPreview, ReconnectingWebSocket } from "@/lib/api";
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
      return { headline: `${count} requirement${count !== 1 ? "s" : ""} defined`, detail: funcReqs.slice(0, 2).map((r: unknown) => typeof r === "string" ? r.split(".")[0].trim() : "").filter(Boolean).join(" · ") };
    }
    case "researcher": {
      const products = Array.isArray(content.existing_products) ? content.existing_products : [];
      return { headline: products.length > 0 ? `${products.length} competitor${products.length !== 1 ? "s" : ""} analyzed` : "Research complete", detail: firstSentence(content.recommended_approach) };
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
      return { headline: files.length > 0 ? `${files.length} file${files.length !== 1 ? "s" : ""} generated` : "Code complete", detail: firstSentence(content.implementation_summary) };
    }
    case "ppt": {
      const slides = Array.isArray(content.slides) ? content.slides : [];
      return { headline: slides.length > 0 ? `${slides.length} slide${slides.length !== 1 ? "s" : ""} prepared` : "Docs ready", detail: firstSentence(content.executive_summary) };
    }
    default:
      return { headline: "Complete", detail: "" };
  }
}

type StageState = "future" | "active" | "review" | "done";

function getStageState(role: string, currentStatus: string, outputs: { role: string; status: string }[], streamingAgent: string | null): StageState {
  const hasApproved = outputs.some(o => o.role === role && o.status === "approved");
  if (hasApproved) return "done";
  const hasPending = outputs.some(o => o.role === role && o.status === "pending");
  if (hasPending) return "review";
  if (streamingAgent === role) return "active";
  const activeAgent = STATUS_TO_AGENT[currentStatus];
  if (activeAgent === role) return "active";
  return "future";
}

export default function Dashboard({ projectId }: Props) {
  const [state, setState] = useState<ProjectState | null>(null);
  const [events, setEvents] = useState<{ type: string; message: string; time: string }[]>([]);
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
  const [costEvent, setCostEvent] = useState<{ role: string; tokens: number } | null>(null);
  const [securityScan, setSecurityScan] = useState<SecurityScanEvent | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [detailPanel, setDetailPanel] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const { toast } = useToast();

  const refreshState = useCallback(async () => {
    try {
      const s = await getProjectState(projectId);
      setState(s);
      if (s.memory?.final_validation_result) {
        try { setValidationResult(JSON.parse(s.memory.final_validation_result)); } catch {}
      }
      if (s.memory?.security_scan) {
        try { setSecurityScan(JSON.parse(s.memory.security_scan)); } catch {}
      }
      getPreviewStatus(projectId).then(p => {
        if (p.preview_url) setPreviewUrl(p.preview_url);
        else if (p.has_static_preview) setPreviewUrl(getStaticPreviewUrl(projectId));
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
    getModelConfig()
      .then((cfg) => updateModelLabels(cfg.agents))
      .catch(() => {});
  }, []);

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
        if (msg.data.role) setSelectedAgent(msg.data.role);
      }
      if (msg.type === "error") {
        toast("error", "Pipeline error", msg.data.message || "An agent encountered an error.");
      }
      if (msg.type === "approval_needed" || msg.type === "agent_completed" || msg.type === "project_completed") {
        setStreamingAgent(null);
        setStreamTokens(0);
        setStreamText("");
        setAgentStartTime(null);
        if (msg.type === "approval_needed" && msg.data.role) {
          setDetailPanel(msg.data.role);
          setSelectedAgent(msg.data.role);
        }
      }
      if (msg.type === "sandbox_completed" && (msg.data as Record<string, unknown>).validation_result) {
        setValidationResult((msg.data as Record<string, unknown>).validation_result as ValidationResult);
      }
      if (msg.type === "sandbox_preview_ready" && (msg.data as Record<string, unknown>).preview_url) {
        setPreviewUrl((msg.data as Record<string, unknown>).preview_url as string);
      }
      if (msg.type === "cost_update") {
        setCostEvent({ role: (msg.data as Record<string, unknown>).role as string, tokens: (msg.data as Record<string, unknown>).tokens as number });
        return;
      }
      if (msg.type === "security_scan") {
        setSecurityScan(msg.data as unknown as SecurityScanEvent);
        return;
      }
      setEvents((prev) => {
        const next = [...prev, { type: msg.type, message: msg.data.message || msg.type, time: new Date().toLocaleTimeString() }];
        return next.length > 100 ? next.slice(-80) : next;
      });
      debouncedRefresh();
    }, (connected) => setWsConnected(connected));
    const pollInterval = setInterval(() => { refreshState(); }, 8000);
    return () => { ws.close(); clearInterval(pollInterval); if (refreshTimer.current) clearTimeout(refreshTimer.current); };
  }, [projectId, refreshState, debouncedRefresh]);

  async function handleApprove(outputId: string) {
    try { await approveOutput(projectId, outputId, true); setDetailPanel(null); refreshState(); }
    catch { toast("error", "Approval failed", "Could not approve — backend may be restarting. Try again."); }
  }

  async function handleReject(outputId: string, feedback: string) {
    try { await approveOutput(projectId, outputId, false, feedback); setDetailPanel(null); refreshState(); }
    catch { toast("error", "Rejection failed", "Could not send feedback — backend may be restarting. Try again."); }
  }

  async function handleRevise(role: string, feedback: string) {
    try { await reviseAgent(projectId, role, feedback); toast("success", "Revision started", `${role.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())} is reworking.`); refreshState(); }
    catch { toast("error", "Revision failed", "Could not start revision."); }
  }

  async function handleShareLink() {
    setCopyingLink(true);
    try {
      const { token } = await generateShareLink(projectId);
      const url = `${window.location.origin}/shared/${token}`;
      setShareLink(url);
      await navigator.clipboard.writeText(url);
      toast("success", "Link copied!", "Share this link with anyone — no login required.");
    } catch { toast("error", "Share failed", "Could not generate share link."); }
    finally { setCopyingLink(false); }
  }

  useEffect(() => {
    if (!agentStartTime) { setElapsed(0); return; }
    const interval = setInterval(() => { setElapsed(Math.floor((Date.now() - agentStartTime) / 1000)); }, 1000);
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
    const interval = setInterval(() => { setPipelineElapsed(Math.floor((Date.now() - created) / 1000)); }, 1000);
    return () => clearInterval(interval);
  }, [state?.project?.created_at, state?.project?.status, state?.project?.updated_at]);

  if (!state?.project) return <DashboardSkeleton />;

  const { project, outputs, memory } = state;
  const pendingOutput = outputs.find((o) => o.status === "pending");
  const statusLabel = STATUS_LABELS[project.status] || project.status;
  const routeName = memory?.pipeline_route || "full";
  const routeAgents = ROUTE_CONFIG[routeName]?.agents || PIPELINE_ORDER;
  const routeInfo = ROUTE_CONFIG[routeName];
  const isAutoPilot = memory?.auto_approve === "true";
  const isCompleted = project.status === "completed";
  const deliverableType = state.memory?.deliverable_type || "code";

  function getPeerReview(role: string) {
    const raw = memory?.[`peer_review_${role}`];
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }

  function handleNodeClick(role: string) {
    setSelectedAgent(role);
    const st = getStageState(role, project.status, outputs, streamingAgent);
    if (st === "done" || st === "review") {
      setDetailPanel(detailPanel === role ? null : role);
    } else {
      setInspectingAgent(role);
    }
  }

  const detailOutput = detailPanel ? outputs.find(o => o.role === detailPanel && (o.status === "approved" || o.status === "pending")) : null;
  const completedAgents = routeAgents.filter(r => {
    const st = getStageState(r, project.status, outputs, streamingAgent);
    return st === "done" || st === "review";
  });

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(180deg, #080b1a 0%, #0d1025 40%, #111528 100%)",
      color: "#e0e0e0",
      // Override CSS vars so all child components render in dark mode
      "--bg-base": "#0d1025",
      "--bg-card": "rgba(255,255,255,0.04)",
      "--bg-card-hover": "rgba(255,255,255,0.07)",
      "--bg-elevated": "rgba(255,255,255,0.06)",
      "--bg-secondary": "rgba(255,255,255,0.03)",
      "--border": "rgba(255,255,255,0.08)",
      "--border-hover": "rgba(255,255,255,0.15)",
      "--text-primary": "rgba(255,255,255,0.92)",
      "--text-secondary": "rgba(255,255,255,0.6)",
      "--text-muted": "rgba(255,255,255,0.35)",
      "--accent": "#7a73ff",
      "--accent-light": "#a5a0ff",
      "--accent-bg": "rgba(99,91,255,0.12)",
      "--accent-border": "rgba(99,91,255,0.25)",
      "--success": "#34d399",
      "--success-bg": "rgba(16,185,129,0.12)",
      "--success-border": "rgba(16,185,129,0.25)",
      "--warning": "#fbbf24",
      "--warning-bg": "rgba(245,166,35,0.12)",
      "--warning-border": "rgba(245,166,35,0.25)",
      "--danger": "#f87171",
      "--info": "#818cf8",
    } as React.CSSProperties}>
      <style>{`
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .mc-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; transition: all 0.15s ease; }
        .mc-card:hover { border-color: rgba(99,91,255,0.3); background: rgba(255,255,255,0.05); }
        .mc-btn { padding: 8px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.85); cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px; justify-content: center; }
        .mc-btn:hover { background: rgba(255,255,255,0.1); border-color: rgba(99,91,255,0.4); }
        .mc-btn-primary { background: rgba(99,91,255,0.2); border-color: rgba(99,91,255,0.4); color: #a5a0ff; }
        .mc-btn-primary:hover { background: rgba(99,91,255,0.3); }
        .mc-btn-success { background: rgba(16,185,129,0.2); border-color: rgba(16,185,129,0.4); color: #34d399; }
        .mc-btn-success:hover { background: rgba(16,185,129,0.3); }
        .detail-panel { animation: slideIn 0.25s ease; }
        .mc-fade { animation: fadeUp 0.3s ease; }
        .mc-chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
        .mc-output-strip { padding: 10px 14px; border-radius: 10px; cursor: pointer; display: flex; align-items: center; gap: 10px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); transition: all 0.15s; }
        .mc-output-strip:hover { background: rgba(255,255,255,0.05); border-color: rgba(99,91,255,0.3); }
      `}</style>

      {/* Connection banner */}
      {!wsConnected && (
        <div style={{
          background: "rgba(237,95,116,0.1)", border: "1px solid rgba(237,95,116,0.25)",
          borderRadius: 10, padding: "10px 16px", margin: "12px 24px 0",
          display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "#ed5f74",
        }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ed5f74", flexShrink: 0 }} />
          <span><strong>Disconnected</strong> — live updates paused.</span>
        </div>
      )}

      {/* Top Nav Bar */}
      <div style={{
        padding: "14px 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", textDecoration: "none", transition: "color 0.15s" }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "#a5a0ff"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(255,255,255,0.4)"; }}>
            ← Company
          </Link>
          <span style={{ color: "rgba(255,255,255,0.1)" }}>|</span>
          <span style={{ fontSize: 15, fontWeight: 700, color: "rgba(255,255,255,0.9)" }}>Build Room</span>
          {routeInfo && routeName !== "full" && (
            <span className="mc-chip" style={{ background: "rgba(99,91,255,0.12)", color: "#a5a0ff", border: "1px solid rgba(99,91,255,0.25)" }}>
              {routeInfo.icon} {routeInfo.name}
            </span>
          )}
          {isAutoPilot && (
            <span className="mc-chip" style={{ background: "rgba(99,91,255,0.12)", color: "#7a73ff", border: "1px solid rgba(99,91,255,0.25)" }}>
              Auto-pilot
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="mc-chip" style={{
            background: isCompleted ? "rgba(16,185,129,0.12)" : "rgba(99,91,255,0.12)",
            color: isCompleted ? "#34d399" : "#a5a0ff",
            border: `1px solid ${isCompleted ? "rgba(16,185,129,0.3)" : "rgba(99,91,255,0.25)"}`,
          }}>
            {isCompleted && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34d399" }} />}
            {statusLabel}
          </span>
          {pipelineElapsed > 0 && (
            <span style={{ fontSize: 12, fontFamily: "monospace", color: "rgba(255,255,255,0.4)", padding: "3px 10px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)" }}>
              {formatPipelineTime(pipelineElapsed)}
            </span>
          )}
        </div>
      </div>

      {/* Problem Statement */}
      <div style={{ padding: "8px 24px 0", maxWidth: 700 }}>
        <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {project.problem_statement}
        </p>
      </div>

      {/* ===== HERO: Company HQ — Full Width ===== */}
      <div style={{ padding: "16px 24px" }} className="mc-fade">
        <AgentCanvas
          status={project.status}
          outputs={outputs}
          streamingAgent={streamingAgent}
          streamTokens={streamTokens}
          elapsed={elapsed}
          visibleAgents={routeAgents}
          selectedAgent={selectedAgent}
          onNodeClick={handleNodeClick}
        />
      </div>

      {/* ===== Below Hero: Content Area ===== */}
      <div style={{ padding: "0 24px 24px", display: "flex", gap: 20 }}>

        {/* Main Content */}
        <div style={{ flex: 1, minWidth: 0 }}>

          {/* Live stream panel */}
          {streamingAgent && (
            <div className="mc-fade" style={{ marginBottom: 16 }}>
              <LiveStreamPanel
                agentRole={streamingAgent}
                streamText={streamText}
                tokenCount={streamTokens}
                elapsed={elapsed}
              />
            </div>
          )}

          {/* Completed Agent Strips */}
          {completedAgents.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                Agent Outputs
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {completedAgents.map((role) => {
                  const output = outputs.find(o => o.role === role && (o.status === "approved" || o.status === "pending"));
                  if (!output) return null;
                  const config = AGENT_CONFIG[role];
                  const summary = extractSummary(role, output.content as Record<string, unknown>);
                  const isPending = pendingOutput?.role === role;
                  const isOpen = detailPanel === role;

                  return (
                    <div key={role} className="mc-output-strip" onClick={() => handleNodeClick(role)}
                      style={{
                        borderColor: isPending ? "rgba(245,166,35,0.3)" : isOpen ? "rgba(99,91,255,0.4)" : undefined,
                        background: isPending ? "rgba(245,166,35,0.06)" : isOpen ? "rgba(99,91,255,0.06)" : undefined,
                      }}>
                      <span style={{ fontSize: 20, flexShrink: 0, width: 28, textAlign: "center" }}>{config?.icon}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(255,255,255,0.9)" }}>{config?.label}</span>
                          {isPending && (
                            <span className="mc-chip" style={{ background: "rgba(245,166,35,0.15)", color: "#f5a623", border: "1px solid rgba(245,166,35,0.3)", animation: "pulse 2s infinite" }}>
                              Needs Approval
                            </span>
                          )}
                          {!isPending && (
                            <span className="mc-chip" style={{ background: "rgba(16,185,129,0.1)", color: "#34d399" }}>Done</span>
                          )}
                        </div>
                        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", margin: "2px 0 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {summary.headline}{summary.detail ? ` — ${summary.detail}` : ""}
                        </p>
                      </div>
                      <span style={{ fontSize: 14, color: "rgba(255,255,255,0.2)", flexShrink: 0, transform: isOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▾</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Product Ready Actions */}
          {isCompleted && (
            <div className="mc-card mc-fade" style={{ padding: 16, marginBottom: 16, borderColor: "rgba(16,185,129,0.2)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#34d399", boxShadow: "0 0 12px rgba(16,185,129,0.4)" }} />
                  <span style={{ fontSize: 14, fontWeight: 700, color: "rgba(255,255,255,0.95)" }}>Product Ready</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {validationResult && (
                    <span className="mc-chip" style={{
                      background: validationResult.final_status === "VALIDATED" ? "rgba(16,185,129,0.12)" : "rgba(237,95,116,0.12)",
                      color: validationResult.final_status === "VALIDATED" ? "#34d399" : "#ed5f74",
                    }}>
                      {validationResult.final_status === "VALIDATED" ? "PASS" : "FAIL"} Build
                    </span>
                  )}
                  {securityScan && (
                    <span className="mc-chip" style={{
                      background: securityScan.status === "PASS" ? "rgba(16,185,129,0.12)" : "rgba(245,166,35,0.12)",
                      color: securityScan.status === "PASS" ? "#34d399" : "#f5a623",
                    }}>
                      {securityScan.status} Security
                    </span>
                  )}
                  <span style={{ fontSize: 12, fontFamily: "monospace", color: "rgba(255,255,255,0.35)" }}>
                    {formatPipelineTime(pipelineElapsed)}
                  </span>
                </div>
              </div>

              {/* Preview iframe */}
              {previewUrl && (() => {
                const isStatic = previewUrl.includes("/preview/static");
                return (
                  <div style={{ borderRadius: 8, overflow: "hidden", border: "1px solid rgba(255,255,255,0.08)", marginBottom: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 12px", background: "rgba(255,255,255,0.03)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: isStatic ? "#a5a0ff" : "#34d399" }} />
                        <span style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.5)" }}>{isStatic ? "Preview" : "Live"}</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <a href={previewUrl} target="_blank" rel="noopener noreferrer" style={{ fontSize: 10, color: "#a5a0ff", textDecoration: "none" }}>Open ↗</a>
                        {!isStatic && (
                          <button onClick={async () => { try { await stopPreview(projectId); } catch {} setPreviewUrl(null); }}
                            style={{ fontSize: 10, color: "#ed5f74", background: "none", border: "none", cursor: "pointer" }}>Stop</button>
                        )}
                      </div>
                    </div>
                    <iframe src={previewUrl} style={{ width: "100%", height: 260, border: "none" }}
                            sandbox="allow-scripts allow-same-origin allow-forms allow-popups" />
                  </div>
                );
              })()}

              {/* Action Buttons */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(100px, 1fr))", gap: 6 }}>
                {(!deliverableType || deliverableType === "code" || deliverableType === "hybrid") && (
                  <button className="mc-btn-success" onClick={async () => { try { await downloadCode(projectId); } catch (e) { toast("error", "Download failed", e instanceof Error ? e.message : ""); } }}>
                    <span>📦</span> Code
                  </button>
                )}
                {(!deliverableType || deliverableType === "code" || deliverableType === "hybrid") && validationResult?.final_status === "VALIDATED" && (
                  <button className="mc-btn" onClick={async () => { try { await downloadBundle(projectId); } catch (e) { toast("warning", "Not available", e instanceof Error ? e.message : ""); } }}
                    style={{ background: "rgba(139,92,246,0.2)", borderColor: "rgba(139,92,246,0.4)", color: "#a78bfa" }}>
                    <span>🚀</span> Deploy
                  </button>
                )}
                {(deliverableType === "workflow" || deliverableType === "hybrid") && (
                  <button className="mc-btn-primary" onClick={async () => { try { await downloadWorkflow(projectId); } catch (e) { toast("warning", "Not available", e instanceof Error ? e.message : ""); } }}>
                    <span>⚡</span> Workflow
                  </button>
                )}
                <button className="mc-btn-primary" onClick={async () => { try { await downloadPptx(projectId); } catch (e) { toast("error", "Failed", e instanceof Error ? e.message : ""); } }}>
                  <span>📊</span> PPTX
                </button>
                <button className="mc-btn" onClick={async () => { try { await downloadDocx(projectId); } catch (e) { toast("error", "Failed", e instanceof Error ? e.message : ""); } }}>
                  <span>📄</span> DOCX
                </button>
                {(!deliverableType || deliverableType === "code" || deliverableType === "hybrid") && (
                  <>
                    <button className="mc-btn" onClick={() => setShowCodePreview(true)}>
                      <span>👁️</span> Code
                    </button>
                    <button className="mc-btn" onClick={() => setShowGitHubPush(true)}>
                      <span>🐙</span> GitHub
                    </button>
                  </>
                )}
                <button className="mc-btn" onClick={handleShareLink} disabled={copyingLink}
                  style={{ borderColor: "rgba(99,91,255,0.4)", color: "#a5a0ff" }}>
                  {copyingLink ? "..." : <><span>🔗</span> {shareLink ? "Copied!" : "Share"}</>}
                </button>
                <button className="mc-btn" onClick={async () => { try { await saveDemoCache(projectId); toast("success", "Saved", "Demo Mode available."); } catch { toast("error", "Failed", ""); } }}
                  style={{ borderColor: "rgba(245,166,35,0.3)", color: "#f5a623" }}>
                  <span>💾</span> Demo
                </button>
                {outputs.find(o => o.role === "architect") && (
                  <button className="mc-btn" onClick={() => setShowArchDiagram(true)}
                    style={{ borderColor: "rgba(139,92,246,0.3)", color: "#a78bfa" }}>
                    <span>🏗️</span> Arch
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Talk to Company */}
          {showChat ? (
            <div className="mc-fade">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(255,255,255,0.9)" }}>Talk to your Company</span>
                <button onClick={() => setShowChat(false)} style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", background: "none", border: "none", cursor: "pointer" }}>Close</button>
              </div>
              <CallEmployee projectId={projectId} />
            </div>
          ) : (
            <button className="mc-btn" onClick={() => setShowChat(true)}
              style={{ width: "100%", padding: "12px", borderColor: "rgba(99,91,255,0.25)", color: "#a5a0ff" }}>
              <span>💬</span> Talk to your Company
            </button>
          )}
        </div>

        {/* Right Sidebar */}
        <div style={{ width: 280, flexShrink: 0, display: "flex", flexDirection: "column", gap: 12 }}>
          <CostMonitor projectId={projectId} costEvent={costEvent} />
          {securityScan && <SecurityBadge scan={securityScan} />}

          {/* Activity Feed */}
          {events.length > 0 && (
            <div className="mc-card" style={{ padding: 12, maxHeight: 180, overflowY: "auto" }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
                Activity
              </div>
              {events.slice(-6).reverse().map((e, i) => (
                <div key={i} style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", display: "flex", gap: 6, marginBottom: 3 }}>
                  <span style={{ fontFamily: "monospace", flexShrink: 0, opacity: 0.6, fontSize: 10 }}>{e.time}</span>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ===== Slide-in Detail Panel ===== */}
      {detailPanel && detailOutput && (
        <div style={{
          position: "fixed", top: 0, right: 0, bottom: 0, width: "min(600px, 85vw)",
          background: "linear-gradient(180deg, #0c0f24, #111528)",
          borderLeft: "1px solid rgba(99,91,255,0.2)",
          zIndex: 50, overflowY: "auto", padding: "0",
          boxShadow: "-8px 0 40px rgba(0,0,0,0.5)",
          "--bg-card": "rgba(255,255,255,0.04)",
          "--bg-card-hover": "rgba(255,255,255,0.07)",
          "--bg-elevated": "rgba(255,255,255,0.06)",
          "--bg-secondary": "rgba(255,255,255,0.03)",
          "--border": "rgba(255,255,255,0.08)",
          "--border-hover": "rgba(255,255,255,0.15)",
          "--text-primary": "rgba(255,255,255,0.92)",
          "--text-secondary": "rgba(255,255,255,0.6)",
          "--text-muted": "rgba(255,255,255,0.35)",
          "--accent": "#7a73ff",
          "--accent-bg": "rgba(99,91,255,0.12)",
          "--accent-border": "rgba(99,91,255,0.25)",
          "--success": "#34d399",
          "--success-bg": "rgba(16,185,129,0.12)",
          "--success-border": "rgba(16,185,129,0.25)",
          "--warning": "#fbbf24",
          "--warning-bg": "rgba(245,166,35,0.12)",
          "--warning-border": "rgba(245,166,35,0.25)",
          "--danger": "#f87171",
        } as React.CSSProperties} className="detail-panel">
          {/* Panel header */}
          <div style={{
            position: "sticky", top: 0, zIndex: 2,
            background: "linear-gradient(180deg, #0c0f24, rgba(12,15,36,0.95))",
            padding: "16px 20px",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 22 }}>{AGENT_CONFIG[detailPanel]?.icon}</span>
              <span style={{ fontSize: 15, fontWeight: 700, color: "rgba(255,255,255,0.95)" }}>
                {AGENT_CONFIG[detailPanel]?.label || detailPanel}
              </span>
              {pendingOutput?.role === detailPanel && (
                <span className="mc-chip" style={{ background: "rgba(245,166,35,0.15)", color: "#f5a623", border: "1px solid rgba(245,166,35,0.3)" }}>
                  Needs Approval
                </span>
              )}
            </div>
            <button onClick={() => setDetailPanel(null)}
              style={{ fontSize: 20, color: "rgba(255,255,255,0.4)", background: "none", border: "none", cursor: "pointer", padding: "4px 8px" }}>
              ✕
            </button>
          </div>

          {/* Panel content */}
          <div style={{ padding: 20 }}>
            <AgentOutputCard
              role={detailOutput.role}
              content={detailOutput.content as Record<string, unknown>}
              status={detailOutput.status}
              outputId={detailOutput.id}
              onApprove={handleApprove}
              onReject={handleReject}
              onRevise={handleRevise}
              showActions={pendingOutput?.role === detailPanel}
              peerReview={getPeerReview(detailOutput.role)}
            />
            {detailPanel === "engineer" && validationResult && (
              <div style={{ marginTop: 16 }}>
                <BuildStatus validationResult={validationResult} />
                {previewUrl && (
                  <button className="mc-btn-success" onClick={() => setShowPreview(true)} style={{ marginTop: 8 }}>
                    <span>🌐</span> Live Preview
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Backdrop for detail panel */}
      {detailPanel && detailOutput && (
        <div onClick={() => setDetailPanel(null)} style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 49,
        }} />
      )}

      {/* ===== Modals ===== */}
      {inspectingAgent && (
        <AgentIntrospection projectId={projectId} role={inspectingAgent} onClose={() => setInspectingAgent(null)} />
      )}

      {showPreview && previewUrl && (
        <div style={{ padding: 0, overflow: "hidden", position: "fixed", top: 40, left: 40, right: 40, bottom: 40, zIndex: 50, background: "#0c0f24", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#34d399" }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.9)" }}>Live Preview</span>
              <a href={previewUrl} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: "#a5a0ff", textDecoration: "none" }}>Open ↗</a>
            </div>
            <button onClick={() => setShowPreview(false)} style={{ fontSize: 18, color: "rgba(255,255,255,0.4)", background: "none", border: "none", cursor: "pointer" }}>✕</button>
          </div>
          <iframe src={previewUrl} style={{ width: "100%", height: "calc(100% - 45px)", border: "none" }} sandbox="allow-scripts allow-same-origin allow-forms allow-popups" />
        </div>
      )}

      {showCodePreview && <CodePreview projectId={projectId} onClose={() => setShowCodePreview(false)} />}
      {showGitHubPush && <GitHubPush projectId={projectId} problemStatement={project.problem_statement} onClose={() => setShowGitHubPush(false)} />}

      {showArchDiagram && (() => {
        const archOutput = outputs.find((o) => o.role === "architect");
        if (!archOutput) return null;
        return <ArchitectureDiagram architectOutput={archOutput.content as Record<string, unknown>} onClose={() => setShowArchDiagram(false)} />;
      })()}
    </div>
  );
}
