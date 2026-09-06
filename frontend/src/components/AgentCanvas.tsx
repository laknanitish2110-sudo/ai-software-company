"use client";

import { AGENT_CONFIG, PIPELINE_ORDER, MODEL_LABELS } from "@/lib/constants";

interface Props {
  status: string;
  outputs: Array<{ role: string; status: string }>;
  streamingAgent: string | null;
  streamTokens: number;
  elapsed: number;
  onNodeClick?: (role: string) => void;
}

const R = 30;
const NODE_SPACING = 88;
const CENTER_X = 75;
const START_Y = 55;
const BRAND_X = 18;

const DATA_LABELS = ["Brief", "Requirements", "Research", "Architecture", "Code"];

type StepState = "done" | "active" | "review" | "waiting";

function getStepState(
  role: string,
  status: string,
  outputs: Array<{ role: string; status: string }>
): StepState {
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
}: Props) {
  const completedCount = PIPELINE_ORDER.filter(
    (r) => getStepState(r, status, outputs) === "done"
  ).length;

  const totalHeight = START_Y + (PIPELINE_ORDER.length - 1) * NODE_SPACING + 65;

  return (
    <div
      className="card overflow-hidden"
      style={{
        background: "linear-gradient(145deg, #080b1a, #0f1330)",
        border: "1px solid #1a1f3a",
        position: "relative",
      }}
    >
      <style>{`
        @keyframes canvasPulse {
          0%, 100% { opacity: 0.6; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.3); }
        }
        @keyframes ambientFloat {
          0%, 100% { transform: translateY(0px); opacity: 0.3; }
          50% { transform: translateY(-8px); opacity: 0.7; }
        }
        @keyframes rippleExpand {
          0% { r: ${R + 4}; opacity: 0.4; }
          100% { r: ${R + 30}; opacity: 0; }
        }
        @keyframes glowPulse {
          0%, 100% { opacity: 0.15; }
          50% { opacity: 0.35; }
        }
        @keyframes energyFlow {
          0% { stroke-dashoffset: 0; }
          100% { stroke-dashoffset: -60; }
        }
        .agent-node { transition: transform 0.15s ease; }
        .agent-node:hover { transform: scale(1.04); }
        .agent-node:hover .node-hover-ring { opacity: 0.4 !important; }
      `}</style>

      {/* Header */}
      <div style={{
        padding: "12px 16px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: streamingAgent ? "#635bff" : completedCount === 6 ? "#0bbf8c" : "#2a2f4a",
            boxShadow: streamingAgent ? "0 0 10px #635bff" : completedCount === 6 ? "0 0 10px #0bbf8c" : "none",
            animation: streamingAgent ? "canvasPulse 2s infinite" : undefined,
          }} />
          <span style={{
            color: "rgba(255,255,255,0.9)", fontSize: 13, fontWeight: 700,
            letterSpacing: "0.04em", textTransform: "uppercase" as const,
          }}>
            Company HQ
          </span>
          {completedCount === 6 && (
            <span style={{
              fontSize: 9, fontWeight: 600, padding: "2px 8px", borderRadius: 10,
              background: "rgba(11,191,140,0.15)", color: "#0bbf8c", border: "1px solid rgba(11,191,140,0.3)",
            }}>
              ALL SHIPPED
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 12, fontWeight: 600 }}>
            {completedCount}/6
          </span>
          <div style={{
            width: 60, height: 5, borderRadius: 3,
            background: "rgba(255,255,255,0.06)", overflow: "hidden",
          }}>
            <div style={{
              width: `${(completedCount / 6) * 100}%`, height: "100%", borderRadius: 3,
              background: completedCount === 6 ? "#0bbf8c" : "linear-gradient(90deg, #635bff, #7a73ff)",
              transition: "width 0.5s ease",
            }} />
          </div>
        </div>
      </div>

      {/* SVG Canvas — Vertical */}
      <svg
        viewBox={`0 0 310 ${totalHeight}`}
        style={{ width: "100%", display: "block" }}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <filter id="activeGlow">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="particleGlow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="nodeGlow">
            <feGaussianBlur stdDeviation="12" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <pattern id="bgDots" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="12" cy="12" r="0.4" fill="rgba(255,255,255,0.03)" />
          </pattern>
          <linearGradient id="brandGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#635bff" stopOpacity="0.12" />
            <stop offset="50%" stopColor="#635bff" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#635bff" stopOpacity="0.08" />
          </linearGradient>
          <filter id="brandGlow">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <linearGradient id="connGlow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#635bff" stopOpacity="0" />
            <stop offset="50%" stopColor="#635bff" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#635bff" stopOpacity="0" />
          </linearGradient>
        </defs>

        <rect width="310" height={totalHeight} fill="url(#bgDots)" />

        {/* Branding strip — left edge */}
        <rect x="0" y="0" width={BRAND_X + 12} height={totalHeight} fill="url(#brandGrad)" />
        <line x1={BRAND_X + 12} y1="0" x2={BRAND_X + 12} y2={totalHeight}
          stroke="rgba(99,91,255,0.4)" strokeWidth="2" />
        {/* Glowing accent dots along the brand line */}
        {PIPELINE_ORDER.map((_, i) => (
          <circle key={`bd-${i}`} cx={BRAND_X + 12} cy={START_Y + i * NODE_SPACING} r="3"
            fill="#635bff" opacity="0.7" filter="url(#brandGlow)" />
        ))}

        {/* Vertical brand text — large and visible */}
        <text
          x={BRAND_X - 1}
          y={totalHeight / 2}
          textAnchor="middle"
          fill="rgba(99,91,255,0.7)"
          fontSize="14"
          fontWeight="900"
          letterSpacing="0.5em"
          filter="url(#brandGlow)"
          transform={`rotate(-90 ${BRAND_X - 1} ${totalHeight / 2})`}
        >
          AI SOFTWARE CO.
        </text>

        {/* Bottom horizontal brand mark */}
        <text
          x={CENTER_X + 50}
          y={totalHeight - 8}
          textAnchor="middle"
          fill="rgba(99,91,255,0.4)"
          fontSize="8"
          fontWeight="700"
          letterSpacing="0.3em"
        >
          BUILT BY AI SOFTWARE CO.
        </text>

        {/* Ambient floating particles */}
        {[
          { cx: 250, cy: 80, delay: 0 },
          { cx: 280, cy: 200, delay: 1.2 },
          { cx: 40, cy: 320, delay: 0.5 },
          { cx: 260, cy: 420, delay: 2 },
          { cx: 45, cy: 150, delay: 1.5 },
          { cx: 290, cy: 350, delay: 0.8 },
        ].map((p, i) => (
          <circle key={`amb-${i}`} cx={p.cx} cy={p.cy} r="1.5"
            fill="rgba(99,91,255,0.3)"
            style={{ animation: `ambientFloat ${3 + i * 0.4}s ease-in-out ${p.delay}s infinite` }} />
        ))}

        {/* Connections */}
        {PIPELINE_ORDER.slice(0, -1).map((role, i) => {
          const nextRole = PIPELINE_ORDER[i + 1];
          const y1 = START_Y + i * NODE_SPACING + R;
          const y2 = START_Y + (i + 1) * NODE_SPACING - R;
          const connState = getConnState(role, nextRole, status, outputs);
          const color =
            connState === "passed" ? "#0bbf8c"
            : connState === "flowing" ? "#635bff"
            : connState === "blocked" ? "#f5a623"
            : "#1e2340";
          const pathId = `vp-${i}`;
          const pathD = `M ${CENTER_X},${y1} L ${CENTER_X},${y2}`;
          const gateY = (y1 + y2) / 2;

          return (
            <g key={`c-${i}`}>
              {/* Glow behind active connections */}
              {(connState === "flowing" || connState === "passed") && (
                <line x1={CENTER_X} y1={y1} x2={CENTER_X} y2={y2}
                  stroke={color} strokeWidth="8" opacity="0.08" />
              )}

              <path id={pathId} d={pathD} fill="none" stroke={color}
                strokeWidth={connState === "idle" ? 1.5 : 2.5}
                strokeDasharray={connState === "idle" || connState === "blocked" ? "4 4" : undefined}
                opacity={connState === "idle" ? 0.3 : 0.7} />

              {/* Flowing energy line */}
              {connState === "flowing" && (
                <path d={pathD} fill="none" stroke="#635bff" strokeWidth="3" strokeDasharray="8 14" opacity="0.6"
                  style={{ animation: "energyFlow 0.8s linear infinite" }} />
              )}

              {/* Particles */}
              {(connState === "flowing" || connState === "passed") &&
                [0, 0.4, 0.8].map((delay, j) => (
                  <circle key={j} r={j === 0 ? 3.5 : 2} fill={color} filter="url(#particleGlow)"
                    opacity={j === 0 ? 1 : 0.5}>
                    <animateMotion dur="1.2s" repeatCount="indefinite" begin={`${delay}s`} calcMode="linear">
                      <mpath href={`#${pathId}`} />
                    </animateMotion>
                  </circle>
                ))}

              {/* Data label */}
              {(connState === "flowing" || connState === "passed") && (
                <text x={CENTER_X + 18} y={gateY + 4} fill="rgba(255,255,255,0.3)" fontSize="9" fontFamily="monospace" fontWeight="500">
                  {DATA_LABELS[i]}
                </text>
              )}

              {/* Approval gate */}
              {i > 0 && (
                <g>
                  <rect x={CENTER_X - 6} y={gateY - 6} width="12" height="12" rx="2"
                    transform={`rotate(45 ${CENTER_X} ${gateY})`}
                    fill={connState === "blocked" ? "rgba(245,166,35,0.2)" : connState === "passed" || connState === "flowing" ? "rgba(11,191,140,0.15)" : "rgba(255,255,255,0.02)"}
                    stroke={connState === "blocked" ? "#f5a623" : connState === "passed" || connState === "flowing" ? "#0bbf8c" : "#2a2f4a"}
                    strokeWidth="1.5" opacity={connState === "idle" ? 0.4 : 1}>
                    {connState === "blocked" && (
                      <animate attributeName="opacity" values="0.5;1;0.5" dur="1.5s" repeatCount="indefinite" />
                    )}
                  </rect>
                  {connState === "blocked" && (
                    <text x={CENTER_X} y={gateY + 3.5} textAnchor="middle" fill="#f5a623" fontSize="8" fontWeight="bold">!</text>
                  )}
                  {(connState === "passed" || connState === "flowing") && (
                    <text x={CENTER_X} y={gateY + 3.5} textAnchor="middle" fill="#0bbf8c" fontSize="8" fontWeight="bold">✓</text>
                  )}
                </g>
              )}
            </g>
          );
        })}

        {/* Agent Nodes */}
        {PIPELINE_ORDER.map((role, i) => {
          const x = CENTER_X;
          const y = START_Y + i * NODE_SPACING;
          const config = AGENT_CONFIG[role];
          const state = getStepState(role, status, outputs);
          const isStreaming = streamingAgent === role;

          const sc =
            state === "done" ? { fill: "rgba(11,191,140,0.12)", stroke: "#0bbf8c", text: "#0bbf8c" }
            : state === "active" ? { fill: withAlpha(config.color, 0.15), stroke: config.color, text: config.color }
            : state === "review" ? { fill: "rgba(245,166,35,0.12)", stroke: "#f5a623", text: "#f5a623" }
            : { fill: "rgba(255,255,255,0.03)", stroke: "#2a2f4a", text: "rgba(255,255,255,0.25)" };

          return (
            <g key={role} className="agent-node"
              onClick={() => onNodeClick?.(role)}
              style={{ cursor: onNodeClick ? "pointer" : undefined }}>

              {/* Radial glow behind active/done nodes */}
              {(state === "done" || state === "active") && (
                <circle cx={x} cy={y} r={R + 18} fill={state === "done" ? "#0bbf8c" : config.color}
                  opacity={state === "active" ? 0.08 : 0.06} filter="url(#nodeGlow)">
                  {state === "active" && (
                    <animate attributeName="opacity" values="0.04;0.12;0.04" dur="3s" repeatCount="indefinite" />
                  )}
                </circle>
              )}

              {/* Expanding ripple (active only) */}
              {state === "active" && (
                <>
                  <circle cx={x} cy={y} fill="none" stroke={config.color} strokeWidth="1" opacity="0">
                    <animate attributeName="r" values={`${R + 4};${R + 28}`} dur="2.5s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.35;0" dur="2.5s" repeatCount="indefinite" />
                  </circle>
                  <circle cx={x} cy={y} fill="none" stroke={config.color} strokeWidth="1" opacity="0">
                    <animate attributeName="r" values={`${R + 4};${R + 28}`} dur="2.5s" begin="1.25s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.35;0" dur="2.5s" begin="1.25s" repeatCount="indefinite" />
                  </circle>
                </>
              )}

              <circle className="node-hover-ring" cx={x} cy={y} r={R + 3}
                fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" strokeDasharray="4 3" opacity={0} />

              {/* Spinning orbit (active) */}
              {state === "active" && (
                <circle cx={x} cy={y} r={R + 5} fill="none" stroke={config.color}
                  strokeWidth="1.5" strokeDasharray="5 7" opacity="0.5">
                  <animateTransform attributeName="transform" type="rotate"
                    from={`0 ${x} ${y}`} to={`360 ${x} ${y}`} dur="5s" repeatCount="indefinite" />
                </circle>
              )}

              {/* Main circle */}
              <circle cx={x} cy={y} r={R} fill={sc.fill} stroke={sc.stroke}
                strokeWidth={state === "waiting" ? 1 : 2.5} />

              {/* Agent icon */}
              <foreignObject x={x - 14} y={y - 14} width="28" height="28">
                <div style={{ fontSize: 22, lineHeight: "28px", textAlign: "center", width: 28, height: 28 }}>
                  {config.icon}
                </div>
              </foreignObject>

              {/* Done badge */}
              {state === "done" && (
                <g>
                  <circle cx={x + R - 3} cy={y - R + 3} r="9" fill="#0bbf8c" stroke="#080b1a" strokeWidth="2" />
                  <text x={x + R - 3} y={y - R + 6.5} textAnchor="middle" fill="white" fontSize="9" fontWeight="bold">✓</text>
                </g>
              )}

              {/* Review badge */}
              {state === "review" && (
                <g>
                  <circle cx={x + R - 3} cy={y - R + 3} r="9" fill="#f5a623" stroke="#080b1a" strokeWidth="2">
                    <animate attributeName="fill-opacity" values="0.7;1;0.7" dur="1.5s" repeatCount="indefinite" />
                  </circle>
                  <text x={x + R - 3} y={y - R + 6.5} textAnchor="middle" fill="white" fontSize="9" fontWeight="bold">!</text>
                </g>
              )}

              {/* Name + status to the right */}
              <text x={x + R + 14} y={y - 4}
                fill={state === "waiting" ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.95)"}
                fontSize="14.5" fontWeight="700">
                {config.label}
              </text>
              <text x={x + R + 14} y={y + 13} fill={sc.text} fontSize="11" fontFamily="monospace"
                opacity={state === "waiting" ? 0.3 : 0.85}>
                {state === "done" ? "Shipped" : state === "active" ? "Working..." : state === "review" ? "Needs Review" : "Standby"}
              </text>

              {MODEL_LABELS[role] && (
                <text x={x + R + 14} y={y + 27} fill={MODEL_LABELS[role].providerColor}
                  fontSize="10" fontFamily="monospace" opacity={state === "waiting" ? 0.2 : 0.6}>
                  {MODEL_LABELS[role].model}
                </text>
              )}

              {/* Streaming badge — above node */}
              {isStreaming && (
                <g>
                  <rect x={x - 48} y={y - R - 24} width="96" height="20" rx="10"
                    fill="rgba(99,91,255,0.2)" stroke="rgba(99,91,255,0.4)" strokeWidth="1" />
                  <text x={x} y={y - R - 11} textAnchor="middle" fill="#a5a0ff" fontSize="10" fontFamily="monospace" fontWeight="600">
                    {streamTokens > 0 ? `${streamTokens} tok` : "..."}
                    {" · "}
                    {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
