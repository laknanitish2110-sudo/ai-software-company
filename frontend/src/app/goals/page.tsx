"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import {
  listGoals, createGoal, deleteGoal, decomposeGoal, startGoal,
  listGoalTasks, getGoalProgress, listEmployees,
  type Goal, type GoalTask, type Employee,
} from "@/lib/api";
import { ThinkingOrb } from "thinking-orbs";

const PRIORITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f59e0b",
  medium: "#3b82f6",
  low: "#8898aa",
};

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  draft:     { label: "Draft",      color: "#8898aa", bg: "rgba(136,152,170,0.1)" },
  planned:   { label: "Planned",    color: "#8b5cf6", bg: "rgba(139,92,246,0.1)" },
  running:   { label: "Running",    color: "#0bbf8c", bg: "rgba(11,191,140,0.1)" },
  completed: { label: "Completed",  color: "#22c55e", bg: "rgba(34,197,94,0.1)" },
  failed:    { label: "Failed",     color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  paused:    { label: "Paused",     color: "#f5a623", bg: "rgba(245,166,35,0.1)" },
};

const TASK_STATUS_META: Record<string, { color: string; icon: string }> = {
  pending:   { color: "#8898aa", icon: "○" },
  running:   { color: "#635bff", icon: "◉" },
  completed: { color: "#22c55e", icon: "✓" },
  failed:    { color: "#ef4444", icon: "✕" },
  blocked:   { color: "#f5a623", icon: "⊘" },
};

function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] || STATUS_META.draft;
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, padding: "2px 10px", borderRadius: 99,
      color: meta.color, background: meta.bg, textTransform: "uppercase", letterSpacing: 0.5,
    }}>{meta.label}</span>
  );
}

function ProgressBar({ progress, total, completed }: { progress: number; total: number; completed: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
      <div style={{
        flex: 1, height: 6, borderRadius: 3,
        background: "var(--border)", overflow: "hidden",
      }}>
        <div style={{
          width: `${progress}%`, height: "100%", borderRadius: 3,
          background: progress === 100 ? "#22c55e" : "linear-gradient(90deg, #635bff, #7c3aed)",
          transition: "width 0.4s ease",
        }} />
      </div>
      <span style={{ fontSize: 11, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
        {completed}/{total}
      </span>
    </div>
  );
}

function GoalCard({
  goal, employees, onExpand, expanded, onDelete, onDecompose, onStart, tasks,
}: {
  goal: Goal; employees: Employee[];
  onExpand: () => void; expanded: boolean;
  onDelete: () => void; onDecompose: () => void; onStart: () => void;
  tasks: GoalTask[];
}) {
  const meta = STATUS_META[goal.status] || STATUS_META.draft;
  const owner = employees.find(e => e.id === goal.owner_employee_id);

  return (
    <div style={{
      borderRadius: 14, background: "var(--bg-card)",
      border: "1px solid var(--border)", overflow: "hidden",
      transition: "border-color 0.2s",
    }}>
      <div
        onClick={onExpand}
        style={{
          padding: "16px 20px", cursor: "pointer",
          display: "flex", alignItems: "center", gap: 14,
        }}
      >
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: `linear-gradient(135deg, ${meta.color}22, ${meta.color}44)`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, flexShrink: 0,
        }}>🎯</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ fontWeight: 600, fontSize: 15, color: "var(--text-primary)" }}>
              {goal.title}
            </span>
            <StatusBadge status={goal.status} />
            <span style={{
              fontSize: 10, fontWeight: 600, padding: "1px 6px", borderRadius: 4,
              color: PRIORITY_COLORS[goal.priority] || "#8898aa",
              background: `${PRIORITY_COLORS[goal.priority] || "#8898aa"}18`,
              textTransform: "uppercase",
            }}>{goal.priority}</span>
          </div>
          {goal.description && (
            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.4 }}>
              {goal.description.length > 100 ? goal.description.slice(0, 100) + "..." : goal.description}
            </div>
          )}
          {goal.total_tasks > 0 && (
            <div style={{ marginTop: 8 }}>
              <ProgressBar progress={goal.progress} total={goal.total_tasks} completed={goal.completed_tasks} />
            </div>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {owner && (
            <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>{owner.name}</span>
          )}
          <span style={{
            fontSize: 12, transition: "transform 0.2s",
            transform: expanded ? "rotate(180deg)" : "rotate(0)",
            color: "var(--text-secondary)",
          }}>▼</span>
        </div>
      </div>

      {expanded && (
        <div style={{
          borderTop: "1px solid var(--border)", padding: "16px 20px",
          background: "var(--bg-secondary)",
        }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            {goal.status === "draft" && (
              <button onClick={onDecompose} style={{
                padding: "6px 14px", borderRadius: 8, border: "none",
                background: "linear-gradient(135deg, #635bff, #7c3aed)",
                color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}>Plan Tasks</button>
            )}
            {goal.status === "planned" && (
              <button onClick={onStart} style={{
                padding: "6px 14px", borderRadius: 8, border: "none",
                background: "linear-gradient(135deg, #0bbf8c, #059669)",
                color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}>Start Execution</button>
            )}
            <button onClick={onDelete} style={{
              padding: "6px 14px", borderRadius: 8,
              border: "1px solid var(--border)", background: "transparent",
              color: "#ef4444", fontSize: 12, fontWeight: 500, cursor: "pointer",
            }}>Delete</button>
          </div>

          {tasks.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>
                Task Graph ({tasks.length} tasks)
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {tasks.map((t) => {
                  const tMeta = TASK_STATUS_META[t.status] || TASK_STATUS_META.pending;
                  const assignee = employees.find(e => e.id === t.assigned_employee_id);
                  return (
                    <div key={t.id} style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "8px 12px", borderRadius: 8,
                      background: "var(--bg-card)", border: "1px solid var(--border)",
                    }}>
                      <span style={{ color: tMeta.color, fontSize: 14, fontWeight: 700, width: 16 }}>
                        {tMeta.icon}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
                          {t.title}
                        </div>
                        {t.description && (
                          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                            {t.description.length > 80 ? t.description.slice(0, 80) + "..." : t.description}
                          </div>
                        )}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                        {assignee && (
                          <span style={{
                            fontSize: 10, padding: "2px 8px", borderRadius: 6,
                            background: "var(--border)", color: "var(--text-secondary)",
                          }}>{assignee.name}</span>
                        )}
                        <span style={{
                          fontSize: 10, fontWeight: 600, padding: "2px 6px",
                          borderRadius: 4, color: tMeta.color,
                          background: `${tMeta.color}18`, textTransform: "uppercase",
                        }}>{t.status}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {goal.result && (
            <div style={{
              marginTop: 12, padding: "10px 12px", borderRadius: 8,
              background: goal.status === "completed" ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
              fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5,
            }}>
              <strong>Result:</strong> {goal.result}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function GoalsPage() {
  const { user, loading: authLoading } = useAuth();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [taskMap, setTaskMap] = useState<Record<string, GoalTask[]>>({});
  const [creating, setCreating] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPriority, setNewPriority] = useState("medium");
  const [newOwner, setNewOwner] = useState("");

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      const [goalsRes, empsRes] = await Promise.all([
        listGoals(), listEmployees(),
      ]);
      setGoals(goalsRes.goals);
      setEmployees(empsRes);
    } catch {
      // noop
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!authLoading && user) refresh();
  }, [authLoading, user, refresh]);

  const handleExpand = async (goalId: string) => {
    if (expandedId === goalId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(goalId);
    if (!taskMap[goalId]) {
      try {
        const res = await listGoalTasks(goalId);
        setTaskMap(prev => ({ ...prev, [goalId]: res.tasks }));
      } catch {
        // noop
      }
    }
  };

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    setActionLoading("create");
    try {
      await createGoal({
        title: newTitle.trim(),
        description: newDesc.trim() || undefined,
        priority: newPriority,
        owner_employee_id: newOwner || undefined,
      });
      setNewTitle(""); setNewDesc(""); setNewPriority("medium"); setNewOwner("");
      setCreating(false);
      await refresh();
    } catch {
      // noop
    } finally {
      setActionLoading(null);
    }
  };

  const handleDecompose = async (goalId: string) => {
    setActionLoading(goalId);
    try {
      const res = await decomposeGoal(goalId);
      setTaskMap(prev => ({ ...prev, [goalId]: res.tasks }));
      await refresh();
    } catch {
      // noop
    } finally {
      setActionLoading(null);
    }
  };

  const handleStart = async (goalId: string) => {
    setActionLoading(goalId);
    try {
      await startGoal(goalId);
      const res = await listGoalTasks(goalId);
      setTaskMap(prev => ({ ...prev, [goalId]: res.tasks }));
      await refresh();
    } catch {
      // noop
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (goalId: string) => {
    setActionLoading(goalId);
    try {
      await deleteGoal(goalId);
      setExpandedId(null);
      await refresh();
    } catch {
      // noop
    } finally {
      setActionLoading(null);
    }
  };

  if (authLoading || loading) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", minHeight: "60vh", gap: 16,
      }}>
        <ThinkingOrb size={64} state="solving" />
        <div style={{ color: "var(--text-secondary)", fontSize: 14 }}>Loading goals...</div>
      </div>
    );
  }

  const stats = {
    total: goals.length,
    running: goals.filter(g => g.status === "running").length,
    completed: goals.filter(g => g.status === "completed").length,
    draft: goals.filter(g => g.status === "draft" || g.status === "planned").length,
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 16px" }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 24,
      }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
            Goals
          </h1>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "4px 0 0" }}>
            Set objectives, decompose into tasks, assign to your team
          </p>
        </div>
        <button
          onClick={() => setCreating(!creating)}
          style={{
            padding: "8px 18px", borderRadius: 10, border: "none",
            background: "linear-gradient(135deg, #635bff, #7c3aed)",
            color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
          }}
        >+ New Goal</button>
      </div>

      {/* Stats */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12,
        marginBottom: 20,
      }}>
        {[
          { label: "Total", value: stats.total, color: "#635bff" },
          { label: "Active", value: stats.running, color: "#0bbf8c" },
          { label: "Completed", value: stats.completed, color: "#22c55e" },
          { label: "Drafts", value: stats.draft, color: "#8898aa" },
        ].map(s => (
          <div key={s.label} style={{
            padding: "14px 16px", borderRadius: 12,
            background: "var(--bg-card)", border: "1px solid var(--border)",
            textAlign: "center",
          }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Create Form */}
      {creating && (
        <div style={{
          padding: 20, borderRadius: 14, marginBottom: 20,
          background: "var(--bg-card)", border: "1px solid var(--border)",
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "var(--text-primary)" }}>
            New Goal
          </div>
          <input
            value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
            placeholder="What do you want to achieve?"
            style={{
              width: "100%", padding: "10px 12px", borderRadius: 8,
              border: "1px solid var(--border)", background: "var(--bg-secondary)",
              color: "var(--text-primary)", fontSize: 14, marginBottom: 10,
              outline: "none", boxSizing: "border-box",
            }}
          />
          <textarea
            value={newDesc}
            onChange={e => setNewDesc(e.target.value)}
            placeholder="Describe the goal in detail (optional)"
            rows={3}
            style={{
              width: "100%", padding: "10px 12px", borderRadius: 8,
              border: "1px solid var(--border)", background: "var(--bg-secondary)",
              color: "var(--text-primary)", fontSize: 13, marginBottom: 10,
              outline: "none", resize: "vertical", boxSizing: "border-box",
              fontFamily: "inherit",
            }}
          />
          <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>
                Priority
              </label>
              <select
                value={newPriority}
                onChange={e => setNewPriority(e.target.value)}
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: 8,
                  border: "1px solid var(--border)", background: "var(--bg-secondary)",
                  color: "var(--text-primary)", fontSize: 13, outline: "none",
                }}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>
                Owner (optional)
              </label>
              <select
                value={newOwner}
                onChange={e => setNewOwner(e.target.value)}
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: 8,
                  border: "1px solid var(--border)", background: "var(--bg-secondary)",
                  color: "var(--text-primary)", fontSize: 13, outline: "none",
                }}
              >
                <option value="">No owner</option>
                {employees.filter(e => e.status !== "archived").map(e => (
                  <option key={e.id} value={e.id}>{e.name} ({e.role})</option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleCreate}
              disabled={!newTitle.trim() || actionLoading === "create"}
              style={{
                padding: "8px 18px", borderRadius: 8, border: "none",
                background: "linear-gradient(135deg, #635bff, #7c3aed)",
                color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
                opacity: !newTitle.trim() || actionLoading === "create" ? 0.5 : 1,
              }}
            >
              {actionLoading === "create" ? "Creating..." : "Create Goal"}
            </button>
            <button
              onClick={() => setCreating(false)}
              style={{
                padding: "8px 14px", borderRadius: 8,
                border: "1px solid var(--border)", background: "transparent",
                color: "var(--text-secondary)", fontSize: 13, cursor: "pointer",
              }}
            >Cancel</button>
          </div>
        </div>
      )}

      {/* Goal List */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {goals.length === 0 ? (
          <div style={{
            textAlign: "center", padding: 60,
            color: "var(--text-secondary)", fontSize: 14,
          }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🎯</div>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>No goals yet</div>
            <div style={{ fontSize: 12 }}>
              Create a goal to break it into tasks and assign to your AI team
            </div>
          </div>
        ) : (
          goals.map(g => (
            <GoalCard
              key={g.id}
              goal={g}
              employees={employees}
              expanded={expandedId === g.id}
              onExpand={() => handleExpand(g.id)}
              onDelete={() => handleDelete(g.id)}
              onDecompose={() => handleDecompose(g.id)}
              onStart={() => handleStart(g.id)}
              tasks={taskMap[g.id] || []}
            />
          ))
        )}
      </div>
    </div>
  );
}
