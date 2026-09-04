"use client";

import { useState, useRef, useEffect } from "react";
import { AGENT_CONFIG } from "@/lib/constants";
import { useToast } from "./Toast";
import { callEmployeeStream, getConversation, applyFileChanges } from "@/lib/api";

interface Props {
  projectId: string;
}

interface ChatMessage {
  role: string;
  content: string;
  timestamp?: string;
  hasFileBlocks?: boolean;
}

function parseFileBlocks(text: string): { path: string; content: string }[] {
  const blocks: { path: string; content: string }[] = [];
  const regex = /=== FILE: (.+?) ===\n([\s\S]*?)(?:=== END FILE ===|(?==== FILE:)|$)/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    const content = match[2].trim();
    if (content) blocks.push({ path: match[1].trim(), content });
  }
  return blocks;
}

export default function CallEmployee({ projectId }: Props) {
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (selectedRole) {
      getConversation(projectId, selectedRole).then((data) => {
        const msgs: ChatMessage[] = (data.messages || []).map((m: { role: string; content: string }) => ({
          ...m,
          hasFileBlocks: m.role === "assistant" && parseFileBlocks(m.content).length > 0,
        }));
        setMessages(msgs);
      });
    }
  }, [selectedRole, projectId]);

  async function handleSend() {
    if (!message.trim() || !selectedRole || loading) return;

    const userMsg = message;
    setMessage("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg, timestamp: new Date().toLocaleTimeString() }]);
    setLoading(true);

    setMessages((prev) => [...prev, { role: "assistant", content: "", timestamp: new Date().toLocaleTimeString() }]);

    try {
      await callEmployeeStream(
        projectId, selectedRole, userMsg,
        (token) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.role === "assistant") {
              updated[updated.length - 1] = { ...last, content: last.content + token };
            }
            return updated;
          });
        },
        () => {
          setLoading(false);
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.role === "assistant") {
              updated[updated.length - 1] = { ...last, hasFileBlocks: parseFileBlocks(last.content).length > 0 };
            }
            return updated;
          });
        },
        (error) => {
          toast("error", "Connection failed", error);
          setLoading(false);
        }
      );
    } catch {
      toast("error", "Connection failed", `Could not reach ${AGENT_CONFIG[selectedRole]?.label || "this employee"}. Backend may be offline.`);
      setLoading(false);
    }
  }

  async function handleApplyFiles(content: string) {
    const blocks = parseFileBlocks(content);
    if (blocks.length === 0) return;
    setApplying(true);
    try {
      const result = await applyFileChanges(projectId, blocks);
      toast("success", "Files updated", `Applied changes to ${result.count} file(s): ${result.updated_files.join(", ")}`);
    } catch (e) {
      toast("error", "Apply failed", e instanceof Error ? e.message : "Could not apply file changes.");
    } finally {
      setApplying(false);
    }
  }

  if (!selectedRole) {
    return (
      <div className="card p-5">
        <h3 className="font-semibold mb-1 text-[15px]" style={{ color: "var(--text-primary)" }}>Call an Employee</h3>
        <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>Talk directly to any team member</p>
        <div className="grid grid-cols-2 gap-2.5">
          {Object.entries(AGENT_CONFIG).map(([role, config]) => (
            <button
              key={role}
              onClick={() => setSelectedRole(role)}
              className="flex items-center gap-3 p-3.5 rounded-xl transition-all text-left cursor-pointer"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--accent-border)";
                e.currentTarget.style.background = "var(--bg-card-hover)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.background = "var(--bg-base)";
              }}
            >
              <span className="text-xl">{config.icon}</span>
              <div>
                <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{config.label}</div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>{config.description}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  const config = AGENT_CONFIG[selectedRole];

  return (
    <div className="card flex flex-col h-[500px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2.5">
          <span className="text-lg">{config.icon}</span>
          <span className="font-semibold text-[15px]" style={{ color: "var(--text-primary)" }}>{config.label}</span>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>Direct Line</span>
        </div>
        <button
          onClick={() => {
            setSelectedRole(null);
            setMessages([]);
          }}
          className="text-sm px-3 py-1 rounded-lg transition-colors cursor-pointer"
          style={{ color: "var(--text-secondary)", background: "var(--bg-elevated)" }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; }}
        >
          Close
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <span className="text-3xl block mb-2">{config.icon}</span>
            <span className="text-sm" style={{ color: "var(--text-muted)" }}>
              Ask {config.label} anything about the project.
            </span>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} animate-fade-in`}
          >
            <div className="max-w-[80%]">
              <div
                className="px-4 py-2.5 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed"
                style={msg.role === "user"
                  ? { background: "linear-gradient(135deg, #635bff, #7a73ff)", color: "white", borderBottomRightRadius: 6 }
                  : { background: "var(--bg-elevated)", color: "var(--text-secondary)", border: "1px solid var(--border)", borderBottomLeftRadius: 6 }
                }
              >
                {msg.content}
                {loading && i === messages.length - 1 && msg.role === "assistant" && (
                  <span className="inline-block w-1.5 h-4 ml-0.5 animate-pulse" style={{ background: "var(--accent)", borderRadius: 1 }} />
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                {msg.timestamp && (
                  <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{msg.timestamp}</span>
                )}
                {msg.hasFileBlocks && msg.role === "assistant" && (
                  <button
                    onClick={() => handleApplyFiles(msg.content)}
                    disabled={applying}
                    className="text-xs px-2 py-0.5 rounded-md transition-colors cursor-pointer"
                    style={{
                      background: "var(--success-bg)",
                      color: "var(--success)",
                      border: "1px solid var(--success-border)",
                    }}
                  >
                    {applying ? "Applying..." : "Apply File Changes"}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="p-3" style={{ borderTop: "1px solid var(--border)" }}>
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder={`Message ${config.label}...`}
            className="flex-1 rounded-xl px-4 py-2.5 text-sm focus:outline-none transition-all"
            style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-bg)"; }}
            onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
          />
          <button
            onClick={handleSend}
            disabled={!message.trim() || loading}
            className="btn-primary px-5 py-2.5 text-sm"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
