"use client";

import { AGENT_CONFIG } from "@/lib/constants";

interface TimelineEntry {
  type: string;
  message: string;
  time: string;
}

interface Props {
  events: TimelineEntry[];
  projectStatus: string;
  createdAt?: string;
}

const EVENT_ICONS: Record<string, string> = {
  agent_started: "▶",
  agent_completed: "✓",
  approval_needed: "!",
  project_completed: "★",
  sandbox_started: "⚙",
  sandbox_completed: "⚙",
  peer_review_completed: "👁",
  route_selected: "🔀",
  error: "✕",
};

const AGENT_EVENTS = new Set([
  "agent_started",
  "agent_completed",
  "approval_needed",
  "project_completed",
  "sandbox_started",
  "sandbox_completed",
  "peer_review_completed",
  "route_selected",
  "error",
]);

function extractAgent(message: string): string | null {
  const lower = message.toLowerCase();
  for (const role of Object.keys(AGENT_CONFIG)) {
    const label = AGENT_CONFIG[role]?.label?.toLowerCase();
    if (label && lower.includes(label)) return role;
  }
  if (lower.includes("ceo")) return "ceo";
  if (lower.includes("analyst")) return "business_analyst";
  if (lower.includes("research")) return "researcher";
  if (lower.includes("architect")) return "architect";
  if (lower.includes("engineer")) return "engineer";
  if (lower.includes("presentation") || lower.includes("ppt")) return "ppt";
  return null;
}

export default function VersionTimeline({ events, projectStatus, createdAt }: Props) {
  const milestones = events.filter((e) => AGENT_EVENTS.has(e.type));
  const visible = milestones.slice(-20);
  const isRunning = projectStatus !== "completed";

  return (
    <div className="card p-4 animate-fade-in">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h3 className="font-semibold text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
          Timeline
        </h3>
        {createdAt && (
          <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "monospace" }}>
            {new Date(createdAt).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          </span>
        )}
      </div>

      <div style={{ position: "relative", paddingLeft: 20 }}>
        {/* Vertical line */}
        <div style={{
          position: "absolute", left: 6, top: 4, bottom: 4, width: 1,
          background: isRunning
            ? "linear-gradient(to bottom, var(--accent), var(--border))"
            : "var(--success)",
          opacity: 0.4,
        }} />

        {visible.length === 0 && (
          <div style={{ fontSize: 12, color: "var(--text-muted)", padding: "8px 0" }}>
            Waiting for first agent...
          </div>
        )}

        {visible.map((entry, i) => {
          const agent = extractAgent(entry.message);
          const config = agent ? AGENT_CONFIG[agent] : null;
          const icon = EVENT_ICONS[entry.type] || "·";
          const isError = entry.type === "error";
          const isComplete = entry.type === "agent_completed" || entry.type === "project_completed";
          const isReview = entry.type === "approval_needed";

          const dotColor = isError
            ? "var(--danger)"
            : isComplete
              ? "var(--success)"
              : isReview
                ? "var(--warning)"
                : config?.color || "var(--accent)";

          return (
            <div
              key={i}
              className="animate-slide-in"
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
                paddingBottom: i === visible.length - 1 ? 0 : 6,
                position: "relative",
              }}
            >
              {/* Dot */}
              <div style={{
                width: 13, height: 13, borderRadius: "50%",
                background: dotColor, flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 7, color: "white", fontWeight: 700,
                position: "relative", left: -20,
                border: "2px solid var(--bg-card)",
              }}>
                {icon}
              </div>

              {/* Content */}
              <div style={{ marginLeft: -16, minWidth: 0, flex: 1 }}>
                <div style={{
                  fontSize: 11,
                  color: isError ? "var(--danger)" : "var(--text-secondary)",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {config && <span style={{ marginRight: 4 }}>{config.icon}</span>}
                  {entry.message}
                </div>
                <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 1 }}>
                  {entry.time}
                </div>
              </div>
            </div>
          );
        })}

        {/* Current status indicator */}
        {isRunning && (
          <div style={{
            display: "flex", alignItems: "center", gap: 8, paddingTop: 6, position: "relative",
          }}>
            <div style={{
              width: 13, height: 13, borderRadius: "50%",
              background: "var(--accent)", flexShrink: 0,
              position: "relative", left: -20,
              border: "2px solid var(--bg-card)",
              animation: "pulse 2s infinite",
            }} />
            <span style={{ fontSize: 10, color: "var(--accent)", fontStyle: "italic", marginLeft: -16 }}>
              In progress...
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
