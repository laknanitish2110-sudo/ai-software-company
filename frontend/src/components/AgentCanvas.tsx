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

const R = 36;

const NODES: Record<string, { x: number; y: number }> = {
  ceo: { x: 110, y: 110 },
  business_analyst: { x: 340, y: 110 },
  researcher: { x: 570, y: 110 },
  architect: { x: 570, y: 280 },
  engineer: { x: 340, y: 280 },
  ppt: { x: 110, y: 280 },
};

const CONNECTIONS = [
  { from: "ceo", to: "business_analyst", path: "M 146,110 L 304,110", hasGate: false, gateX: 225, gateY: 110, labelX: 225, labelY: 96 },
  { from: "business_analyst", to: "researcher", path: "M 376,110 L 534,110", hasGate: true, gateX: 455, gateY: 110, labelX: 455, labelY: 88 },
  { from: "researcher", to: "architect", path: "M 570,146 C 670,146 670,244 570,244", hasGate: true, gateX: 645, gateY: 195, labelX: 662, labelY: 182 },
  { from: "architect", to: "engineer", path: "M 534,280 L 376,280", hasGate: true, gateX: 455, gateY: 280, labelX: 455, labelY: 268 },
  { from: "engineer", to: "ppt", path: "M 304,280 L 146,280", hasGate: true, gateX: 225, gateY: 280, labelX: 225, labelY: 268 },
];

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

  return (
    <div
      className="card overflow-hidden"
      style={{
        background: "linear-gradient(145deg, #080b1a, #0f1330)",
        border: "1px solid #1a1f3a",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: streamingAgent
                ? "#635bff"
                : completedCount === 6
                  ? "#0bbf8c"
                  : "#2a2f4a",
              boxShadow: streamingAgent
                ? "0 0 8px #635bff"
                : completedCount === 6
                  ? "0 0 8px #0bbf8c"
                  : "none",
            }}
          />
          <span
            style={{
              color: "rgba(255,255,255,0.85)",
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: "0.02em",
            }}
          >
            Live Agent Canvas
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {streamingAgent && (
            <span
              style={{
                color: "#a5a0ff",
                fontSize: 11,
                fontFamily: "monospace",
              }}
            >
              {AGENT_CONFIG[streamingAgent]?.label} working...
            </span>
          )}
          <span
            style={{
              color: "rgba(255,255,255,0.35)",
              fontSize: 11,
              fontFamily: "monospace",
            }}
          >
            {completedCount}/6
          </span>
          <div
            style={{
              width: 60,
              height: 4,
              borderRadius: 2,
              background: "rgba(255,255,255,0.06)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${(completedCount / 6) * 100}%`,
                height: "100%",
                borderRadius: 2,
                background:
                  completedCount === 6
                    ? "#0bbf8c"
                    : "linear-gradient(90deg, #635bff, #7a73ff)",
                transition: "width 0.5s ease",
              }}
            />
          </div>
        </div>
      </div>

      {/* SVG Canvas */}
      <svg
        viewBox="0 0 900 380"
        style={{ width: "100%", display: "block" }}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <filter id="activeGlow">
            <feGaussianBlur stdDeviation="8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="particleGlow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <pattern
            id="bgDots"
            x="0"
            y="0"
            width="30"
            height="30"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="15" cy="15" r="0.5" fill="rgba(255,255,255,0.04)" />
          </pattern>
        </defs>

        {/* Background dot grid */}
        <rect width="900" height="380" fill="url(#bgDots)" />

        {/* Center watermark */}
        <text
          x="340"
          y="200"
          textAnchor="middle"
          fill="rgba(255,255,255,0.035)"
          fontSize="26"
          fontWeight="700"
          letterSpacing="0.2em"
        >
          AI SOFTWARE CO
        </text>

        {/* Connections */}
        {CONNECTIONS.map((conn, i) => {
          const state = getConnState(conn.from, conn.to, status, outputs);
          const color =
            state === "passed"
              ? "#0bbf8c"
              : state === "flowing"
                ? "#635bff"
                : state === "blocked"
                  ? "#f5a623"
                  : "#1e2340";

          return (
            <g key={`c-${i}`}>
              {/* Base connection line */}
              <path
                id={`path-${i}`}
                d={conn.path}
                fill="none"
                stroke={color}
                strokeWidth={state === "idle" ? 1.5 : 2}
                strokeDasharray={
                  state === "idle" || state === "blocked" ? "4 4" : undefined
                }
                opacity={state === "idle" ? 0.3 : 0.6}
              />

              {/* Animated flowing dashes for active transfer */}
              {state === "flowing" && (
                <path
                  d={conn.path}
                  fill="none"
                  stroke="#635bff"
                  strokeWidth="2"
                  strokeDasharray="8 12"
                  opacity="0.7"
                >
                  <animate
                    attributeName="stroke-dashoffset"
                    from="0"
                    to="-40"
                    dur="1s"
                    repeatCount="indefinite"
                  />
                </path>
              )}

              {/* Flowing particles */}
              {(state === "flowing" || state === "passed") &&
                [0, 0.6, 1.2].map((delay, j) => (
                  <circle
                    key={j}
                    r={j === 0 ? 3.5 : 2}
                    fill={color}
                    filter="url(#particleGlow)"
                    opacity={j === 0 ? 0.9 : 0.4}
                  >
                    <animateMotion
                      dur="2s"
                      repeatCount="indefinite"
                      begin={`${delay}s`}
                      calcMode="linear"
                    >
                      <mpath href={`#path-${i}`} />
                    </animateMotion>
                  </circle>
                ))}

              {/* Data flow label */}
              {(state === "flowing" || state === "passed") && (
                <text
                  x={conn.labelX}
                  y={conn.labelY}
                  textAnchor="middle"
                  fill="rgba(255,255,255,0.2)"
                  fontSize="9"
                  fontFamily="monospace"
                >
                  {DATA_LABELS[i]}
                </text>
              )}

              {/* Approval gate indicator */}
              {conn.hasGate && (
                <g>
                  <rect
                    x={conn.gateX - 7}
                    y={conn.gateY - 7}
                    width="14"
                    height="14"
                    rx="2"
                    transform={`rotate(45 ${conn.gateX} ${conn.gateY})`}
                    fill={
                      state === "blocked"
                        ? "rgba(245,166,35,0.2)"
                        : state === "passed" || state === "flowing"
                          ? "rgba(11,191,140,0.15)"
                          : "rgba(255,255,255,0.02)"
                    }
                    stroke={
                      state === "blocked"
                        ? "#f5a623"
                        : state === "passed" || state === "flowing"
                          ? "#0bbf8c"
                          : "#2a2f4a"
                    }
                    strokeWidth="1.5"
                    opacity={state === "idle" ? 0.4 : 1}
                  >
                    {state === "blocked" && (
                      <animate
                        attributeName="opacity"
                        values="0.5;1;0.5"
                        dur="1.5s"
                        repeatCount="indefinite"
                      />
                    )}
                  </rect>
                  {state === "blocked" && (
                    <text
                      x={conn.gateX}
                      y={conn.gateY + 3.5}
                      textAnchor="middle"
                      fill="#f5a623"
                      fontSize="9"
                      fontWeight="bold"
                    >
                      !
                    </text>
                  )}
                  {(state === "passed" || state === "flowing") && (
                    <text
                      x={conn.gateX}
                      y={conn.gateY + 3.5}
                      textAnchor="middle"
                      fill="#0bbf8c"
                      fontSize="9"
                      fontWeight="bold"
                    >
                      ✓
                    </text>
                  )}
                </g>
              )}
            </g>
          );
        })}

        {/* Agent Nodes */}
        {PIPELINE_ORDER.map((role) => {
          const { x, y } = NODES[role];
          const config = AGENT_CONFIG[role];
          const state = getStepState(role, status, outputs);
          const isStreaming = streamingAgent === role;

          const sc =
            state === "done"
              ? {
                  fill: "rgba(11,191,140,0.12)",
                  stroke: "#0bbf8c",
                  text: "#0bbf8c",
                }
              : state === "active"
                ? {
                    fill: withAlpha(config.color, 0.15),
                    stroke: config.color,
                    text: config.color,
                  }
                : state === "review"
                  ? {
                      fill: "rgba(245,166,35,0.12)",
                      stroke: "#f5a623",
                      text: "#f5a623",
                    }
                  : {
                      fill: "rgba(255,255,255,0.03)",
                      stroke: "#2a2f4a",
                      text: "rgba(255,255,255,0.25)",
                    };

          return (
            <g
              key={role}
              onClick={() => onNodeClick?.(role)}
              style={{ cursor: onNodeClick ? "pointer" : undefined }}
            >
              {/* Pulsing glow ring (active only) */}
              {state === "active" && (
                <circle
                  cx={x}
                  cy={y}
                  r={R + 8}
                  fill="none"
                  stroke={config.color}
                  strokeWidth="1"
                >
                  <animate
                    attributeName="r"
                    values={`${R + 6};${R + 14};${R + 6}`}
                    dur="2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.25;0.05;0.25"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}

              {/* Spinning orbit ring (active only) */}
              {state === "active" && (
                <circle
                  cx={x}
                  cy={y}
                  r={R + 4}
                  fill="none"
                  stroke={config.color}
                  strokeWidth="1.5"
                  strokeDasharray="6 8"
                  opacity="0.5"
                >
                  <animateTransform
                    attributeName="transform"
                    type="rotate"
                    from={`0 ${x} ${y}`}
                    to={`360 ${x} ${y}`}
                    dur="6s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}

              {/* Main node circle */}
              <circle
                cx={x}
                cy={y}
                r={R}
                fill={sc.fill}
                stroke={sc.stroke}
                strokeWidth={state === "waiting" ? 1 : 2}
              />

              {/* Agent icon (emoji) */}
              <foreignObject x={x - 15} y={y - 15} width="30" height="30">
                <div
                  style={{
                    fontSize: 24,
                    lineHeight: "30px",
                    textAlign: "center",
                    width: 30,
                    height: 30,
                  }}
                >
                  {config.icon}
                </div>
              </foreignObject>

              {/* Done badge (top-right of node) */}
              {state === "done" && (
                <g>
                  <circle
                    cx={x + R - 4}
                    cy={y - R + 4}
                    r="9"
                    fill="#0bbf8c"
                    stroke="#080b1a"
                    strokeWidth="2"
                  />
                  <text
                    x={x + R - 4}
                    y={y - R + 7.5}
                    textAnchor="middle"
                    fill="white"
                    fontSize="10"
                    fontWeight="bold"
                  >
                    ✓
                  </text>
                </g>
              )}

              {/* Review badge (top-right of node) */}
              {state === "review" && (
                <g>
                  <circle
                    cx={x + R - 4}
                    cy={y - R + 4}
                    r="9"
                    fill="#f5a623"
                    stroke="#080b1a"
                    strokeWidth="2"
                  >
                    <animate
                      attributeName="fill-opacity"
                      values="0.7;1;0.7"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                  </circle>
                  <text
                    x={x + R - 4}
                    y={y - R + 7.5}
                    textAnchor="middle"
                    fill="white"
                    fontSize="10"
                    fontWeight="bold"
                  >
                    !
                  </text>
                </g>
              )}

              {/* Agent name */}
              <text
                x={x}
                y={y + R + 18}
                textAnchor="middle"
                fill={
                  state === "waiting"
                    ? "rgba(255,255,255,0.3)"
                    : "rgba(255,255,255,0.85)"
                }
                fontSize="11.5"
                fontWeight="600"
              >
                {config.label}
              </text>

              {/* Status label */}
              <text
                x={x}
                y={y + R + 32}
                textAnchor="middle"
                fill={sc.text}
                fontSize="9.5"
                fontFamily="monospace"
                opacity={state === "waiting" ? 0.3 : 0.7}
              >
                {state === "done"
                  ? "Complete"
                  : state === "active"
                    ? "Working..."
                    : state === "review"
                      ? "Awaiting Review"
                      : "Standby"}
              </text>

              {/* Model/Provider badge */}
              {MODEL_LABELS[role] && (
                <text
                  x={x}
                  y={y + R + 46}
                  textAnchor="middle"
                  fill={MODEL_LABELS[role].providerColor}
                  fontSize="8"
                  fontFamily="monospace"
                  opacity={state === "waiting" ? 0.2 : 0.5}
                >
                  {MODEL_LABELS[role].model}
                </text>
              )}

              {/* Streaming metrics badge (above active node) */}
              {isStreaming && (
                <g>
                  <rect
                    x={x - 52}
                    y={y - R - 30}
                    width="104"
                    height="22"
                    rx="11"
                    fill="rgba(99,91,255,0.15)"
                    stroke="rgba(99,91,255,0.3)"
                    strokeWidth="1"
                  />
                  <text
                    x={x}
                    y={y - R - 15.5}
                    textAnchor="middle"
                    fill="#a5a0ff"
                    fontSize="10"
                    fontFamily="monospace"
                  >
                    {streamTokens > 0 ? `${streamTokens} tok` : "..."}
                    {" · "}
                    {Math.floor(elapsed / 60)}:
                    {String(elapsed % 60).padStart(2, "0")}
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
