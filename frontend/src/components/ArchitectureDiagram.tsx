"use client";

import { useState, useMemo } from "react";

interface Props {
  architectOutput: Record<string, unknown>;
  onClose: () => void;
}

function generateMermaid(output: Record<string, unknown>): string {
  const lines: string[] = ["graph TB"];
  const techStack = output.tech_stack as Record<string, unknown> | undefined;
  const dbSchema = output.database_schema as Record<string, unknown> | undefined;
  const apiDesign = output.api_design as Record<string, unknown> | undefined;
  const systemOverview = output.system_overview as string | undefined;
  const components = output.components as Array<Record<string, unknown>> | undefined;
  const nlpPipeline = output.nlp_pipeline as Record<string, unknown> | undefined;

  lines.push("  subgraph Client[\"Frontend\"]");
  if (techStack?.frontend) {
    const fe = techStack.frontend;
    if (typeof fe === "string") {
      lines.push(`    FE["${sanitize(fe)}"]`);
    } else if (typeof fe === "object" && fe !== null) {
      const feObj = fe as Record<string, unknown>;
      const framework = feObj.framework || feObj.language || Object.values(feObj)[0];
      lines.push(`    FE["${sanitize(String(framework))}"]`);
    }
  } else {
    lines.push('    FE["Web App"]');
  }
  lines.push("  end");

  lines.push('  subgraph Server["Backend"]');
  if (techStack?.backend) {
    const be = techStack.backend;
    if (typeof be === "string") {
      lines.push(`    BE["${sanitize(be)}"]`);
    } else if (typeof be === "object" && be !== null) {
      const beObj = be as Record<string, unknown>;
      const framework = beObj.framework || beObj.language || Object.values(beObj)[0];
      lines.push(`    BE["${sanitize(String(framework))}"]`);
    }
  } else {
    lines.push('    BE["API Server"]');
  }

  if (apiDesign) {
    const endpoints = apiDesign.endpoints || apiDesign.routes || apiDesign.api_endpoints;
    if (Array.isArray(endpoints) && endpoints.length > 0) {
      const shown = endpoints.slice(0, 5);
      shown.forEach((ep, i) => {
        const label = typeof ep === "string" ? ep : (ep as Record<string, unknown>).path || (ep as Record<string, unknown>).endpoint || `API ${i + 1}`;
        lines.push(`    API${i}["${sanitize(String(label))}"]`);
      });
      lines.push("    BE --> " + shown.map((_, i) => `API${i}`).join(" & "));
    }
  }
  lines.push("  end");

  lines.push('  subgraph Data["Database"]');
  if (techStack?.database) {
    const db = techStack.database;
    if (typeof db === "string") {
      lines.push(`    DB[("${sanitize(db)}")]`);
    } else if (typeof db === "object" && db !== null) {
      const dbObj = db as Record<string, unknown>;
      const name = dbObj.primary || dbObj.type || dbObj.name || Object.values(dbObj)[0];
      lines.push(`    DB[("${sanitize(String(name))}")]`);
    }
  } else {
    lines.push('    DB[("Database")]');
  }

  if (dbSchema) {
    const tables = dbSchema.tables || dbSchema.collections || dbSchema.models;
    if (Array.isArray(tables) && tables.length > 0) {
      tables.slice(0, 6).forEach((t, i) => {
        const name = typeof t === "string" ? t : (t as Record<string, unknown>).name || (t as Record<string, unknown>).table || `Table ${i + 1}`;
        lines.push(`    T${i}["${sanitize(String(name))}"]`);
        lines.push(`    DB --- T${i}`);
      });
    }
  }
  lines.push("  end");

  if (nlpPipeline || (techStack && (techStack as Record<string, unknown>).ai)) {
    lines.push('  subgraph AI["AI/ML"]');
    if (nlpPipeline) {
      const pipelineSteps = Object.entries(nlpPipeline).slice(0, 4);
      pipelineSteps.forEach(([key, val], i) => {
        const label = typeof val === "string" ? val : key.replace(/_/g, " ");
        lines.push(`    NLP${i}["${sanitize(label)}"]`);
        if (i > 0) {
          lines.push(`    NLP${i - 1} --> NLP${i}`);
        }
      });
    } else {
      const ai = (techStack as Record<string, unknown>).ai;
      lines.push(`    AI_SVC["${sanitize(typeof ai === "string" ? ai : "AI Service")}"]`);
    }
    lines.push("  end");
    lines.push("  Server --> AI");
  }

  if (techStack?.deployment || techStack?.infrastructure) {
    lines.push('  subgraph Infra["Infrastructure"]');
    const deploy = techStack.deployment || techStack.infrastructure;
    if (typeof deploy === "string") {
      lines.push(`    DEPLOY["${sanitize(deploy)}"]`);
    } else if (typeof deploy === "object" && deploy !== null) {
      Object.entries(deploy as Record<string, unknown>).slice(0, 3).forEach(([key, val], i) => {
        lines.push(`    INF${i}["${sanitize(typeof val === "string" ? val : key)}"]`);
      });
    }
    lines.push("  end");
  }

  if (components && Array.isArray(components) && components.length > 0) {
    lines.push('  subgraph Services["Services"]');
    components.slice(0, 5).forEach((c, i) => {
      const name = c.name || c.service || `Service ${i + 1}`;
      lines.push(`    SVC${i}["${sanitize(String(name))}"]`);
    });
    lines.push("  end");
    lines.push("  Server --> Services");
  }

  lines.push("  Client -->|HTTP/WS| Server");
  lines.push("  Server -->|Query| Data");

  lines.push("");
  lines.push("  classDef frontend fill:#1e3a5f,stroke:#60a5fa,color:#bfdbfe");
  lines.push("  classDef backend fill:#1e3a2d,stroke:#34d399,color:#a7f3d0");
  lines.push("  classDef database fill:#3a1e3a,stroke:#c084fc,color:#e9d5ff");
  lines.push("  classDef ai fill:#3a2e1e,stroke:#fbbf24,color:#fef3c7");
  lines.push("  classDef infra fill:#1e2d3a,stroke:#67e8f9,color:#cffafe");
  lines.push("  class Client frontend");
  lines.push("  class Server backend");
  lines.push("  class Data database");
  lines.push("  class AI ai");
  lines.push("  class Infra infra");

  return lines.join("\n");
}

function sanitize(s: string): string {
  return s.replace(/"/g, "'").replace(/[[\]{}()#&]/g, "").slice(0, 60);
}

function extractKeyPoints(output: Record<string, unknown>): string[] {
  const points: string[] = [];
  const overview = output.system_overview;
  if (typeof overview === "string" && overview.length > 0) {
    points.push(overview.slice(0, 150));
  }
  const techStack = output.tech_stack as Record<string, unknown> | undefined;
  if (techStack) {
    Object.entries(techStack).slice(0, 5).forEach(([key, val]) => {
      const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      if (typeof val === "string") {
        points.push(`${label}: ${val}`);
      } else if (typeof val === "object" && val !== null) {
        const summary = Object.entries(val as Record<string, unknown>)
          .slice(0, 3)
          .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
          .join(", ");
        points.push(`${label}: ${summary.slice(0, 100)}`);
      }
    });
  }
  return points;
}

export default function ArchitectureDiagram({ architectOutput, onClose }: Props) {
  const [activeView, setActiveView] = useState<"diagram" | "details">("diagram");

  const mermaidCode = useMemo(() => generateMermaid(architectOutput), [architectOutput]);
  const keyPoints = useMemo(() => extractKeyPoints(architectOutput), [architectOutput]);

  return (
    <div
      className="fixed inset-0 animate-fade-in"
      style={{ background: "rgba(0,0,0,0.7)", zIndex: 100 }}
      onClick={onClose}
    >
      <div
        className="absolute inset-3 lg:inset-6 flex flex-col overflow-hidden"
        style={{
          background: "#0d1117",
          borderRadius: 16,
          border: "1px solid #30363d",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{
            borderBottom: "1px solid #30363d",
            background: "#161b22",
          }}
        >
          <div className="flex items-center gap-3">
            <span style={{ fontSize: 18 }}>🏗️</span>
            <span style={{ color: "#e6edf3", fontSize: 15, fontWeight: 600 }}>
              Architecture Diagram
            </span>
            <div className="flex gap-1">
              {(["diagram", "details"] as const).map((view) => (
                <button
                  key={view}
                  onClick={() => setActiveView(view)}
                  style={{
                    padding: "3px 12px",
                    borderRadius: 6,
                    fontSize: 11,
                    fontWeight: 500,
                    cursor: "pointer",
                    border: "1px solid",
                    borderColor: activeView === view ? "rgba(99,91,255,0.4)" : "#30363d",
                    background: activeView === view ? "rgba(99,91,255,0.15)" : "transparent",
                    color: activeView === view ? "#a5a0ff" : "#8b949e",
                  }}
                >
                  {view === "diagram" ? "Diagram" : "Tech Details"}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid #30363d",
              color: "#8b949e",
              padding: "6px 14px",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            Close ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-6">
          {activeView === "diagram" ? (
            <div className="flex flex-col items-center gap-6">
              <pre className="mermaid" style={{ width: "100%", maxWidth: 900, margin: "0 auto" }}>
                {mermaidCode}
              </pre>
              {keyPoints.length > 0 && (
                <div
                  style={{
                    maxWidth: 700,
                    width: "100%",
                    background: "rgba(255,255,255,0.03)",
                    borderRadius: 12,
                    border: "1px solid #21262d",
                    padding: "16px 20px",
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#8b949e",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      marginBottom: 10,
                    }}
                  >
                    Architecture Summary
                  </div>
                  {keyPoints.map((point, i) => (
                    <div
                      key={i}
                      style={{
                        fontSize: 13,
                        color: "#c9d1d9",
                        padding: "4px 0",
                        borderBottom: i < keyPoints.length - 1 ? "1px solid #21262d" : "none",
                      }}
                    >
                      {point}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div
              style={{
                maxWidth: 800,
                margin: "0 auto",
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 16,
              }}
            >
              {Object.entries(architectOutput).map(([key, val]) => {
                if (!val || key === "project_structure") return null;
                const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                return (
                  <div
                    key={key}
                    style={{
                      background: "rgba(255,255,255,0.03)",
                      borderRadius: 12,
                      border: "1px solid #21262d",
                      padding: "14px 18px",
                      gridColumn: typeof val === "string" && val.length > 200 ? "1 / -1" : undefined,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: "#8b5cf6",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        marginBottom: 8,
                      }}
                    >
                      {label}
                    </div>
                    <pre
                      style={{
                        fontSize: 12,
                        color: "#c9d1d9",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        fontFamily: "'Consolas', monospace",
                        margin: 0,
                        maxHeight: 300,
                        overflow: "auto",
                      }}
                    >
                      {typeof val === "string" ? val : JSON.stringify(val, null, 2)}
                    </pre>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
