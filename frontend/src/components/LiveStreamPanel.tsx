"use client";

import { useEffect, useRef } from "react";
import { AGENT_CONFIG } from "@/lib/constants";

interface Props {
  agentRole: string;
  streamText: string;
  tokenCount: number;
  elapsed: number;
}

export default function LiveStreamPanel({ agentRole, streamText, tokenCount, elapsed }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const config = AGENT_CONFIG[agentRole];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [streamText]);

  const minutes = Math.floor(elapsed / 60);
  const seconds = String(elapsed % 60).padStart(2, "0");

  return (
    <div
      className="card overflow-hidden animate-fade-in"
      style={{
        background: "linear-gradient(145deg, #080b1a, #0f1330)",
        border: "1px solid #1a1f3a",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "10px 16px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: config?.color || "#635bff",
              boxShadow: `0 0 8px ${config?.color || "#635bff"}`,
            }}
          >
            <style>{`
              @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.3; }
              }
            `}</style>
            <div style={{ animation: "blink 1.2s infinite" }} />
          </div>
          <span style={{ color: "#e6edf3", fontSize: 13, fontWeight: 600 }}>
            {config?.icon} {config?.label || agentRole} — Live Output
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span
            className="status-badge"
            style={{
              background: "rgba(99,91,255,0.12)",
              color: "#a5a0ff",
              border: "1px solid rgba(99,91,255,0.25)",
              fontSize: 10,
              fontFamily: "monospace",
            }}
          >
            {tokenCount} tokens
          </span>
          <span
            style={{
              color: "rgba(255,255,255,0.35)",
              fontSize: 11,
              fontFamily: "monospace",
            }}
          >
            {minutes}:{seconds}
          </span>
        </div>
      </div>

      {/* Streaming text */}
      <div
        ref={scrollRef}
        style={{
          padding: "12px 16px",
          maxHeight: 220,
          minHeight: 80,
          overflow: "auto",
          fontFamily: "'Consolas', 'Monaco', monospace",
          fontSize: 12,
          lineHeight: "1.6",
          color: "#c9d1d9",
          scrollbarWidth: "thin",
          scrollbarColor: "#30363d transparent",
        }}
      >
        {streamText ? (
          <span>
            {streamText.length > 4000 ? "..." + streamText.slice(-3500) : streamText}
            <span
              style={{
                display: "inline-block",
                width: 2,
                height: 14,
                background: config?.color || "#635bff",
                marginLeft: 2,
                verticalAlign: "text-bottom",
                animation: "blink 0.8s infinite",
              }}
            />
          </span>
        ) : (
          <span style={{ color: "rgba(255,255,255,0.25)", fontStyle: "italic" }}>
            Waiting for output...
          </span>
        )}
      </div>
    </div>
  );
}
