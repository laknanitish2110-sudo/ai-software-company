"use client";

import { useState, useEffect } from "react";
import { AGENT_CONFIG } from "@/lib/constants";
import { getIntrospection, IntrospectionData } from "@/lib/api";

interface Props {
  projectId: string;
  role: string;
  onClose: () => void;
}

function Section({
  title,
  expanded,
  onToggle,
  accent,
  children,
}: {
  title: string;
  expanded: boolean;
  onToggle: () => void;
  accent?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <button
        onClick={onToggle}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 12px",
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          borderRadius: expanded ? "10px 10px 0 0" : 10,
          cursor: "pointer",
          color: accent || "var(--text-primary)",
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        <span>{title}</span>
        <span
          style={{
            fontSize: 11,
            transition: "transform 0.2s",
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            color: "var(--text-muted)",
          }}
        >
          ▼
        </span>
      </button>
      {expanded && (
        <div
          style={{
            border: "1px solid var(--border)",
            borderTop: "none",
            borderRadius: "0 0 10px 10px",
            padding: 12,
            background: "var(--bg-card)",
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export default function AgentIntrospection({ projectId, role, onClose }: Props) {
  const [data, setData] = useState<IntrospectionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["output"]));

  useEffect(() => {
    setLoading(true);
    getIntrospection(projectId, role)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [projectId, role]);

  const toggle = (s: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s);
      else next.add(s);
      return next;
    });

  const config = AGENT_CONFIG[role];
  const timing = data?.timing;
  const hasRun = timing && timing.elapsed_seconds !== undefined;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.2)",
          zIndex: 40,
        }}
      />

      {/* Drawer */}
      <div
        className="animate-slide-in-right"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          width: 460,
          maxWidth: "90vw",
          height: "100vh",
          background: "var(--bg-card)",
          borderLeft: "1px solid var(--border)",
          boxShadow: "-8px 0 32px rgba(0,0,0,0.12)",
          zIndex: 50,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 28 }}>{config?.icon}</span>
            <div>
              <div
                style={{
                  fontWeight: 700,
                  fontSize: 16,
                  color: "var(--text-primary)",
                }}
              >
                {data?.label || config?.label}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--text-muted)",
                  fontFamily: "monospace",
                  marginTop: 2,
                }}
              >
                Agent Introspection
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 14,
              color: "var(--text-muted)",
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {loading ? (
            <div
              style={{
                textAlign: "center",
                color: "var(--text-muted)",
                paddingTop: 60,
              }}
            >
              <div
                className="dot-loading"
                style={{
                  display: "flex",
                  justifyContent: "center",
                  gap: 6,
                  marginBottom: 12,
                }}
              >
                <span />
                <span />
                <span />
              </div>
              Loading agent data...
            </div>
          ) : (
            <>
              {/* Metric cards */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 10,
                  marginBottom: 20,
                }}
              >
                <div className="card" style={{ padding: "10px 12px", textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: 700,
                      color: "var(--accent)",
                      fontFamily: "monospace",
                    }}
                  >
                    {hasRun ? `${timing.elapsed_seconds}s` : "—"}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                    Duration
                  </div>
                </div>
                <div className="card" style={{ padding: "10px 12px", textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--success)",
                      fontFamily: "monospace",
                      wordBreak: "break-all",
                    }}
                  >
                    {data?.model?.split("/").pop() || "—"}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                    Model
                  </div>
                </div>
                <div className="card" style={{ padding: "10px 12px", textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: 700,
                      color: "var(--warning)",
                      fontFamily: "monospace",
                    }}
                  >
                    {data?.max_tokens?.toLocaleString() || "—"}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                    Max Tokens
                  </div>
                </div>
              </div>

              {/* Model info bar */}
              <div
                style={{
                  display: "flex",
                  gap: 16,
                  padding: "10px 14px",
                  background: "var(--bg-elevated)",
                  borderRadius: 10,
                  marginBottom: 16,
                  fontSize: 11,
                  color: "var(--text-secondary)",
                }}
              >
                <span>
                  Model:{" "}
                  <strong style={{ color: "var(--text-primary)" }}>
                    {data?.model || "—"}
                  </strong>
                </span>
                <span>
                  Timeout:{" "}
                  <strong style={{ color: "var(--text-primary)" }}>
                    {data?.timeout}s
                  </strong>
                </span>
                {timing?.context_length && (
                  <span>
                    Context:{" "}
                    <strong style={{ color: "var(--text-primary)" }}>
                      {timing.context_length.toLocaleString()} chars
                    </strong>
                  </span>
                )}
                {timing?.used_fallback && (
                  <span
                    style={{
                      background: "rgba(245,166,35,0.12)",
                      color: "var(--warning)",
                      padding: "2px 8px",
                      borderRadius: 6,
                      fontWeight: 600,
                      fontSize: 10,
                    }}
                  >
                    FALLBACK
                  </span>
                )}
              </div>

              {/* System Prompt */}
              <Section
                title="System Prompt"
                expanded={expanded.has("prompt")}
                onToggle={() => toggle("prompt")}
                accent="var(--accent)"
              >
                <pre
                  style={{
                    fontSize: 11,
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    color: "var(--text-secondary)",
                    fontFamily: "var(--font-geist-mono), monospace",
                    margin: 0,
                    maxHeight: 300,
                    overflowY: "auto",
                  }}
                >
                  {data?.system_prompt || "No prompt available"}
                </pre>
              </Section>

              {/* Output */}
              {data?.output && (
                <Section
                  title="Agent Output"
                  expanded={expanded.has("output")}
                  onToggle={() => toggle("output")}
                  accent="var(--success)"
                >
                  <div style={{ maxHeight: 400, overflowY: "auto" }}>
                    {typeof data.output.content === "object" ? (
                      Object.entries(
                        data.output.content as Record<string, unknown>
                      ).map(([key, value]) => (
                        <div key={key} style={{ marginBottom: 10 }}>
                          <div
                            style={{
                              fontSize: 11,
                              fontWeight: 600,
                              color: "var(--accent)",
                              textTransform: "uppercase",
                              letterSpacing: "0.05em",
                              marginBottom: 3,
                            }}
                          >
                            {key.replace(/_/g, " ")}
                          </div>
                          <div
                            style={{
                              fontSize: 12,
                              color: "var(--text-secondary)",
                              lineHeight: 1.5,
                            }}
                          >
                            {typeof value === "string"
                              ? value
                              : typeof value === "object" && value !== null
                                ? Array.isArray(value)
                                  ? (value as string[]).map((item, i) => (
                                      <div
                                        key={i}
                                        style={{
                                          paddingLeft: 12,
                                          borderLeft:
                                            "2px solid var(--border)",
                                          marginBottom: 4,
                                          fontSize: 11,
                                        }}
                                      >
                                        {typeof item === "string"
                                          ? item
                                          : JSON.stringify(item)}
                                      </div>
                                    ))
                                  : Object.entries(
                                      value as Record<string, unknown>
                                    ).map(([k, v]) => (
                                      <div
                                        key={k}
                                        style={{
                                          paddingLeft: 12,
                                          borderLeft:
                                            "2px solid var(--border)",
                                          marginBottom: 4,
                                          fontSize: 11,
                                        }}
                                      >
                                        <strong>{k}:</strong>{" "}
                                        {typeof v === "string"
                                          ? v
                                          : JSON.stringify(v)}
                                      </div>
                                    ))
                                : String(value)}
                          </div>
                        </div>
                      ))
                    ) : (
                      <pre
                        style={{
                          fontSize: 11,
                          whiteSpace: "pre-wrap",
                          color: "var(--text-secondary)",
                          fontFamily: "monospace",
                          margin: 0,
                        }}
                      >
                        {JSON.stringify(data.output.content, null, 2)}
                      </pre>
                    )}
                  </div>
                </Section>
              )}

              {/* Peer Review */}
              {data?.peer_review && (
                <Section
                  title={`Peer Review — ${(data.peer_review as Record<string, string>).reviewer_label || "Teammate"}`}
                  expanded={expanded.has("review")}
                  onToggle={() => toggle("review")}
                  accent="var(--info)"
                >
                  <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                    {(() => {
                      const r = data.peer_review as Record<string, unknown>;
                      return (
                        <>
                          {r.team_note && (
                            <div
                              style={{
                                padding: "8px 12px",
                                background: "var(--accent-bg)",
                                borderRadius: 8,
                                color: "var(--text-secondary)",
                                marginBottom: 10,
                                fontStyle: "italic",
                                fontSize: 12,
                              }}
                            >
                              &ldquo;{String(r.team_note)}&rdquo;
                            </div>
                          )}
                          {Array.isArray(r.strengths) &&
                            r.strengths.length > 0 && (
                              <div style={{ marginBottom: 8 }}>
                                <div
                                  style={{
                                    fontSize: 11,
                                    fontWeight: 600,
                                    color: "var(--success)",
                                    marginBottom: 4,
                                  }}
                                >
                                  Strengths
                                </div>
                                {(r.strengths as string[]).map(
                                  (s: string, i: number) => (
                                    <div
                                      key={i}
                                      style={{
                                        fontSize: 11,
                                        color: "var(--text-secondary)",
                                        paddingLeft: 10,
                                        borderLeft:
                                          "2px solid var(--success)",
                                        marginBottom: 3,
                                      }}
                                    >
                                      {s}
                                    </div>
                                  )
                                )}
                              </div>
                            )}
                          {Array.isArray(r.concerns) &&
                            r.concerns.length > 0 && (
                              <div style={{ marginBottom: 8 }}>
                                <div
                                  style={{
                                    fontSize: 11,
                                    fontWeight: 600,
                                    color: "var(--warning)",
                                    marginBottom: 4,
                                  }}
                                >
                                  Concerns
                                </div>
                                {(r.concerns as string[]).map(
                                  (s: string, i: number) => (
                                    <div
                                      key={i}
                                      style={{
                                        fontSize: 11,
                                        color: "var(--text-secondary)",
                                        paddingLeft: 10,
                                        borderLeft:
                                          "2px solid var(--warning)",
                                        marginBottom: 3,
                                      }}
                                    >
                                      {s}
                                    </div>
                                  )
                                )}
                              </div>
                            )}
                          {Array.isArray(r.suggestions) &&
                            r.suggestions.length > 0 && (
                              <div>
                                <div
                                  style={{
                                    fontSize: 11,
                                    fontWeight: 600,
                                    color: "var(--info)",
                                    marginBottom: 4,
                                  }}
                                >
                                  Suggestions
                                </div>
                                {(r.suggestions as string[]).map(
                                  (s: string, i: number) => (
                                    <div
                                      key={i}
                                      style={{
                                        fontSize: 11,
                                        color: "var(--text-secondary)",
                                        paddingLeft: 10,
                                        borderLeft:
                                          "2px solid var(--info)",
                                        marginBottom: 3,
                                      }}
                                    >
                                      {s}
                                    </div>
                                  )
                                )}
                              </div>
                            )}
                        </>
                      );
                    })()}
                  </div>
                </Section>
              )}

              {!data?.output && !hasRun && (
                <div
                  style={{
                    textAlign: "center",
                    padding: "30px 0",
                    color: "var(--text-muted)",
                    fontSize: 13,
                  }}
                >
                  This agent hasn&apos;t run yet.
                  <br />
                  <span style={{ fontSize: 11 }}>
                    The system prompt and configuration above show what this
                    agent will do when activated.
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
