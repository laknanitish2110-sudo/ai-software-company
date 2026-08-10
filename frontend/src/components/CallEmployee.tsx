"use client";

import { useState, useRef, useEffect } from "react";
import { AGENT_CONFIG } from "@/lib/constants";
import { callEmployee, getConversation } from "@/lib/api";

interface Props {
  projectId: string;
}

export default function CallEmployee({ projectId }: Props) {
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (selectedRole) {
      getConversation(projectId, selectedRole).then((data) => {
        setMessages(data.messages || []);
      });
    }
  }, [selectedRole, projectId]);

  async function handleSend() {
    if (!message.trim() || !selectedRole || loading) return;

    const userMsg = message;
    setMessage("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const response = await callEmployee(projectId, selectedRole, userMsg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.response },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: Could not reach this employee." },
      ]);
    } finally {
      setLoading(false);
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
            <div
              className="max-w-[80%] px-4 py-2.5 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed"
              style={msg.role === "user"
                ? { background: "linear-gradient(135deg, #635bff, #7a73ff)", color: "white", borderBottomRightRadius: 6 }
                : { background: "var(--bg-elevated)", color: "var(--text-secondary)", border: "1px solid var(--border)", borderBottomLeftRadius: 6 }
              }
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start animate-fade-in">
            <div className="px-4 py-3 rounded-2xl flex items-center gap-2"
                 style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderBottomLeftRadius: 6 }}>
              <span className="dot-loading"><span /><span /><span /></span>
              <span className="text-sm" style={{ color: "var(--text-muted)" }}>{config.label} is thinking</span>
            </div>
          </div>
        )}
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
