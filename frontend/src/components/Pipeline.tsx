"use client";

import { AGENT_CONFIG, PIPELINE_ORDER } from "@/lib/constants";

interface Props {
  status: string;
  outputs: Array<{ role: string; status: string }>;
}

function getStepState(
  role: string,
  status: string,
  outputs: Array<{ role: string; status: string }>
): "done" | "active" | "review" | "waiting" {
  const output = outputs.filter((o) => o.role === role).pop();

  if (output?.status === "approved") return "done";

  const reviewStatuses: Record<string, string> = {
    business_analyst: "ba_review",
    researcher: "research_review",
    architect: "architect_review",
    engineer: "engineer_review",
  };
  if (reviewStatuses[role] === status) return "review";

  const workingStatuses: Record<string, string> = {
    business_analyst: "ba_working",
    researcher: "research_working",
    architect: "architect_working",
    engineer: "engineer_working",
    ppt: "ppt_working",
  };
  if (workingStatuses[role] === status) return "active";

  if (role === "ceo") {
    const ceoOutput = outputs.find((o) => o.role === "ceo");
    if (ceoOutput) return "done";
    if (status === "created") return "active";
  }

  if (role === "ppt" && status === "completed") return "done";

  return "waiting";
}

const STATE_STYLES = {
  done: {
    bg: "var(--success-bg)",
    border: "var(--success-border)",
    text: "var(--success)",
    icon: "✓",
    line: "var(--success)",
  },
  active: {
    bg: "var(--accent-bg)",
    border: "var(--accent-border)",
    text: "var(--accent)",
    icon: null,
    line: "var(--border)",
  },
  review: {
    bg: "var(--warning-bg)",
    border: "var(--warning-border)",
    text: "var(--warning)",
    icon: "!",
    line: "var(--border)",
  },
  waiting: {
    bg: "var(--bg-elevated)",
    border: "var(--border)",
    text: "var(--text-muted)",
    icon: null,
    line: "var(--border)",
  },
};

export default function Pipeline({ status, outputs }: Props) {
  const completedCount = PIPELINE_ORDER.filter(
    (role) => getStepState(role, status, outputs) === "done"
  ).length;
  const progress = (completedCount / PIPELINE_ORDER.length) * 100;

  return (
    <div className="card p-5">
      {/* Progress bar */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
          Pipeline Progress
        </span>
        <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
          {completedCount}/{PIPELINE_ORDER.length}
        </span>
      </div>
      <div className="h-1 rounded-full mb-5" style={{ background: "var(--bg-elevated)" }}>
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${progress}%`,
            background: progress === 100
              ? "linear-gradient(90deg, #0bbf8c, #00d4aa)"
              : "linear-gradient(90deg, #635bff, #7a73ff)",
          }}
        />
      </div>

      {/* Steps */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
        {PIPELINE_ORDER.map((role, i) => {
          const config = AGENT_CONFIG[role];
          const state = getStepState(role, status, outputs);
          const styles = STATE_STYLES[state];

          return (
            <div key={role} className="flex items-center animate-fade-in" style={{ animationDelay: `${i * 0.05}s` }}>
              <div
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm whitespace-nowrap transition-all"
                style={{
                  background: styles.bg,
                  border: `1px solid ${styles.border}`,
                  color: styles.text,
                  ...(state === "active" ? { animation: "pulseGlow 2s infinite" } : {}),
                }}
              >
                <span className="text-base">{config.icon}</span>
                <span className="font-medium text-[13px]">{config.label}</span>
                {styles.icon && (
                  <span className="text-[11px] font-bold">{styles.icon}</span>
                )}
                {state === "active" && (
                  <span className="dot-loading ml-0.5">
                    <span /><span /><span />
                  </span>
                )}
              </div>
              {i < PIPELINE_ORDER.length - 1 && (
                <div
                  className="w-5 h-px mx-0.5 transition-colors duration-500"
                  style={{ background: styles.line }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
