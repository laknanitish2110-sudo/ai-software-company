"use client";

import { useState } from "react";

interface OnboardingModalProps {
  onDismiss: () => void;
  onTryPipeline: () => void;
  onTryEmployee: () => void;
}

const STEPS = [
  {
    title: "Welcome to ForgeAI",
    subtitle: "Your AI software company — two powerful ways to work",
    content: "welcome",
  },
  {
    title: "The Pipeline",
    subtitle: "One-shot project builder",
    content: "pipeline",
  },
  {
    title: "AI Employees",
    subtitle: "Persistent teammates with memory",
    content: "employees",
  },
  {
    title: "Ready to start?",
    subtitle: "Choose how you want to begin",
    content: "cta",
  },
];

export default function OnboardingModal({ onDismiss, onTryPipeline, onTryEmployee }: OnboardingModalProps) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)",
      animation: "fadeIn 0.2s ease-out",
    }} onClick={(e) => { if (e.target === e.currentTarget) onDismiss(); }}>
      <div style={{
        width: "min(520px, calc(100vw - 40px))", borderRadius: 20,
        background: "var(--bg-card)", border: "1px solid var(--border)",
        boxShadow: "0 24px 80px rgba(0,0,0,0.2)", overflow: "hidden",
        animation: "slideUp 0.3s ease-out",
      }}>
        {/* Progress dots */}
        <div style={{
          display: "flex", justifyContent: "center", gap: 6,
          padding: "16px 0 0",
        }}>
          {STEPS.map((_, i) => (
            <div key={i} style={{
              width: i === step ? 24 : 8, height: 8, borderRadius: 4,
              background: i === step ? "var(--accent)" : "var(--border)",
              transition: "all 0.3s",
            }} />
          ))}
        </div>

        <div style={{ padding: "24px 32px 32px" }}>
          <h2 style={{
            fontSize: 22, fontWeight: 800, color: "var(--text-primary)",
            marginBottom: 4, textAlign: "center",
          }}>{current.title}</h2>
          <p style={{
            fontSize: 14, color: "var(--text-secondary)", textAlign: "center",
            marginBottom: 24,
          }}>{current.subtitle}</p>

          {current.content === "welcome" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{
                padding: 20, borderRadius: 12, background: "rgba(99,91,255,0.04)",
                border: "1px solid rgba(99,91,255,0.12)", textAlign: "center",
              }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>⚡</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>Pipeline</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>6 agents build your project end-to-end in minutes</div>
              </div>
              <div style={{
                padding: 20, borderRadius: 12, background: "rgba(16,185,129,0.04)",
                border: "1px solid rgba(16,185,129,0.12)", textAlign: "center",
              }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>👥</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>Employees</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Chat with persistent AI teammates who learn and remember</div>
              </div>
            </div>
          )}

          {current.content === "pipeline" && (
            <div>
              <div style={{
                display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center", marginBottom: 16,
              }}>
                {["CEO", "Business Analyst", "Researcher", "Architect", "Engineer", "Presenter"].map((role, i) => (
                  <div key={role} style={{
                    padding: "6px 14px", borderRadius: 20, fontSize: 12, fontWeight: 600,
                    background: `hsla(${250 + i * 20}, 70%, 60%, 0.08)`,
                    border: `1px solid hsla(${250 + i * 20}, 70%, 60%, 0.15)`,
                    color: `hsl(${250 + i * 20}, 70%, 50%)`,
                  }}>{role}</div>
                ))}
              </div>
              <div style={{
                padding: 16, borderRadius: 10, background: "var(--bg-page)",
                border: "1px solid var(--border)", fontSize: 13, color: "var(--text-secondary)",
                lineHeight: 1.6,
              }}>
                Describe what you want to build, and 6 specialized agents work in sequence — analyzing requirements,
                researching tech, designing architecture, writing code, and creating a presentation. Get a complete
                project in under 5 minutes.
              </div>
            </div>
          )}

          {current.content === "employees" && (
            <div>
              <div style={{
                display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16,
              }}>
                {[
                  { name: "Arc", role: "Architect", color: "#635bff" },
                  { name: "Atlas", role: "Developer", color: "#10b981" },
                  { name: "Sage", role: "Analyst", color: "#f59e0b" },
                  { name: "Scout", role: "Researcher", color: "#3b82f6" },
                  { name: "Sentinel", role: "QA/Security", color: "#ef4444" },
                  { name: "Scribe", role: "Documentation", color: "#8b5cf6" },
                ].map((emp) => (
                  <div key={emp.name} style={{
                    padding: "10px 14px", borderRadius: 10, display: "flex", alignItems: "center", gap: 10,
                    background: "var(--bg-page)", border: "1px solid var(--border)",
                  }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: "50%",
                      background: `${emp.color}18`, border: `1.5px solid ${emp.color}30`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 11, fontWeight: 800, color: emp.color,
                    }}>{emp.name[0]}</div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>{emp.name}</div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{emp.role}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{
                padding: 16, borderRadius: 10, background: "var(--bg-page)",
                border: "1px solid var(--border)", fontSize: 13, color: "var(--text-secondary)",
                lineHeight: 1.6,
              }}>
                Chat with AI employees who remember past conversations, learn new skills, use tools,
                and even delegate tasks to each other. They persist between sessions.
              </div>
            </div>
          )}

          {current.content === "cta" && (
            <div style={{ display: "grid", gap: 12 }}>
              <button onClick={onTryPipeline} style={{
                padding: "14px 20px", borderRadius: 12, fontSize: 14, fontWeight: 700,
                background: "var(--accent)", color: "#fff", border: "none",
                cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              }}>
                ⚡ Try the Pipeline
                <span style={{ fontSize: 11, fontWeight: 400, opacity: 0.8 }}>Build a project in minutes</span>
              </button>
              <button onClick={onTryEmployee} style={{
                padding: "14px 20px", borderRadius: 12, fontSize: 14, fontWeight: 700,
                background: "rgba(16,185,129,0.08)", color: "#10b981",
                border: "1px solid rgba(16,185,129,0.2)", cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              }}>
                👥 Meet your team
                <span style={{ fontSize: 11, fontWeight: 400, opacity: 0.8 }}>Chat with an AI employee</span>
              </button>
              <button onClick={onDismiss} style={{
                padding: "10px", fontSize: 12, fontWeight: 500,
                background: "none", border: "none", color: "var(--text-muted)",
                cursor: "pointer",
              }}>
                Skip — I'll explore on my own
              </button>
            </div>
          )}

          {/* Navigation */}
          {current.content !== "cta" && (
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              marginTop: 24,
            }}>
              <button
                onClick={() => step > 0 ? setStep(step - 1) : onDismiss()}
                style={{
                  padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                  background: "none", border: "1px solid var(--border)",
                  color: "var(--text-secondary)", cursor: "pointer",
                }}
              >{step === 0 ? "Skip" : "Back"}</button>
              <button
                onClick={() => setStep(step + 1)}
                style={{
                  padding: "8px 20px", borderRadius: 8, fontSize: 13, fontWeight: 700,
                  background: "var(--accent)", color: "#fff", border: "none",
                  cursor: "pointer",
                }}
              >Next</button>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}
