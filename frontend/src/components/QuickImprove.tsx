"use client";

import { useState } from "react";

interface Props {
  projectId: string;
  onImprove: (role: string, feedback: string) => Promise<void>;
}

const IMPROVEMENTS = [
  {
    label: "Add Tests",
    icon: "🧪",
    role: "engineer",
    feedback: "Add comprehensive unit tests and integration tests for the core functionality. Use the appropriate testing framework for this project (Jest, Pytest, etc). Cover edge cases and error handling.",
    color: "#10b981",
  },
  {
    label: "Improve UI",
    icon: "🎨",
    role: "engineer",
    feedback: "Improve the UI/UX: add better spacing, consistent colors, hover states, loading indicators, error states, responsive design, and accessibility. Make it feel polished and professional.",
    color: "#8b5cf6",
  },
  {
    label: "Fix Warnings",
    icon: "⚠️",
    role: "engineer",
    feedback: "Fix all linting warnings, TypeScript errors, unused imports, and console warnings. Clean up any TODO comments. Ensure the code passes strict linting without warnings.",
    color: "#f59e0b",
  },
  {
    label: "Optimize",
    icon: "⚡",
    role: "engineer",
    feedback: "Optimize performance: reduce bundle size, add lazy loading, minimize re-renders, optimize database queries, add caching where appropriate, and improve load times.",
    color: "#3b82f6",
  },
  {
    label: "Add Docs",
    icon: "📝",
    role: "engineer",
    feedback: "Add a comprehensive README.md with setup instructions, API documentation, architecture overview, and usage examples. Add inline JSDoc/docstring comments for all public functions and classes.",
    color: "#6366f1",
  },
  {
    label: "Security",
    icon: "🔒",
    role: "engineer",
    feedback: "Review and fix security issues: sanitize user inputs, prevent XSS/CSRF/SQL injection, add rate limiting, validate API inputs, use environment variables for secrets, and add authentication checks where needed.",
    color: "#ef4444",
  },
];

export default function QuickImprove({ projectId, onImprove }: Props) {
  const [running, setRunning] = useState<string | null>(null);
  const [done, setDone] = useState<Set<string>>(new Set());

  async function handleClick(improvement: typeof IMPROVEMENTS[0]) {
    if (running || done.has(improvement.label)) return;
    setRunning(improvement.label);
    try {
      await onImprove(improvement.role, improvement.feedback);
      setDone((prev) => new Set(prev).add(improvement.label));
    } finally {
      setRunning(null);
    }
  }

  return (
    <div className="card p-4 animate-fade-in">
      <h3
        className="font-semibold mb-3 text-xs uppercase tracking-wider"
        style={{ color: "var(--text-muted)" }}
      >
        Quick Improve
      </h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {IMPROVEMENTS.map((imp) => {
          const isDone = done.has(imp.label);
          const isRunning = running === imp.label;
          return (
            <button
              key={imp.label}
              onClick={() => handleClick(imp)}
              disabled={!!running || isDone}
              className="cursor-pointer transition-all"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 10px",
                borderRadius: 8,
                border: `1px solid ${isDone ? "var(--success-border)" : `${imp.color}30`}`,
                background: isDone
                  ? "var(--success-bg)"
                  : isRunning
                    ? `${imp.color}15`
                    : "var(--bg-elevated)",
                color: isDone ? "var(--success)" : "var(--text-secondary)",
                fontSize: 11,
                fontWeight: 500,
                opacity: running && !isRunning ? 0.5 : 1,
              }}
            >
              {isRunning ? (
                <span className="spinner" style={{ width: 12, height: 12 }} />
              ) : (
                <span style={{ fontSize: 13 }}>{isDone ? "✓" : imp.icon}</span>
              )}
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {isDone ? `${imp.label} sent` : imp.label}
              </span>
            </button>
          );
        })}
      </div>
      {running && (
        <div
          className="animate-fade-in"
          style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 8, textAlign: "center" }}
        >
          Sending improvement request to Engineer...
        </div>
      )}
    </div>
  );
}
