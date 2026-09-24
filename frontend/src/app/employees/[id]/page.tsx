"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import {
  getEmployee, listEmployeeSessions, createEmployeeSession, getSessionWithMessages,
  sendEmployeeMessage, endEmployeeSession, listMemories, listSkills, extractSkills,
  deactivateSkill, type Employee, type EmployeeSession, type SessionMessage,
  type Memory, type EmployeeSkill,
} from "@/lib/api";
import { ThinkingOrb, type OrbState } from "thinking-orbs";

type Tab = "chat" | "memories" | "sessions" | "skills";

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
      const result = await sendEmployeeMessage(activeSession.id, text);
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
      <div style={{ minHeight: "100vh", background: "var(--bg-base)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <ThinkingOrb state="connecting" size={64} theme="auto" />
      </div>
    );
  }

  if (!user) return null;
  if (error && !employee) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--bg-base)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ color: "#ed5f74", fontSize: 14, marginBottom: 16 }}>{error}</p>
          <Link href="/employees" style={{ color: "var(--accent)", fontSize: 14 }}>Back to Team</Link>
        </div>
      </div>
    );
  }
  if (!employee) return null;

  const MEMORY_TYPES = ["working", "episodic", "semantic", "preference", "procedural"];

  return (
    <div style={{ display: "flex", height: "calc(100vh - 41px)", background: "var(--bg-base)" }}>
      {/* Sidebar */}
      <div style={{
        width: 260, borderRight: "1px solid var(--border)", background: "var(--bg-card)",
        display: "flex", flexDirection: "column", flexShrink: 0,
      }}>
        {/* Employee header */}
        <div style={{ padding: "16px 16px 12px", borderBottom: "1px solid var(--border)" }}>
          <Link href="/employees" style={{ fontSize: 12, color: "var(--text-muted)", textDecoration: "none" }}>
            &larr; Team
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
            <div style={{ flexShrink: 0 }}>
              {sending || employee.status === "thinking" || employee.status === "tool_execution" ? (
                <ThinkingOrb state={(STATUS_ORB[employee.status] || STATUS_ORB.idle).orbState} size={32} theme="auto" />
              ) : (
                <div style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: `${(ROLE_META[employee.role] || { color: "#635bff" }).color}12`,
                  border: `1.5px solid ${(ROLE_META[employee.role] || { color: "#635bff" }).color}30`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 15,
                }}>
                  {(ROLE_META[employee.role] || { icon: "🤖" }).icon}
                </div>
              )}
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)" }}>{employee.name}</div>
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

        {/* Tabs */}
        <div className="flex" style={{ borderBottom: "1px solid var(--border)" }}>
          {(["chat", "sessions", "memories", "skills"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setSideTab(tab)}
              style={{
                flex: 1, padding: "10px 0", fontSize: 12, fontWeight: 600, cursor: "pointer",
                border: "none", background: "transparent",
                color: sideTab === tab ? "var(--accent)" : "var(--text-muted)",
                borderBottom: sideTab === tab ? "2px solid var(--accent)" : "2px solid transparent",
                textTransform: "capitalize",
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
          {sideTab === "chat" && (
            <div>
              {activeSession ? (
                <div style={{ fontSize: 13 }}>
                  <div style={{ color: "var(--text-secondary)", marginBottom: 8 }}>
                    Active session
                  </div>
                  <div style={{ padding: "8px 12px", borderRadius: 8, background: "var(--success-bg)", border: "1px solid var(--success-border)", fontSize: 12, color: "var(--success)", marginBottom: 12 }}>
                    Started {new Date(activeSession.started_at).toLocaleTimeString()}
                  </div>
                  <button
                    onClick={handleEndSession}
                    style={{
                      width: "100%", padding: "8px 0", borderRadius: 8, border: "1px solid var(--border)",
                      background: "var(--bg-base)", color: "var(--text-secondary)", fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    End Session
                  </button>
                </div>
              ) : (
                <div style={{ textAlign: "center", padding: "24px 8px" }}>
                  <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 12 }}>No active session</p>
                  <button
                    onClick={handleStartSession}
                    style={{
                      padding: "8px 16px", borderRadius: 8, border: "none",
                      background: "var(--accent)", color: "#fff", fontSize: 13, fontWeight: 600,
                      cursor: "pointer",
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
              {sessions.length === 0 && (
                <p style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", padding: 16 }}>No sessions yet</p>
              )}
              {sessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => handleLoadSession(s.id)}
                  style={{
                    display: "block", width: "100%", textAlign: "left",
                    padding: "10px 12px", borderRadius: 8, marginBottom: 4,
                    border: activeSession?.id === s.id ? "1px solid var(--accent-border)" : "1px solid transparent",
                    background: activeSession?.id === s.id ? "var(--accent-bg)" : "transparent",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                    {new Date(s.started_at).toLocaleDateString()}
                  </div>
                  <div className="flex items-center gap-2" style={{ marginTop: 2 }}>
                    <span style={{
                      width: 6, height: 6, borderRadius: "50%",
                      background: s.status === "active" ? "var(--success)" : "var(--text-muted)",
                    }} />
                    <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "capitalize" }}>
                      {s.status}
                    </span>
                  </div>
                </button>
              ))}
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
                <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: 16 }}>
                  No memories yet. Chat with {employee.name} to build memories.
                </p>
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
                <p style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: 16 }}>
                  No skills yet. {employee.name} learns skills from successful conversations.
                </p>
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
        </div>
      </div>

      {/* Main chat area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Chat header */}
        <div style={{
          padding: "12px 20px", borderBottom: "1px solid var(--border)",
          background: "var(--bg-card)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {(sending || employee.status === "thinking" || employee.status === "tool_execution") && (
              <ThinkingOrb state={(STATUS_ORB[employee.status] || STATUS_ORB.thinking).orbState} size={20} theme="auto" />
            )}
            <span style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)" }}>
              {employee.name}
            </span>
            <span style={{
              fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
              background: employee.status !== "idle" && sending
                ? "rgba(99,91,255,0.1)" : "rgba(11,191,140,0.1)",
              color: employee.status !== "idle" && sending
                ? "#635bff" : "#0bbf8c",
              textTransform: "uppercase", letterSpacing: "0.05em",
            }}>
              {(STATUS_ORB[employee.status] || STATUS_ORB.idle).label}
            </span>
          </div>
          {error && (
            <span style={{ fontSize: 12, color: "#ed5f74" }}>{error}</span>
          )}
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {!activeSession && messages.length === 0 && (
            <div style={{ textAlign: "center", padding: "80px 24px" }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>{employee.avatar_url ? "" : "\u{1f4ac}"}</div>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 }}>
                Chat with {employee.name}
              </h2>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", maxWidth: 400, margin: "0 auto 24px" }}>
                Start a session to begin a conversation. {employee.name} remembers context across sessions.
              </p>
              <button
                onClick={handleStartSession}
                style={{
                  padding: "10px 24px", borderRadius: 10, border: "none",
                  background: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Start Session
              </button>
            </div>
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
                <div style={{
                  maxWidth: "70%", padding: "10px 16px", borderRadius: 14,
                  background: isUser ? "var(--accent)" : "var(--bg-card)",
                  color: isUser ? "#fff" : "var(--text-primary)",
                  border: isUser ? "none" : "1px solid var(--border)",
                  fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word",
                }}>
                  {msg.content}
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
          <div style={{ padding: "12px 20px", borderTop: "1px solid var(--border)", background: "var(--bg-card)" }}>
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Message ${employee.name}...`}
                rows={1}
                style={{
                  flex: 1, padding: "10px 14px", borderRadius: 12,
                  border: "1px solid var(--border)", background: "var(--bg-base)",
                  color: "var(--text-primary)", fontSize: 14, outline: "none",
                  resize: "none", fontFamily: "inherit", lineHeight: 1.5,
                  maxHeight: 120, overflowY: "auto",
                }}
                onInput={(e) => {
                  const t = e.currentTarget;
                  t.style.height = "auto";
                  t.style.height = Math.min(t.scrollHeight, 120) + "px";
                }}
                onFocus={(e) => e.target.style.borderColor = "var(--accent)"}
                onBlur={(e) => e.target.style.borderColor = "var(--border)"}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || sending}
                style={{
                  padding: "10px 18px", borderRadius: 12, border: "none",
                  background: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600,
                  cursor: !input.trim() || sending ? "default" : "pointer",
                  opacity: !input.trim() || sending ? 0.5 : 1,
                  transition: "opacity 0.15s", flexShrink: 0,
                }}
              >
                Send
              </button>
            </div>
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
              Press Enter to send, Shift+Enter for new line
            </p>
          </div>
        )}
      </div>

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
