"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/contexts/AuthContext";
import {
  getEmployee, updateEmployee, listEmployeeSessions, createEmployeeSession, getSessionWithMessages,
  sendEmployeeMessage, endEmployeeSession, listMemories, listSkills, extractSkills,
  deactivateSkill, getEmployeePermissions, updateEmployeePermission,
  listScheduledTasks, createScheduledTask, deleteScheduledTask, runScheduledTaskNow,
  listExecutions,
  type Employee, type EmployeeSession, type SessionMessage,
  type Memory, type EmployeeSkill, type ToolPermission, type ScheduledTask,
  type AutonomousExecution,
} from "@/lib/api";
import { ThinkingOrb, type OrbState } from "thinking-orbs";
import ExecutionProgress from "@/components/ExecutionProgress";

type Tab = "chat" | "memories" | "sessions" | "skills" | "schedule" | "settings";

const ROLE_META: Record<string, { icon: string; color: string }> = {
  "Business Analyst": { icon: "📋", color: "#0bbf8c" },
  "Researcher":       { icon: "🔍", color: "#3b82f6" },
  "Architect":        { icon: "🏗️", color: "#8b5cf6" },
  "Software Engineer":{ icon: "⚡", color: "#f59e0b" },
  "QA Engineer":      { icon: "🛡️", color: "#ef4444" },
  "Technical Writer": { icon: "✍️", color: "#06b6d4" },
};

const STATUS_ORB: Record<string, { orbState: OrbState; label: string }> = {
  idle:           { orbState: "breathing", label: "Ready" },
  thinking:       { orbState: "solving",   label: "Thinking..." },
  tool_execution: { orbState: "working",   label: "Executing..." },
  working:        { orbState: "working",   label: "Working..." },
  blocked:        { orbState: "listening", label: "Needs input" },
};

export default function EmployeeChatPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const employeeId = params.id as string;

  const [employee, setEmployee] = useState<Employee | null>(null);
  const [sessions, setSessions] = useState<EmployeeSession[]>([]);
  const [activeSession, setActiveSession] = useState<EmployeeSession | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sideTab, setSideTab] = useState<Tab>("chat");
  const [memoryFilter, setMemoryFilter] = useState<string>("");
  const [skills, setSkills] = useState<EmployeeSkill[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [showDelegationInfo, setShowDelegationInfo] = useState(false);
  const [permissions, setPermissions] = useState<ToolPermission[]>([]);
  const [editPersona, setEditPersona] = useState("");
  const [savingPersona, setSavingPersona] = useState(false);
  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTask[]>([]);
  const [showNewTask, setShowNewTask] = useState(false);
  const [newTaskName, setNewTaskName] = useState("");
  const [newTaskPrompt, setNewTaskPrompt] = useState("");
  const [newTaskType, setNewTaskType] = useState<"once" | "recurring">("once");
  const [newTaskCron, setNewTaskCron] = useState("");
  const [savingTask, setSavingTask] = useState(false);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (!user || !employeeId) return;
    (async () => {
      try {
        const emp = await getEmployee(employeeId);
        setEmployee(emp);
        const sess = await listEmployeeSessions(employeeId);
        setSessions(sess);
        const active = sess.find((s) => s.status === "active");
        if (active) {
          const full = await getSessionWithMessages(active.id);
          setActiveSession(active);
          setMessages(full.messages);
        }
        try {
          const { executions } = await listExecutions(employeeId, "running");
          if (executions.length > 0) {
            setActiveExecutionId(executions[0].id);
          }
        } catch { /* no running executions */ }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load employee");
      } finally {
        setLoading(false);
      }
    })();
  }, [user, employeeId]);

  useEffect(scrollToBottom, [messages, scrollToBottom]);

  useEffect(() => {
    if (!sending || !employeeId) return;
    let active = true;
    const poll = setInterval(() => {
      getEmployee(employeeId).then((emp) => { if (active) setEmployee(emp); }).catch(() => {});
    }, 1500);
    return () => { active = false; clearInterval(poll); };
  }, [sending, employeeId]);

  useEffect(() => {
    if (sideTab !== "memories" || !employeeId) return;
    listMemories(employeeId, undefined, memoryFilter || undefined)
      .then(setMemories)
      .catch(() => {});
  }, [sideTab, employeeId, memoryFilter]);

  useEffect(() => {
    if (sideTab !== "skills" || !employeeId) return;
    listSkills(employeeId).then(setSkills).catch(() => {});
  }, [sideTab, employeeId]);

  useEffect(() => {
    if (sideTab !== "settings" || !employeeId) return;
    getEmployeePermissions(employeeId).then(setPermissions).catch(() => {});
    if (employee) setEditPersona(employee.persona || "");
  }, [sideTab, employeeId, employee]);

  useEffect(() => {
    if (sideTab !== "schedule" || !employeeId) return;
    listScheduledTasks(employeeId).then((d) => setScheduledTasks(d.tasks)).catch(() => {});
  }, [sideTab, employeeId]);

  async function handleStartSession() {
    try {
      const session = await createEmployeeSession(employeeId);
      setActiveSession(session);
      setMessages([]);
      setSessions((prev) => [session, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session");
    }
  }

  async function handleEndSession() {
    if (!activeSession) return;
    try {
      await endEmployeeSession(activeSession.id);
      setActiveSession(null);
      setSessions((prev) => prev.map((s) => s.id === activeSession.id ? { ...s, status: "completed" } : s));
    } catch { /* ignore */ }
  }

  async function handleSend() {
    if (!input.trim() || !activeSession || sending) return;
    const text = input.trim();
    setInput("");
    setSending(true);

    const optimisticMsg: SessionMessage = {
      id: `temp-${Date.now()}`, session_id: activeSession.id, role: "user",
      content: text, tool_calls: null, tool_results: null, created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticMsg]);

    try {
      const result = await sendEmployeeMessage(activeSession.id, text) as Record<string, unknown>;
      if (result.autonomous_execution) {
        const exec = result.autonomous_execution as AutonomousExecution;
        setActiveExecutionId(exec.id);
      }
      const full = await getSessionWithMessages(activeSession.id);
      setMessages(full.messages);
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== optimisticMsg.id));
      setError(e instanceof Error ? e.message : "Failed to send message");
    } finally {
      setSending(false);
      setEmployee((prev) => prev ? { ...prev, status: "idle" } : prev);
      inputRef.current?.focus();
    }
  }

  async function handleLoadSession(sessionId: string) {
    try {
      const full = await getSessionWithMessages(sessionId);
      setActiveSession({ ...full });
      setMessages(full.messages);
      setSideTab("chat");
    } catch { /* ignore */ }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  useEffect(() => {
    if (!authLoading && !loading && !user) router.push("/login");
  }, [authLoading, loading, user, router]);

  if (authLoading || loading) {
    return (
      <div style={{ display: "flex", height: "calc(100vh - 53px)", background: "var(--bg-base)" }}>
        {/* Skeleton sidebar */}
        <div style={{
          width: 280, borderRight: "1px solid var(--border)", background: "var(--bg-card)",
          display: "flex", flexDirection: "column", flexShrink: 0,
        }}>
          <div style={{ padding: "18px 16px", borderBottom: "1px solid var(--border)" }}>
            <div className="skeleton skeleton-text-sm" style={{ width: 40, marginBottom: 14 }} />
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div className="skeleton skeleton-circle" style={{ width: 32, height: 32 }} />
              <div style={{ flex: 1 }}>
                <div className="skeleton skeleton-text" style={{ width: "70%", marginBottom: 4 }} />
                <div className="skeleton skeleton-text-sm" style={{ width: "50%" }} />
              </div>
            </div>
          </div>
          <div style={{ display: "flex", borderBottom: "1px solid var(--border)", padding: "8px 12px", gap: 4 }}>
            {[40, 50, 55, 35, 50, 50].map((w, i) => (
              <div key={i} className="skeleton" style={{ width: w, height: 24, borderRadius: 6 }} />
            ))}
          </div>
          <div style={{ padding: 12 }}>
            <div className="skeleton skeleton-text" style={{ width: "80%", marginBottom: 12 }} />
            <div className="skeleton skeleton-text" style={{ width: "60%" }} />
          </div>
        </div>
        {/* Skeleton main area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "14px 24px", borderBottom: "1px solid var(--border)", background: "var(--bg-card)" }}>
            <div className="skeleton skeleton-text" style={{ width: 180 }} />
          </div>
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <ThinkingOrb state="connecting" size={32} theme="auto" />
          </div>
        </div>
      </div>
    );
  }

  if (!user) return null;
  if (error && !employee) {
    return (
      <div style={{ minHeight: "calc(100vh - 53px)", background: "var(--bg-base)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
        <div style={{ textAlign: "center", maxWidth: 400 }}>
          <div style={{
            width: 64, height: 64, borderRadius: 20, margin: "0 auto 20px",
            background: "rgba(237,95,116,0.08)", border: "1px solid rgba(237,95,116,0.15)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ed5f74" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)", marginBottom: 8 }}>
            Could not load employee
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: 14, marginBottom: 20, lineHeight: 1.6 }}>{error}</p>
          <Link href="/employees" style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "10px 20px", borderRadius: 10,
            background: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600,
            textDecoration: "none", boxShadow: "0 2px 8px rgba(99,91,255,0.25)",
          }}>
            <svg width="14" height="14" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M7.5 9L4.5 6L7.5 3"/></svg>
            Back to Team
          </Link>
        </div>
      </div>
    );
  }
  if (!employee) return null;

  const MEMORY_TYPES = ["working", "episodic", "semantic", "preference", "procedural"];

  return (
    <div className="employee-layout" style={{ display: "flex", height: "calc(100vh - 53px)", background: "var(--bg-base)" }}>
      {/* Sidebar */}
      <div className="employee-sidebar" style={{
        width: 280, borderRight: "1px solid var(--border)", background: "var(--bg-card)",
        display: "flex", flexDirection: "column", flexShrink: 0,
      }}>
        {/* Employee header */}
        <div style={{ overflow: "hidden" }}>
          <div style={{
            height: 3,
            background: `linear-gradient(90deg, ${(ROLE_META[employee.role] || { color: "#635bff" }).color}, ${(ROLE_META[employee.role] || { color: "#635bff" }).color}44)`,
          }} />
          <div style={{ padding: "14px 16px 14px", borderBottom: "1px solid var(--border)" }}>
            <Link href="/employees" style={{
              fontSize: 12, color: "var(--text-muted)", textDecoration: "none",
              display: "inline-flex", alignItems: "center", gap: 4,
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M7.5 9L4.5 6L7.5 3"/></svg>
              Team
            </Link>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10 }}>
              <div style={{ flexShrink: 0 }}>
                {sending || employee.status === "thinking" || employee.status === "tool_execution" ? (
                  <ThinkingOrb state={(STATUS_ORB[employee.status] || STATUS_ORB.idle).orbState} size={32} theme="auto" />
                ) : (
                  <div style={{
                    width: 32, height: 32, borderRadius: 10,
                    background: `${(ROLE_META[employee.role] || { color: "#635bff" }).color}12`,
                    border: `1.5px solid ${(ROLE_META[employee.role] || { color: "#635bff" }).color}30`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 15,
                  }}>
                    {(ROLE_META[employee.role] || { icon: "🤖" }).icon}
                  </div>
                )}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>{employee.name}</div>
                <div style={{
                  fontSize: 12,
                  color: (ROLE_META[employee.role] || { color: "var(--text-muted)" }).color,
                  fontWeight: 500,
                }}>
                  {employee.role}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(6, 1fr)",
          borderBottom: "1px solid var(--border)", padding: "0 4px",
        }}>
          {([
            { id: "chat" as Tab, icon: (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
              </svg>
            ), label: "Chat" },
            { id: "sessions" as Tab, icon: (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a10 10 0 0110 10 10 10 0 01-10 10A10 10 0 012 12 10 10 0 0112 2z"/><path d="M12 6v6l4 2"/>
              </svg>
            ), label: "History" },
            { id: "memories" as Tab, icon: (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/>
              </svg>
            ), label: "Memory" },
            { id: "skills" as Tab, icon: (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
              </svg>
            ), label: "Skills" },
            { id: "schedule" as Tab, icon: (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
            ), label: "Tasks" },
            { id: "settings" as Tab, icon: (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
              </svg>
            ), label: "Config" },
          ]).map(({ id, icon, label }) => {
            const active = sideTab === id;
            return (
              <button
                key={id}
                onClick={() => setSideTab(id)}
                title={label}
                style={{
                  padding: "8px 0", cursor: "pointer",
                  border: "none", background: "transparent",
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
                  color: active ? "var(--accent)" : "var(--text-muted)",
                  borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
                  transition: "color 0.15s",
                }}
              >
                {icon}
                <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.02em" }}>{label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
          {sideTab === "chat" && (
            <div>
              {activeSession ? (
                <div>
                  <div style={{
                    padding: "10px 14px", borderRadius: 10,
                    background: "rgba(11,191,140,0.06)", border: "1px solid rgba(11,191,140,0.15)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#0bbf8c" }} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: "#0bbf8c" }}>Active Session</span>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      Started {new Date(activeSession.started_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </div>
                  </div>
                  <div style={{ marginTop: 12, padding: "0 2px" }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                      Quick Info
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.8 }}>
                      {messages.length} messages this session
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.8 }}>
                      {employee.memory_count ?? 0} total memories
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.8 }}>
                      {employee.session_count ?? 0} total sessions
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: "center", padding: "32px 12px" }}>
                  <div style={{ fontSize: 32, marginBottom: 10 }}>💬</div>
                  <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 4 }}>
                    No active session
                  </p>
                  <p style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 14, lineHeight: 1.5 }}>
                    Start a session to chat with {employee.name}
                  </p>
                  <button
                    onClick={handleStartSession}
                    style={{
                      padding: "8px 20px", borderRadius: 8, border: "none",
                      background: "var(--accent)", color: "#fff", fontSize: 13, fontWeight: 600,
                      cursor: "pointer", boxShadow: "0 2px 8px rgba(99,91,255,0.25)",
                    }}
                  >
                    Start Session
                  </button>
                </div>
              )}
            </div>
          )}

          {sideTab === "sessions" && (
            <div>
              <div style={{
                fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase",
                letterSpacing: "0.05em", marginBottom: 8,
              }}>
                Conversation History ({sessions.length})
              </div>
              {sessions.length === 0 && (
                <div style={{ textAlign: "center", padding: "28px 12px" }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 12, margin: "0 auto 10px",
                    background: "var(--bg-elevated)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
                    </svg>
                  </div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 2 }}>No conversations yet</p>
                  <p style={{ fontSize: 11, color: "var(--text-muted)" }}>Start a session to begin</p>
                </div>
              )}
              {sessions.map((s) => {
                const isActive = activeSession?.id === s.id;
                const isLive = s.status === "active";
                const summary = (s as unknown as Record<string, unknown>).summary as string | undefined;
                const messageCount = (s as unknown as Record<string, unknown>).message_count as number | undefined;
                return (
                  <button
                    key={s.id}
                    onClick={() => handleLoadSession(s.id)}
                    style={{
                      display: "block", width: "100%", textAlign: "left",
                      padding: "10px 12px", borderRadius: 10, marginBottom: 4,
                      border: isActive ? "1px solid var(--accent-border)" : "1px solid transparent",
                      background: isActive ? "var(--accent-bg)" : "transparent",
                      cursor: "pointer", transition: "background 0.15s",
                    }}
                    onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = "var(--bg-base)"; }}
                    onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                        {new Date(s.started_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                        {" "}
                        {new Date(s.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 4,
                        background: isLive ? "rgba(11,191,140,0.1)" : "var(--bg-base)",
                        color: isLive ? "#0bbf8c" : "var(--text-muted)",
                        textTransform: "uppercase",
                      }}>
                        {s.status}
                      </span>
                    </div>
                    {summary && (
                      <div style={{
                        fontSize: 11, color: "var(--text-secondary)", marginTop: 4,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }}>
                        {summary.length > 80 ? summary.slice(0, 80) + "..." : summary}
                      </div>
                    )}
                    {messageCount != null && messageCount > 0 && (
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                        {messageCount} message{messageCount !== 1 ? "s" : ""}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {sideTab === "memories" && (
            <div>
              <input
                type="text"
                placeholder="Search memories..."
                value={memoryFilter}
                onChange={(e) => setMemoryFilter(e.target.value)}
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: 8,
                  border: "1px solid var(--border)", background: "var(--bg-base)",
                  fontSize: 12, color: "var(--text-primary)", outline: "none", marginBottom: 8,
                }}
              />
              {memories.length === 0 && (
                <div style={{ textAlign: "center", padding: "28px 12px" }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 12, margin: "0 auto 10px",
                    background: "var(--bg-elevated)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a10 10 0 0110 10 10 10 0 01-10 10A10 10 0 012 12 10 10 0 0112 2z"/><path d="M12 6v6l4 2"/>
                    </svg>
                  </div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 2 }}>No memories yet</p>
                  <p style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4 }}>Chat with {employee.name} to build memories</p>
                </div>
              )}
              {memories.map((m) => (
                <div
                  key={m.id}
                  style={{
                    padding: "8px 10px", borderRadius: 8, marginBottom: 4,
                    background: "var(--bg-base)", border: "1px solid var(--border)",
                  }}
                >
                  <div className="flex items-center gap-2" style={{ marginBottom: 4 }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                      padding: "1px 6px", borderRadius: 4,
                      background: MEMORY_TYPES.indexOf(m.type) % 2 === 0 ? "var(--accent-bg)" : "var(--success-bg)",
                      color: MEMORY_TYPES.indexOf(m.type) % 2 === 0 ? "var(--accent)" : "var(--success)",
                    }}>
                      {m.type}
                    </span>
                    <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
                      {(m.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: "var(--text-primary)", lineHeight: 1.4, margin: 0 }}>
                    {m.content}
                  </p>
                </div>
              ))}
            </div>
          )}

          {sideTab === "skills" && (
            <div>
              <button
                onClick={async () => {
                  setExtracting(true);
                  try {
                    const result = await extractSkills(employeeId, activeSession?.id);
                    if (result.extracted > 0) {
                      setSkills((prev) => [...result.skills, ...prev]);
                    }
                  } catch { /* ignore */ }
                  setExtracting(false);
                }}
                disabled={extracting}
                style={{
                  width: "100%", padding: "8px 0", borderRadius: 8, border: "1px solid var(--accent-border)",
                  background: "var(--accent-bg)", color: "var(--accent)", fontSize: 12, fontWeight: 600,
                  cursor: extracting ? "default" : "pointer", opacity: extracting ? 0.6 : 1,
                  marginBottom: 10,
                }}
              >
                {extracting ? "Extracting..." : "Extract Skills from Conversations"}
              </button>
              {skills.length === 0 && (
                <div style={{ textAlign: "center", padding: "28px 12px" }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 12, margin: "0 auto 10px",
                    background: "var(--bg-elevated)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                    </svg>
                  </div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 2 }}>No skills learned</p>
                  <p style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4 }}>{employee.name} learns skills from successful conversations</p>
                </div>
              )}
              {skills.map((s) => (
                <div
                  key={s.id}
                  style={{
                    padding: "10px 12px", borderRadius: 8, marginBottom: 6,
                    background: "var(--bg-base)", border: "1px solid var(--border)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                      {s.name}
                    </span>
                    <button
                      onClick={async () => {
                        try {
                          await deactivateSkill(employeeId, s.id);
                          setSkills((prev) => prev.filter((sk) => sk.id !== s.id));
                        } catch { /* ignore */ }
                      }}
                      title="Remove skill"
                      style={{
                        background: "none", border: "none", cursor: "pointer",
                        fontSize: 14, color: "var(--text-muted)", padding: "0 2px",
                        lineHeight: 1,
                      }}
                    >
                      x
                    </button>
                  </div>
                  <p style={{ fontSize: 11, color: "var(--text-secondary)", margin: "0 0 6px", lineHeight: 1.4 }}>
                    {s.description}
                  </p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <span style={{
                      fontSize: 10, padding: "1px 6px", borderRadius: 4,
                      background: "var(--accent-bg)", color: "var(--accent)", fontWeight: 600,
                    }}>
                      Used {s.times_used}x
                    </span>
                    <span style={{
                      fontSize: 10, padding: "1px 6px", borderRadius: 4,
                      background: s.success_rate >= 0.8 ? "var(--success-bg)" : "rgba(245,158,11,0.1)",
                      color: s.success_rate >= 0.8 ? "var(--success)" : "#f59e0b",
                      fontWeight: 600,
                    }}>
                      {(s.success_rate * 100).toFixed(0)}% success
                    </span>
                  </div>
                  {s.trigger_pattern && (
                    <div style={{ marginTop: 6 }}>
                      <span style={{ fontSize: 10, color: "var(--text-muted)" }}>Trigger: </span>
                      <span style={{ fontSize: 10, color: "var(--text-secondary)", fontFamily: "monospace" }}>
                        {s.trigger_pattern}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {sideTab === "schedule" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Scheduled Tasks
                </div>
                <button
                  onClick={() => setShowNewTask(!showNewTask)}
                  style={{
                    padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                    background: "var(--accent-bg)", color: "var(--accent)",
                    border: "1px solid var(--accent-border)", cursor: "pointer",
                  }}
                >{showNewTask ? "Cancel" : "+ New"}</button>
              </div>

              {showNewTask && (
                <div style={{
                  padding: 12, borderRadius: 10, marginBottom: 12,
                  background: "var(--bg-elevated)", border: "1px solid var(--border)",
                }}>
                  <input
                    value={newTaskName}
                    onChange={(e) => setNewTaskName(e.target.value)}
                    placeholder="Task name"
                    style={{
                      width: "100%", padding: "6px 10px", borderRadius: 6, fontSize: 12,
                      border: "1px solid var(--border)", background: "var(--bg-base)",
                      color: "var(--text-primary)", marginBottom: 8,
                    }}
                  />
                  <textarea
                    value={newTaskPrompt}
                    onChange={(e) => setNewTaskPrompt(e.target.value)}
                    placeholder="What should the employee do?"
                    rows={3}
                    style={{
                      width: "100%", padding: "6px 10px", borderRadius: 6, fontSize: 12,
                      border: "1px solid var(--border)", background: "var(--bg-base)",
                      color: "var(--text-primary)", resize: "vertical", marginBottom: 8,
                    }}
                  />
                  <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                    {(["once", "recurring"] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setNewTaskType(t)}
                        style={{
                          padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                          background: newTaskType === t ? "var(--accent-bg)" : "transparent",
                          color: newTaskType === t ? "var(--accent)" : "var(--text-muted)",
                          border: `1px solid ${newTaskType === t ? "var(--accent-border)" : "var(--border)"}`,
                          cursor: "pointer", textTransform: "capitalize",
                        }}
                      >{t}</button>
                    ))}
                  </div>
                  {newTaskType === "recurring" && (
                    <input
                      value={newTaskCron}
                      onChange={(e) => setNewTaskCron(e.target.value)}
                      placeholder="Cron expression (e.g. 0 9 * * 1 = Mon 9am)"
                      style={{
                        width: "100%", padding: "6px 10px", borderRadius: 6, fontSize: 12,
                        border: "1px solid var(--border)", background: "var(--bg-base)",
                        color: "var(--text-primary)", marginBottom: 8,
                      }}
                    />
                  )}
                  <button
                    disabled={savingTask || !newTaskName.trim() || !newTaskPrompt.trim()}
                    onClick={async () => {
                      setSavingTask(true);
                      try {
                        const task = await createScheduledTask({
                          employee_id: employeeId,
                          name: newTaskName.trim(),
                          task_prompt: newTaskPrompt.trim(),
                          schedule_type: newTaskType,
                          cron_expression: newTaskType === "recurring" ? newTaskCron : undefined,
                        });
                        setScheduledTasks((prev) => [task, ...prev]);
                        setShowNewTask(false);
                        setNewTaskName("");
                        setNewTaskPrompt("");
                        setNewTaskCron("");
                      } catch { /* ignore */ }
                      setSavingTask(false);
                    }}
                    style={{
                      width: "100%", padding: "8px 0", borderRadius: 8, fontSize: 12, fontWeight: 700,
                      background: "var(--accent)", color: "#fff", border: "none", cursor: "pointer",
                      opacity: savingTask || !newTaskName.trim() || !newTaskPrompt.trim() ? 0.5 : 1,
                    }}
                  >{savingTask ? "Creating..." : "Create Task"}</button>
                </div>
              )}

              {scheduledTasks.length === 0 && !showNewTask && (
                <div style={{ padding: 20, textAlign: "center", color: "var(--text-muted)", fontSize: 12 }}>
                  No scheduled tasks yet. Create one to have this employee work on tasks automatically.
                </div>
              )}

              {scheduledTasks.map((task) => {
                const isActive = task.is_active === true || task.is_active === 1;
                return (
                  <div key={task.id} style={{
                    padding: 12, borderRadius: 10, marginBottom: 8,
                    background: "var(--bg-card)", border: "1px solid var(--border)",
                    opacity: isActive ? 1 : 0.6,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{task.name}</div>
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                          {task.schedule_type === "recurring" ? `Recurring: ${task.cron_expression}` : "One-time"}
                          {task.run_count > 0 && ` · ${task.run_count} runs`}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button
                          onClick={async () => {
                            try {
                              await runScheduledTaskNow(task.id);
                              const updated = await listScheduledTasks(employeeId);
                              setScheduledTasks(updated.tasks);
                            } catch { /* ignore */ }
                          }}
                          title="Run now"
                          style={{
                            padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                            background: "var(--success-bg)", color: "var(--success)",
                            border: "1px solid var(--success-border)", cursor: "pointer",
                          }}
                        >Run</button>
                        <button
                          onClick={async () => {
                            try {
                              await deleteScheduledTask(task.id);
                              setScheduledTasks((prev) => prev.filter((t) => t.id !== task.id));
                            } catch { /* ignore */ }
                          }}
                          title="Delete"
                          style={{
                            padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600,
                            background: "rgba(237,95,116,0.06)", color: "var(--danger)",
                            border: "1px solid rgba(237,95,116,0.15)", cursor: "pointer",
                          }}
                        >Del</button>
                      </div>
                    </div>
                    <div style={{
                      fontSize: 11, color: "var(--text-secondary)", marginTop: 4,
                      padding: "6px 8px", borderRadius: 6, background: "var(--bg-elevated)",
                      whiteSpace: "pre-wrap", maxHeight: 60, overflow: "hidden",
                    }}>{task.task_prompt}</div>
                    {task.last_run_status && (
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }}>
                        Last run: <span style={{
                          color: task.last_run_status === "success" ? "var(--success)" : "var(--danger)",
                          fontWeight: 600,
                        }}>{task.last_run_status}</span>
                        {task.last_run_at && ` · ${new Date(task.last_run_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`}
                      </div>
                    )}
                    {isActive && task.next_run_at && (
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                        Next run: {new Date(task.next_run_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {sideTab === "settings" && (
            <div>
              {/* Persona editor */}
              <div style={{
                padding: 12, borderRadius: 10, marginBottom: 10,
                background: "var(--bg-base)", border: "1px solid var(--border)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>
                  </svg>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Persona
                  </span>
                </div>
                <textarea
                  value={editPersona}
                  onChange={(e) => setEditPersona(e.target.value)}
                  rows={4}
                  style={{
                    width: "100%", padding: "8px 10px", borderRadius: 8,
                    border: "1px solid var(--border)", background: "var(--bg-card)",
                    fontSize: 12, color: "var(--text-primary)", outline: "none",
                    resize: "vertical", fontFamily: "inherit", lineHeight: 1.5,
                  }}
                />
                <button
                  onClick={async () => {
                    setSavingPersona(true);
                    try {
                      const updated = await updateEmployee(employeeId, { persona: editPersona });
                      setEmployee(updated);
                    } catch { /* ignore */ }
                    setSavingPersona(false);
                  }}
                  disabled={savingPersona || editPersona === (employee.persona || "")}
                  style={{
                    marginTop: 6, width: "100%", padding: "7px 0", borderRadius: 8,
                    border: "none", fontSize: 11, fontWeight: 700, cursor: "pointer",
                    background: editPersona !== (employee.persona || "") ? "var(--accent)" : "var(--bg-elevated)",
                    color: editPersona !== (employee.persona || "") ? "#fff" : "var(--text-muted)",
                    opacity: savingPersona ? 0.6 : 1,
                    transition: "all 0.15s",
                  }}
                >
                  {savingPersona ? "Saving..." : "Save Persona"}
                </button>
              </div>

              {/* Model selection */}
              <div style={{
                padding: 12, borderRadius: 10, marginBottom: 10,
                background: "var(--bg-base)", border: "1px solid var(--border)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
                  </svg>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    LLM Model
                  </span>
                </div>
                <select
                  value={(employee.config as Record<string, unknown>)?.model as string || "default"}
                  onChange={async (e) => {
                    const model = e.target.value === "default" ? undefined : e.target.value;
                    try {
                      const config = { ...(employee.config || {}), model: model || null };
                      const updated = await updateEmployee(employeeId, { config });
                      setEmployee(updated);
                    } catch { /* ignore */ }
                  }}
                  style={{
                    width: "100%", padding: "8px 10px", borderRadius: 8,
                    border: "1px solid var(--border)", background: "var(--bg-card)",
                    fontSize: 12, color: "var(--text-primary)", cursor: "pointer",
                    appearance: "none",
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E")`,
                    backgroundRepeat: "no-repeat",
                    backgroundPosition: "right 10px center",
                    paddingRight: 28,
                  }}
                >
                  <option value="default">Default (auto-select)</option>
                  <option value="nvidia/llama-3.1-nemotron-ultra-253b-v1">Nemotron Ultra 253B</option>
                  <option value="nvidia/llama-3.3-nemotron-super-49b-v1">Nemotron Super 49B</option>
                  <option value="deepseek/deepseek-r1">DeepSeek R1</option>
                  <option value="google/gemini-2.5-flash-preview">Gemini 2.5 Flash</option>
                  <option value="meta-llama/llama-4-maverick">Llama 4 Maverick</option>
                  <option value="qwen/qwen3-235b-a22b">Qwen 3 235B</option>
                </select>
                <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6, lineHeight: 1.4 }}>
                  Override the LLM used for this employee&apos;s conversations
                </p>
              </div>

              {/* Tool permissions */}
              <div style={{
                padding: 12, borderRadius: 10, marginBottom: 10,
                background: "var(--bg-base)", border: "1px solid var(--border)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>
                  </svg>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Tool Permissions
                  </span>
                </div>
                {permissions.length === 0 && (
                  <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: "8px 0" }}>
                    No tool permissions configured
                  </p>
                )}
                {permissions.map((perm) => (
                  <div
                    key={perm.id}
                    style={{
                      padding: "7px 10px", borderRadius: 8, marginBottom: 3,
                      background: "var(--bg-card)", border: "1px solid var(--border)",
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                        {perm.tool}
                      </div>
                      <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{perm.action}</div>
                    </div>
                    <select
                      value={perm.permission}
                      onChange={async (e) => {
                        try {
                          const updated = await updateEmployeePermission(employeeId, perm.tool, perm.action, e.target.value);
                          setPermissions((prev) => prev.map((p) => p.id === perm.id ? updated : p));
                        } catch { /* ignore */ }
                      }}
                      style={{
                        padding: "3px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700,
                        border: "1px solid var(--border)", background: "transparent",
                        color: perm.permission === "allow" ? "#22c55e" : perm.permission === "deny" ? "#ef4444" : "#f59e0b",
                        cursor: "pointer",
                      }}
                    >
                      <option value="allow">Allow</option>
                      <option value="ask">Ask</option>
                      <option value="deny">Deny</option>
                    </select>
                  </div>
                ))}
              </div>

              {/* Employee info */}
              <div style={{
                padding: 12, borderRadius: 10,
                background: "var(--bg-base)", border: "1px solid var(--border)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
                  </svg>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-primary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Info
                  </span>
                </div>
                <div style={{ display: "grid", gap: 6 }}>
                  {[
                    { label: "Created", value: new Date(employee.created_at).toLocaleDateString() },
                    { label: "Status", value: employee.status, color: employee.status === "idle" ? "#22c55e" : "var(--accent)" },
                    { label: "ID", value: employee.id.slice(0, 16) + "...", mono: true },
                  ].map(({ label, value, color, mono }) => (
                    <div key={label} style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      padding: "4px 0",
                    }}>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{label}</span>
                      <span style={{
                        fontSize: mono ? 10 : 11, fontWeight: 600,
                        color: color || "var(--text-primary)",
                        fontFamily: mono ? "monospace" : "inherit",
                      }}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Chat header */}
        <div className="chat-header" style={{
          padding: "14px 24px", borderBottom: "1px solid var(--border)",
          background: "var(--bg-card)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {(sending || employee.status === "thinking" || employee.status === "tool_execution") && (
              <ThinkingOrb state={(STATUS_ORB[employee.status] || STATUS_ORB.thinking).orbState} size={20} theme="auto" />
            )}
            <span style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>
              Chat with {employee.name}
            </span>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 20,
              background: employee.status !== "idle" && sending
                ? "rgba(99,91,255,0.1)" : "rgba(11,191,140,0.1)",
              color: employee.status !== "idle" && sending
                ? "#635bff" : "#0bbf8c",
              textTransform: "uppercase", letterSpacing: "0.05em",
            }}>
              {(STATUS_ORB[employee.status] || STATUS_ORB.idle).label}
            </span>
          </div>
          {activeSession && activeSession.status === "active" && (
            <button
              onClick={handleEndSession}
              style={{
                padding: "5px 12px", borderRadius: 8, border: "1px solid var(--border)",
                background: "transparent", fontSize: 12, fontWeight: 500,
                color: "var(--text-muted)", cursor: "pointer", transition: "all 0.15s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--danger)"; e.currentTarget.style.color = "var(--danger)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}
            >
              End Session
            </button>
          )}
          {error && (
            <span style={{ fontSize: 12, color: "#ed5f74" }}>{error}</span>
          )}
        </div>

        {/* Messages */}
        <div className="chat-messages" style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {!activeSession && messages.length === 0 && (() => {
            const roleColor = (ROLE_META[employee.role] || { color: "#635bff" }).color;
            const SUGGESTIONS: Record<string, string[]> = {
              "Business Analyst": ["Analyze the market for our product", "Create a competitive analysis", "Draft user stories for the next sprint"],
              "Researcher": ["Research the latest trends in AI", "Find papers on retrieval-augmented generation", "Summarize key findings from our data"],
              "Architect": ["Design the system architecture for a new feature", "Review our database schema", "Propose a microservices migration plan"],
              "Software Engineer": ["Implement the authentication module", "Debug the failing API endpoint", "Write unit tests for the user service"],
              "QA Engineer": ["Create a test plan for the login flow", "Run regression tests on the API", "Document the edge cases we need to cover"],
              "Technical Writer": ["Write API documentation for our endpoints", "Create a user guide for onboarding", "Draft release notes for v2.0"],
            };
            const prompts = SUGGESTIONS[employee.role] || ["Help me with a task", "What can you do?", "Let's brainstorm ideas"];
            return (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", padding: "40px 24px" }}>
                <div style={{ textAlign: "center", maxWidth: 520, width: "100%" }}>
                  {/* Gradient orb backdrop */}
                  <div style={{
                    width: 80, height: 80, borderRadius: 24, margin: "0 auto 24px",
                    background: `linear-gradient(135deg, ${roleColor}18, ${roleColor}08)`,
                    border: `1.5px solid ${roleColor}25`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 36, position: "relative",
                    boxShadow: `0 8px 32px ${roleColor}12`,
                  }}>
                    {(ROLE_META[employee.role] || { icon: "🤖" }).icon}
                    <div style={{
                      position: "absolute", bottom: -2, right: -2,
                      width: 20, height: 20, borderRadius: 8,
                      background: "var(--success)", border: "2px solid var(--bg-base)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    </div>
                  </div>
                  <h2 style={{
                    fontSize: 24, fontWeight: 800, color: "var(--text-primary)",
                    marginBottom: 6, letterSpacing: "-0.03em",
                  }}>
                    {employee.name}
                  </h2>
                  <div style={{
                    fontSize: 13, fontWeight: 600, color: roleColor,
                    marginBottom: 8,
                  }}>
                    {employee.role}
                  </div>
                  <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 28, maxWidth: 380, margin: "0 auto 28px" }}>
                    {employee.name} remembers everything across sessions and learns new skills over time. Start a conversation to begin.
                  </p>
                  <button
                    onClick={handleStartSession}
                    style={{
                      padding: "12px 32px", borderRadius: 12, border: "none",
                      background: `linear-gradient(135deg, ${roleColor}, ${roleColor}cc)`,
                      color: "#fff", fontSize: 15, fontWeight: 700,
                      cursor: "pointer",
                      boxShadow: `0 4px 16px ${roleColor}40`,
                      transition: "all 0.2s",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = `0 6px 24px ${roleColor}50`; }}
                    onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = `0 4px 16px ${roleColor}40`; }}
                  >
                    Start Session
                  </button>

                  {/* Suggested prompts */}
                  <div style={{ marginTop: 36, textAlign: "left" }}>
                    <div style={{
                      fontSize: 11, fontWeight: 700, color: "var(--text-muted)",
                      textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10,
                      textAlign: "center",
                    }}>
                      Try asking
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {prompts.map((prompt, i) => (
                        <button
                          key={i}
                          onClick={async () => {
                            await handleStartSession();
                            setInput(prompt);
                          }}
                          style={{
                            padding: "12px 16px", borderRadius: 12,
                            background: "var(--bg-card)", border: "1px solid var(--border)",
                            cursor: "pointer", transition: "all 0.15s",
                            display: "flex", alignItems: "center", gap: 10,
                            textAlign: "left", width: "100%",
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.borderColor = `${roleColor}40`; e.currentTarget.style.background = `${roleColor}06`; }}
                          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.background = "var(--bg-card)"; }}
                        >
                          <div style={{
                            width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                            background: `${roleColor}10`, border: `1px solid ${roleColor}20`,
                            display: "flex", alignItems: "center", justifyContent: "center",
                          }}>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={roleColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                            </svg>
                          </div>
                          <span style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 500 }}>{prompt}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Delegation tip */}
                  <div style={{
                    marginTop: 24, padding: "14px 18px", borderRadius: 12,
                    background: "rgba(99,91,255,0.04)", border: "1px solid rgba(99,91,255,0.1)",
                    textAlign: "left", display: "flex", alignItems: "flex-start", gap: 12,
                  }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                      background: "rgba(99,91,255,0.08)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#635bff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>
                      </svg>
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)", marginBottom: 4 }}>Team Delegation</div>
                      <p style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, margin: 0 }}>
                        {employee.name} can delegate tasks to other team members for cross-functional work.
                        <button
                          onClick={() => setShowDelegationInfo(true)}
                          style={{ background: "none", border: "none", padding: 0, fontSize: 12, fontWeight: 600, color: "var(--accent)", cursor: "pointer", marginLeft: 4 }}
                        >
                          Learn more
                        </button>
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          {activeExecutionId && (
            <ExecutionProgress
              executionId={activeExecutionId}
              onDismiss={() => setActiveExecutionId(null)}
            />
          )}

          {messages.map((msg) => {
            if (msg.role === "tool_calls") {
              let calls: { function: { name: string; arguments: string } }[] = [];
              try { calls = JSON.parse(msg.content); } catch { /* skip */ }
              if (calls.length === 0) return null;
              return (
                <div key={msg.id} style={{ display: "flex", justifyContent: "flex-start", marginBottom: 8 }}>
                  <div style={{
                    maxWidth: "80%", padding: "8px 14px", borderRadius: 10,
                    background: "var(--bg-card)", border: "1px dashed var(--accent-border)",
                    fontSize: 12, color: "var(--text-secondary)",
                  }}>
                    {calls.map((tc, i) => {
                      let argSummary = "";
                      try {
                        const args = JSON.parse(tc.function.arguments);
                        argSummary = Object.entries(args).map(([k, v]) => {
                          const val = typeof v === "string" && v.length > 60 ? v.slice(0, 60) + "..." : String(v);
                          return `${k}: ${val}`;
                        }).join(", ");
                      } catch { argSummary = tc.function.arguments; }
                      return (
                        <div key={i} style={{ marginBottom: i < calls.length - 1 ? 6 : 0 }}>
                          <span style={{ fontWeight: 600, color: "var(--accent)", fontFamily: "monospace" }}>
                            {tc.function.name}
                          </span>
                          {argSummary && (
                            <span style={{ color: "var(--text-muted)", marginLeft: 6, fontFamily: "monospace", fontSize: 11 }}>
                              ({argSummary})
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            }

            if (msg.role === "tool_result") {
              let result: { tool?: string; result?: string; error?: string } = {};
              try {
                const parsed = JSON.parse(msg.content);
                const inner = typeof parsed.result === "string" ? JSON.parse(parsed.result) : parsed;
                result = { tool: parsed.tool, ...inner };
              } catch { /* skip */ }
              const isError = !result.error ? false : true;
              const display = result.error || (typeof result.result === "string" ? result.result : JSON.stringify(result.result));
              const truncated = display && display.length > 200 ? display.slice(0, 200) + "..." : display;
              return (
                <div key={msg.id} style={{ display: "flex", justifyContent: "flex-start", marginBottom: 8 }}>
                  <div style={{
                    maxWidth: "80%", padding: "6px 12px", borderRadius: 8,
                    background: isError ? "rgba(237,95,116,0.06)" : "rgba(11,191,140,0.06)",
                    border: `1px solid ${isError ? "rgba(237,95,116,0.2)" : "rgba(11,191,140,0.2)"}`,
                    fontSize: 12, fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-word",
                    color: isError ? "#ed5f74" : "var(--text-secondary)",
                  }}>
                    {result.tool && (
                      <span style={{ fontWeight: 600, marginRight: 6, color: isError ? "#ed5f74" : "#0bbf8c" }}>
                        {isError ? "x" : "v"} {result.tool}:
                      </span>
                    )}
                    {truncated}
                  </div>
                </div>
              );
            }

            const isUser = msg.role === "user";
            if (msg.role !== "user" && msg.role !== "employee") return null;
            return (
              <div key={msg.id} style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", marginBottom: 12 }}>
                <div
                  className={`msg-bubble md-content ${isUser ? "md-user" : ""}`}
                  style={{
                    maxWidth: "70%", padding: "10px 16px", borderRadius: 14,
                    background: isUser ? "var(--accent)" : "var(--bg-card)",
                    color: isUser ? "#fff" : "var(--text-primary)",
                    border: isUser ? "none" : "1px solid var(--border)",
                    wordBreak: "break-word",
                  }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  <div style={{
                    fontSize: 11, marginTop: 4,
                    color: isUser ? "rgba(255,255,255,0.6)" : "var(--text-muted)",
                    textAlign: "right",
                  }}>
                    {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
              </div>
            );
          })}

          {sending && (
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 12 }}>
              <div style={{
                padding: "10px 20px", borderRadius: 14,
                background: "var(--bg-card)", border: "1px solid var(--border)",
                display: "flex", alignItems: "center", gap: 10,
              }}>
                <ThinkingOrb state={(STATUS_ORB[employee.status] || STATUS_ORB.thinking).orbState} size={20} theme="auto" />
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  {(STATUS_ORB[employee.status] || STATUS_ORB.thinking).label}
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        {activeSession && activeSession.status === "active" && (
          <div className="chat-input-area" style={{ padding: "14px 24px 12px", borderTop: "1px solid var(--border)", background: "var(--bg-card)" }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 10 }}>
              <div style={{
                flex: 1, position: "relative", borderRadius: 14,
                border: "1px solid var(--border)", background: "var(--bg-base)",
                transition: "border-color 0.15s, box-shadow 0.15s",
              }}
                className="chat-input-wrap"
              >
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`Message ${employee.name}...`}
                  rows={1}
                  style={{
                    width: "100%", padding: "12px 16px", borderRadius: 14,
                    border: "none", background: "transparent",
                    color: "var(--text-primary)", fontSize: 14, outline: "none",
                    resize: "none", fontFamily: "inherit", lineHeight: 1.5,
                    maxHeight: 120, overflowY: "auto",
                  }}
                  onInput={(e) => {
                    const t = e.currentTarget;
                    t.style.height = "auto";
                    t.style.height = Math.min(t.scrollHeight, 120) + "px";
                  }}
                  onFocus={(e) => {
                    const wrap = e.target.closest(".chat-input-wrap") as HTMLElement;
                    if (wrap) { wrap.style.borderColor = "var(--accent)"; wrap.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }
                  }}
                  onBlur={(e) => {
                    const wrap = e.target.closest(".chat-input-wrap") as HTMLElement;
                    if (wrap) { wrap.style.borderColor = "var(--border)"; wrap.style.boxShadow = "none"; }
                  }}
                />
              </div>
              <button
                onClick={handleSend}
                disabled={!input.trim() || sending}
                style={{
                  width: 42, height: 42, borderRadius: 12, border: "none",
                  background: "var(--accent)", color: "#fff",
                  cursor: !input.trim() || sending ? "default" : "pointer",
                  opacity: !input.trim() || sending ? 0.4 : 1,
                  transition: "all 0.15s", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  boxShadow: !input.trim() || sending ? "none" : "0 2px 8px rgba(99,91,255,0.3)",
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6, paddingLeft: 2 }}>
              Enter to send · Shift+Enter for new line
            </p>
          </div>
        )}
      </div>

      {/* Delegation Info Modal */}
      {showDelegationInfo && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 200,
            background: "rgba(0,0,0,0.4)", backdropFilter: "blur(4px)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: 24, animation: "fadeIn 0.15s ease-out",
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowDelegationInfo(false); }}
        >
          <div style={{
            width: "100%", maxWidth: 520, borderRadius: 16,
            background: "var(--bg-card)", border: "1px solid var(--border)",
            boxShadow: "0 24px 64px rgba(0,0,0,0.15)",
            overflow: "hidden",
          }}>
            {/* Modal header */}
            <div style={{
              padding: "20px 24px", borderBottom: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.02em" }}>
                How Delegation Works
              </h3>
              <button
                onClick={() => setShowDelegationInfo(false)}
                style={{
                  background: "none", border: "none", fontSize: 18,
                  color: "var(--text-muted)", cursor: "pointer", padding: "4px 8px",
                  borderRadius: 6, lineHeight: 1,
                }}
              >
                &times;
              </button>
            </div>

            {/* Modal body */}
            <div style={{ padding: "24px", overflowY: "auto", maxHeight: "70vh" }}>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.7, margin: "0 0 20px" }}>
                Each employee can delegate tasks to other team members. When they delegate, they pass along the full context of your conversation so the other employee understands what&apos;s needed.
              </p>

              {/* Step-by-step */}
              <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 24 }}>
                {[
                  { step: "1", title: "You ask an employee", desc: "Chat with any employee about your project. For example, ask Arc to design a system." },
                  { step: "2", title: "Request delegation", desc: "Tell the employee to delegate work to a teammate. Example: \"Delegate the business analysis to Sage\"" },
                  { step: "3", title: "Context is transferred", desc: "The employee packages up what you discussed and sends it to the other employee with full context." },
                  { step: "4", title: "Result comes back", desc: "The delegated employee does the work and the result appears in your conversation. You never need to switch chats." },
                ].map((item) => (
                  <div key={item.step} style={{ display: "flex", gap: 14 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                      background: "var(--accent-bg)", border: "1px solid var(--accent-border)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 13, fontWeight: 700, color: "var(--accent)",
                    }}>
                      {item.step}
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", marginBottom: 2 }}>
                        {item.title}
                      </div>
                      <div style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5 }}>
                        {item.desc}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Example phrases */}
              <div style={{
                padding: "16px 18px", borderRadius: 10,
                background: "var(--bg-base)", border: "1px solid var(--border)",
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>
                  Try saying
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[
                    "\"Ask Sage to analyze the business requirements for this\"",
                    "\"Delegate the code review to Sentinel\"",
                    "\"Have Scout research competitors in this space\"",
                    "\"Get Scribe to write documentation for this API\"",
                  ].map((phrase) => (
                    <div key={phrase} style={{
                      fontSize: 13, color: "var(--text-secondary)", fontStyle: "italic",
                      padding: "6px 10px", borderRadius: 6, background: "var(--bg-card)",
                    }}>
                      {phrase}
                    </div>
                  ))}
                </div>
              </div>

              {/* Your team */}
              <div style={{ marginTop: 20 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10 }}>
                  Your Team
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  {Object.entries(ROLE_META).map(([role, meta]) => {
                    const names: Record<string, string> = {
                      "Architect": "Arc", "Business Analyst": "Sage", "Researcher": "Scout",
                      "Software Engineer": "Atlas", "QA Engineer": "Sentinel", "Technical Writer": "Scribe",
                    };
                    return (
                      <div key={role} style={{
                        display: "flex", alignItems: "center", gap: 8,
                        padding: "8px 10px", borderRadius: 8, background: "var(--bg-base)",
                      }}>
                        <span style={{ fontSize: 16 }}>{meta.icon}</span>
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                            {names[role] || role}
                          </div>
                          <div style={{ fontSize: 11, color: meta.color }}>{role}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Modal footer */}
            <div style={{ padding: "16px 24px", borderTop: "1px solid var(--border)", textAlign: "right" }}>
              <button
                onClick={() => setShowDelegationInfo(false)}
                style={{
                  padding: "8px 20px", borderRadius: 8, border: "none",
                  background: "var(--accent)", color: "#fff", fontSize: 13, fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
