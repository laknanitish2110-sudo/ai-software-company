"use client";

import { AGENT_CONFIG, PIPELINE_ORDER, MODEL_LABELS } from "@/lib/constants";

interface Props {
  status: string;
  outputs: Array<{ role: string; status: string }>;
  streamingAgent: string | null;
  streamTokens: number;
  elapsed: number;
  onNodeClick?: (role: string) => void;
  visibleAgents?: string[];
  selectedAgent?: string | null;
}

const R = 36;

const CONN_LABELS: Record<string, string> = {
  ceo: "Product Brief",
  business_analyst: "Requirements",
  researcher: "Insights",
  architect: "System Design",
  engineer: "Working Code",
};

type StepState = "done" | "active" | "review" | "waiting";

function getStepState(
  role: string,
  status: string,
  outputs: Array<{ role: string; status: string }>
): StepState {
  if (status === "completed") return "done";
  const output = outputs.filter((o) => o.role === role).pop();
  if (output?.status === "approved") return "done";
  const reviewMap: Record<string, string> = {
    business_analyst: "ba_review",
    researcher: "research_review",
    architect: "architect_review",
    engineer: "engineer_review",
  };
  if (reviewMap[role] === status) return "review";
  const workingMap: Record<string, string> = {
    business_analyst: "ba_working",
    researcher: "research_working",
    architect: "architect_working",
    engineer: "engineer_working",
    ppt: "ppt_working",
  };
  if (workingMap[role] === status) return "active";
  if (role === "ceo") {
    if (outputs.find((o) => o.role === "ceo")) return "done";
    if (status === "created") return "active";
  }
  if (role === "ppt" && status === "completed") return "done";
  return "waiting";
}

type ConnState = "idle" | "flowing" | "passed" | "blocked";

function getConnState(
  from: string,
  to: string,
  status: string,
  outputs: Array<{ role: string; status: string }>
): ConnState {
  const src = getStepState(from, status, outputs);
  if (src === "waiting" || src === "active") return "idle";
  if (src === "review") return "blocked";
  const dst = getStepState(to, status, outputs);
  if (dst === "active") return "flowing";
  return "passed";
}

function withAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export default function AgentCanvas({
  status,
  outputs,
  streamingAgent,
  streamTokens,
  elapsed,
  onNodeClick,
  visibleAgents,
  selectedAgent,
}: Props) {
  const agents = visibleAgents || PIPELINE_ORDER;
  const completedCount = agents.filter(
    (r) => getStepState(r, status, outputs) === "done"
  ).length;
  const totalAgents = agents.length;

  const NODE_SPACING = Math.min(180, 900 / agents.length);
  const SVG_W = Math.max(700, agents.length * NODE_SPACING + 120);
  const SVG_H = 320;
  const CENTER_Y = 145;
  const START_X = 80;

  return (
    <div style={{ position: "relative", overflow: "hidden" }}>
      <style>{`
        @keyframes canvasPulse {
          0%, 100% { opacity: 0.6; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.3); }
        }
        @keyframes ambientFloat {
          0%, 100% { transform: translateY(0px); opacity: 0.3; }
          50% { transform: translateY(-8px); opacity: 0.7; }
        }
        @keyframes energyFlow {
          0% { stroke-dashoffset: 0; }
          100% { stroke-dashoffset: -60; }
        }
        @keyframes selectedPulse {
          0%, 100% { stroke-opacity: 0.6; }
          50% { stroke-opacity: 1; }
        }
        @keyframes gridPulse {
          0%, 100% { opacity: 0.02; }
          50% { opacity: 0.05; }
        }
        .hq-agent-node { transition: transform 0.2s ease; cursor: pointer; }
        .hq-agent-node:hover { transform: scale(1.08); }
        .hq-agent-node:hover .node-hover-ring { opacity: 0.5 !important; }
      `}</style>

      {/* Header bar */}
      <div style={{
        padding: "16px 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 12, height: 12, borderRadius: "50%",
            background: streamingAgent ? "#635bff" : completedCount === totalAgents ? "#0bbf8c" : "#2a2f4a",
            boxShadow: streamingAgent ? "0 0 16px #635bff" : completedCount === totalAgents ? "0 0 16px #0bbf8c" : "none",
            animation: streamingAgent ? "canvasPulse 2s infinite" : undefined,
          }} />
          <span style={{
            color: "rgba(255,255,255,0.95)", fontSize: 18, fontWeight: 800,
            letterSpacing: "0.08em", textTransform: "uppercase" as const,
          }}>
            Company HQ
          </span>
          {completedCount === totalAgents && (
            <span style={{
              fontSize: 11, fontWeight: 700, padding: "4px 14px", borderRadius: 14,
              background: "rgba(11,191,140,0.15)", color: "#0bbf8c", border: "1px solid rgba(11,191,140,0.3)",
              letterSpacing: "0.05em",
            }}>
              PRODUCT READY
            </span>
          )}
          {streamingAgent && (
            <span style={{
              fontSize: 11, fontWeight: 600, padding: "4px 12px", borderRadius: 14,
              background: "rgba(99,91,255,0.15)", color: "#a5a0ff", border: "1px solid rgba(99,91,255,0.3)",
            }}>
              {AGENT_CONFIG[streamingAgent]?.label || streamingAgent} working...
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {streamingAgent && streamTokens > 0 && (
            <span style={{ color: "rgba(255,255,255,0.4)", fontSize: 12, fontFamily: "monospace" }}>
              {streamTokens} tokens
            </span>
          )}
          <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 14, fontWeight: 700, fontFamily: "monospace" }}>
            {completedCount}/{totalAgents}
          </span>
          <div style={{
            width: 120, height: 8, borderRadius: 4,
            background: "rgba(255,255,255,0.06)", overflow: "hidden",
          }}>
            <div style={{
              width: `${(completedCount / totalAgents) * 100}%`, height: "100%", borderRadius: 4,
              background: completedCount === totalAgents ? "#0bbf8c" : "linear-gradient(90deg, #635bff, #7a73ff)",
              transition: "width 0.5s ease",
              boxShadow: completedCount === totalAgents ? "0 0 12px rgba(11,191,140,0.4)" : "0 0 12px rgba(99,91,255,0.3)",
            }} />
          </div>
        </div>
      </div>

      {/* SVG Canvas */}
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        style={{ width: "100%", display: "block" }}
        preserveAspectRatio="xMidYMid meet"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <filter id="activeGlow">
            <feGaussianBlur stdDeviation="10" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="particleGlow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="nodeGlow">
            <feGaussianBlur stdDeviation="16" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="bigGlow">
            <feGaussianBlur stdDeviation="24" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <pattern id="bgGrid" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
            <line x1="40" y1="0" x2="40" y2="40" stroke="rgba(99,91,255,0.04)" strokeWidth="0.5" />
            <line x1="0" y1="40" x2="40" y2="40" stroke="rgba(99,91,255,0.04)" strokeWidth="0.5" />
          </pattern>
          <radialGradient id="centerSpot" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#635bff" stopOpacity="0.06" />
            <stop offset="100%" stopColor="#635bff" stopOpacity="0" />
          </radialGradient>
        </defs>

        <rect width={SVG_W} height={SVG_H} fill="url(#bgGrid)" style={{ animation: "gridPulse 8s ease-in-out infinite" }} />
        <ellipse cx={SVG_W / 2} cy={CENTER_Y} rx={SVG_W * 0.4} ry={SVG_H * 0.35} fill="url(#centerSpot)" />

        {/* Ambient particles */}
        {Array.from({ length: 12 }).map((_, i) => {
          const angle = (i / 12) * Math.PI * 2;
          const rx = SVG_W * 0.35 + Math.sin(i * 3) * 40;
          const ry = 80 + Math.cos(i * 2) * 30;
          return (
            <circle key={`amb-${i}`}
              cx={SVG_W / 2 + Math.cos(angle) * rx}
              cy={CENTER_Y + Math.sin(angle) * ry}
              r={1 + (i % 3) * 0.5}
              fill="rgba(99,91,255,0.25)"
              style={{ animation: `ambientFloat ${3 + i * 0.3}s ease-in-out ${i * 0.4}s infinite` }}
            />
          );
        })}

        {/* Horizontal connections */}
        {agents.slice(0, -1).map((role, i) => {
          const nextRole = agents[i + 1];
          const x1 = START_X + i * NODE_SPACING + R + 2;
          const x2 = START_X + (i + 1) * NODE_SPACING - R - 2;
          const connState = getConnState(role, nextRole, status, outputs);
          const color =
            connState === "passed" ? "#0bbf8c"
            : connState === "flowing" ? "#635bff"
            : connState === "blocked" ? "#f5a623"
            : "#1e2340";
          const pathId = `hp-${i}`;
          const pathD = `M ${x1},${CENTER_Y} L ${x2},${CENTER_Y}`;
          const gateX = (x1 + x2) / 2;

          return (
            <g key={`c-${i}`}>
              {/* Wide glow behind active connections */}
              {(connState === "flowing" || connState === "passed") && (
                <line x1={x1} y1={CENTER_Y} x2={x2} y2={CENTER_Y}
                  stroke={color} strokeWidth="12" opacity="0.06" />
              )}

              <path id={pathId} d={pathD} fill="none" stroke={color}
                strokeWidth={connState === "idle" ? 1.5 : 3}
                strokeDasharray={connState === "idle" || connState === "blocked" ? "6 6" : undefined}
                opacity={connState === "idle" ? 0.25 : 0.7} />

              {connState === "flowing" && (
                <path d={pathD} fill="none" stroke="#635bff" strokeWidth="3" strokeDasharray="10 16" opacity="0.7"
                  style={{ animation: "energyFlow 0.7s linear infinite" }} />
              )}

              {(connState === "flowing" || connState === "passed") &&
                [0, 0.4, 0.8].map((delay, j) => (
                  <circle key={j} r={j === 0 ? 4 : 2.5} fill={color} filter="url(#particleGlow)"
                    opacity={j === 0 ? 1 : 0.5}>
                    <animateMotion dur="1.2s" repeatCount="indefinite" begin={`${delay}s`} calcMode="linear">
                      <mpath href={`#${pathId}`} />
                    </animateMotion>
                  </circle>
                ))}

              {/* Connection label */}
              {(connState === "flowing" || connState === "passed") && CONN_LABELS[role] && (
                <text x={gateX} y={CENTER_Y - 26} textAnchor="middle" fill="rgba(255,255,255,0.35)" fontSize="9" fontFamily="monospace" fontWeight="500">
                  {CONN_LABELS[role]}
                </text>
              )}

              {/* Gate diamond */}
              <g>
                <rect x={gateX - 6} y={CENTER_Y - 6} width="12" height="12" rx="2"
                  transform={`rotate(45 ${gateX} ${CENTER_Y})`}
                  fill={connState === "blocked" ? "rgba(245,166,35,0.2)" : connState === "passed" || connState === "flowing" ? "rgba(11,191,140,0.15)" : "rgba(255,255,255,0.02)"}
                  stroke={connState === "blocked" ? "#f5a623" : connState === "passed" || connState === "flowing" ? "#0bbf8c" : "#2a2f4a"}
                  strokeWidth="1.5" opacity={connState === "idle" ? 0.4 : 1}>
                  {connState === "blocked" && (
                    <animate attributeName="opacity" values="0.5;1;0.5" dur="1.5s" repeatCount="indefinite" />
                  )}
                </rect>
                {connState === "blocked" && (
                  <text x={gateX} y={CENTER_Y + 4} textAnchor="middle" fill="#f5a623" fontSize="8" fontWeight="bold">!</text>
                )}
                {(connState === "passed" || connState === "flowing") && (
                  <text x={gateX} y={CENTER_Y + 4} textAnchor="middle" fill="#0bbf8c" fontSize="8" fontWeight="bold">✓</text>
                )}
              </g>
            </g>
          );
        })}

        {/* Agent Nodes */}
        {agents.map((role, i) => {
          const x = START_X + i * NODE_SPACING;
          const y = CENTER_Y;
          const config = AGENT_CONFIG[role];
          const state = getStepState(role, status, outputs);
          const isStreaming = streamingAgent === role;
          const isSelected = selectedAgent === role;

          const sc =
            state === "done" ? { fill: "rgba(11,191,140,0.12)", stroke: "#0bbf8c", text: "#0bbf8c" }
            : state === "active" ? { fill: withAlpha(config.color, 0.15), stroke: config.color, text: config.color }
            : state === "review" ? { fill: "rgba(245,166,35,0.12)", stroke: "#f5a623", text: "#f5a623" }
            : { fill: "rgba(255,255,255,0.03)", stroke: "#2a2f4a", text: "rgba(255,255,255,0.25)" };

          return (
            <g key={role} className="hq-agent-node"
              onClick={() => onNodeClick?.(role)}>

              {/* Large background glow */}
              {(state === "done" || state === "active") && (
                <circle cx={x} cy={y} r={R + 30} fill={state === "done" ? "#0bbf8c" : config.color}
                  opacity={state === "active" ? 0.06 : 0.04} filter="url(#bigGlow)">
                  {state === "active" && (
                    <animate attributeName="opacity" values="0.03;0.08;0.03" dur="3s" repeatCount="indefinite" />
                  )}
                </circle>
              )}

              {/* Active ripples */}
              {state === "active" && (
                <>
                  <circle cx={x} cy={y} fill="none" stroke={config.color} strokeWidth="1.5" opacity="0">
                    <animate attributeName="r" values={`${R + 5};${R + 35}`} dur="2.5s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.4;0" dur="2.5s" repeatCount="indefinite" />
                  </circle>
                  <circle cx={x} cy={y} fill="none" stroke={config.color} strokeWidth="1.5" opacity="0">
                    <animate attributeName="r" values={`${R + 5};${R + 35}`} dur="2.5s" begin="1.25s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.4;0" dur="2.5s" begin="1.25s" repeatCount="indefinite" />
                  </circle>
                </>
              )}

              {/* Selected ring */}
              {isSelected && (
                <circle cx={x} cy={y} r={R + 8} fill="none" stroke="#635bff" strokeWidth="2.5"
                  strokeDasharray="8 4" style={{ animation: "selectedPulse 1.5s infinite" }} />
              )}

              {/* Hover ring */}
              <circle className="node-hover-ring" cx={x} cy={y} r={R + 4}
                fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" strokeDasharray="5 4" opacity={0} />

              {/* Spinning orbit (active) */}
              {state === "active" && (
                <circle cx={x} cy={y} r={R + 6} fill="none" stroke={config.color}
                  strokeWidth="2" strokeDasharray="6 8" opacity="0.5">
                  <animateTransform attributeName="transform" type="rotate"
                    from={`0 ${x} ${y}`} to={`360 ${x} ${y}`} dur="4s" repeatCount="indefinite" />
                </circle>
              )}

              {/* Main circle — larger */}
              <circle cx={x} cy={y} r={R} fill={sc.fill} stroke={sc.stroke}
                strokeWidth={state === "waiting" ? 1.5 : 3} />

              {/* Agent icon */}
              <foreignObject x={x - 16} y={y - 16} width="32" height="32">
                <div style={{ fontSize: 24, lineHeight: "32px", textAlign: "center", width: 32, height: 32 }}>
                  {config.icon}
                </div>
              </foreignObject>

              {/* Done badge */}
              {state === "done" && (
                <g>
                  <circle cx={x + R - 5} cy={y - R + 5} r="10" fill="#0bbf8c" stroke="#080b1a" strokeWidth="2.5" />
                  <text x={x + R - 5} y={y - R + 9} textAnchor="middle" fill="white" fontSize="9" fontWeight="bold">✓</text>
                </g>
              )}

              {/* Review badge */}
              {state === "review" && (
                <g>
                  <circle cx={x + R - 5} cy={y - R + 5} r="10" fill="#f5a623" stroke="#080b1a" strokeWidth="2.5">
                    <animate attributeName="fill-opacity" values="0.7;1;0.7" dur="1.5s" repeatCount="indefinite" />
                  </circle>
                  <text x={x + R - 5} y={y - R + 9} textAnchor="middle" fill="white" fontSize="9" fontWeight="bold">!</text>
                </g>
              )}

              {/* Label below node */}
              <text x={x} y={y + R + 20} textAnchor="middle"
                fill={state === "waiting" ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.95)"}
                fontSize="13" fontWeight="700">
                {config.label}
              </text>
              <text x={x} y={y + R + 34} textAnchor="middle" fill={sc.text} fontSize="10" fontFamily="monospace"
                opacity={state === "waiting" ? 0.3 : 0.85}>
                {state === "done" ? "Complete" : state === "active" ? "Working..." : state === "review" ? "Review" : "Standby"}
              </text>

              {/* Model label */}
              {MODEL_LABELS[role] && state !== "waiting" && (
                <text x={x} y={y + R + 48} textAnchor="middle" fill={MODEL_LABELS[role].providerColor}
                  fontSize="8" fontFamily="monospace" opacity={0.4}>
                  {MODEL_LABELS[role].model}
                </text>
              )}

              {/* Streaming badge */}
              {isStreaming && (
                <g>
                  <rect x={x - 48} y={y - R - 26} width="96" height="20" rx="10"
                    fill="rgba(99,91,255,0.2)" stroke="rgba(99,91,255,0.4)" strokeWidth="1" />
                  <text x={x} y={y - R - 12} textAnchor="middle" fill="#a5a0ff" fontSize="10" fontFamily="monospace" fontWeight="600">
                    {streamTokens > 0 ? `${streamTokens} tok` : "thinking..."}
                    {" · "}
                    {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Brand mark */}
        <text x={SVG_W / 2} y={SVG_H - 10} textAnchor="middle" fill="rgba(99,91,255,0.2)" fontSize="9" fontWeight="700" letterSpacing="0.35em">
          BUILT BY FORGEAI
        </text>
      </svg>
    </div>
  );
}
