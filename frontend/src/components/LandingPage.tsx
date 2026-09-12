"use client";

import { useRouter } from "next/navigation";
import { AGENT_CONFIG, PIPELINE_ORDER } from "@/lib/constants";

const FEATURES = [
  {
    icon: "🤖",
    title: "6 Specialized AI Agents",
    desc: "CEO, Business Analyst, Researcher, Architect, Engineer, and Presenter — each with a dedicated role in your pipeline.",
  },
  {
    icon: "⚡",
    title: "Multi-Model Intelligence",
    desc: "Agents powered by DeepSeek, NVIDIA Nemotron, and more. Automatic fallback chains ensure reliability.",
  },
  {
    icon: "🔄",
    title: "Real-Time Streaming",
    desc: "Watch your product come to life. Live token streaming, agent-by-agent progress, and instant output previews.",
  },
  {
    icon: "📦",
    title: "Production-Ready Output",
    desc: "Downloadable source code, architecture docs, PPTX presentations, and DOCX reports — all generated automatically.",
  },
  {
    icon: "🔗",
    title: "GitHub Integration",
    desc: "Push generated code directly to a GitHub repo. One click from idea to repository.",
  },
  {
    icon: "🛡️",
    title: "Security Scanning",
    desc: "Built-in security analysis catches vulnerabilities before code ships. Every build is scanned automatically.",
  },
];

const PIPELINE_STEPS = PIPELINE_ORDER.map((role, i) => ({
  role,
  ...AGENT_CONFIG[role],
  step: i + 1,
}));

export default function LandingPage() {
  const router = useRouter();

  return (
    <div style={{
      minHeight: "100vh",
      background: "#060918",
      color: "#fff",
      fontFamily: "system-ui, -apple-system, sans-serif",
      overflow: "hidden",
    }}>
      <style>{`
        @keyframes heroGlow {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 0.7; }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(24px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideRight {
          from { opacity: 0; transform: translateX(-20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes pipelinePulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(99, 91, 255, 0.3); }
          50% { box-shadow: 0 0 0 8px rgba(99, 91, 255, 0); }
        }
        @keyframes flowDash {
          to { stroke-dashoffset: -20; }
        }
        .land-btn {
          display: inline-flex; align-items: center; gap: 8px;
          padding: 14px 32px; border-radius: 12px; font-size: 16px;
          font-weight: 700; cursor: pointer; transition: all 0.2s ease;
          border: none; text-decoration: none;
        }
        .land-btn:hover { transform: translateY(-2px); }
        .land-btn-primary {
          background: linear-gradient(135deg, #635bff 0%, #7c3aed 100%);
          color: #fff;
          box-shadow: 0 4px 24px rgba(99, 91, 255, 0.35);
        }
        .land-btn-primary:hover {
          box-shadow: 0 8px 32px rgba(99, 91, 255, 0.5);
        }
        .land-btn-ghost {
          background: rgba(255,255,255,0.06);
          color: rgba(255,255,255,0.85);
          border: 1px solid rgba(255,255,255,0.1);
        }
        .land-btn-ghost:hover {
          background: rgba(255,255,255,0.1);
          border-color: rgba(255,255,255,0.2);
        }
        .land-feature-card {
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 16px; padding: 28px;
          transition: all 0.25s ease;
        }
        .land-feature-card:hover {
          background: rgba(99, 91, 255, 0.06);
          border-color: rgba(99, 91, 255, 0.2);
          transform: translateY(-4px);
        }
        .land-pipeline-node {
          transition: all 0.25s ease;
        }
        .land-pipeline-node:hover {
          transform: scale(1.08);
        }
      `}</style>

      {/* NAV */}
      <nav style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "20px 48px", maxWidth: 1200, margin: "0 auto",
        position: "relative", zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: "linear-gradient(135deg, #635bff, #7c3aed)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 900, fontSize: 14, color: "#fff",
          }}>FA</div>
          <span style={{ fontWeight: 800, fontSize: 20, letterSpacing: "-0.02em" }}>
            ForgeAI
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="land-btn land-btn-ghost" onClick={() => router.push("/login")}
            style={{ padding: "10px 24px", fontSize: 14 }}>
            Sign In
          </button>
          <button className="land-btn land-btn-primary" onClick={() => router.push("/register")}
            style={{ padding: "10px 24px", fontSize: 14 }}>
            Get Started
          </button>
        </div>
      </nav>

      {/* HERO */}
      <section style={{
        textAlign: "center", padding: "80px 24px 60px",
        position: "relative", maxWidth: 900, margin: "0 auto",
      }}>
        {/* Background glow */}
        <div style={{
          position: "absolute", top: -120, left: "50%", transform: "translateX(-50%)",
          width: 600, height: 400, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(99,91,255,0.15) 0%, transparent 70%)",
          animation: "heroGlow 6s ease-in-out infinite",
          pointerEvents: "none",
        }} />

        <div style={{ animation: "fadeUp 0.7s ease-out" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "6px 16px", borderRadius: 20,
            background: "rgba(99,91,255,0.1)", border: "1px solid rgba(99,91,255,0.2)",
            fontSize: 13, fontWeight: 600, color: "#a5a0ff", marginBottom: 24,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#0bbf8c" }} />
            6 AI Agents Working Together
          </div>

          <h1 style={{
            fontSize: "clamp(36px, 5vw, 64px)", fontWeight: 900, lineHeight: 1.1,
            letterSpacing: "-0.03em", marginBottom: 20,
            background: "linear-gradient(135deg, #fff 0%, rgba(255,255,255,0.7) 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          } as React.CSSProperties}>
            Describe a product.
            <br />
            <span style={{
              background: "linear-gradient(135deg, #635bff 0%, #a78bfa 50%, #06b6d4 100%)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            } as React.CSSProperties}>
              We build it.
            </span>
          </h1>

          <p style={{
            fontSize: 18, lineHeight: 1.6, color: "rgba(255,255,255,0.55)",
            maxWidth: 560, margin: "0 auto 40px",
          }}>
            ForgeAI is an AI software company. Six specialized agents analyze, design,
            code, and document your product — from a single sentence to production-ready output.
          </p>

          <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="land-btn land-btn-primary" onClick={() => router.push("/register")}>
              Start Building — Free
              <span style={{ fontSize: 18 }}>→</span>
            </button>
            <button className="land-btn land-btn-ghost" onClick={() => {
              document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
            }}>
              See How It Works
            </button>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS - Pipeline Visualization */}
      <section id="how-it-works" style={{
        padding: "80px 24px", maxWidth: 1000, margin: "0 auto",
      }}>
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <h2 style={{
            fontSize: 14, fontWeight: 700, letterSpacing: "0.12em",
            textTransform: "uppercase" as const, color: "#635bff", marginBottom: 12,
          }}>
            How It Works
          </h2>
          <h3 style={{
            fontSize: "clamp(24px, 3.5vw, 40px)", fontWeight: 800,
            letterSpacing: "-0.02em", color: "#fff",
          }}>
            Your AI team, step by step
          </h3>
        </div>

        {/* Pipeline flow */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          gap: 0, flexWrap: "wrap", padding: "0 16px",
        }}>
          {PIPELINE_STEPS.map((agent, i) => (
            <div key={agent.role} style={{
              display: "flex", alignItems: "center",
              animation: `slideRight 0.5s ease-out ${i * 0.1}s both`,
            }}>
              {/* Agent node */}
              <div className="land-pipeline-node" style={{
                display: "flex", flexDirection: "column", alignItems: "center",
                gap: 10, cursor: "default",
              }}>
                <div style={{
                  width: 64, height: 64, borderRadius: 16,
                  background: `rgba(${parseInt(agent.color.slice(1,3),16)},${parseInt(agent.color.slice(3,5),16)},${parseInt(agent.color.slice(5,7),16)},0.1)`,
                  border: `2px solid ${agent.color}40`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 28, position: "relative",
                }}>
                  {agent.icon}
                  <div style={{
                    position: "absolute", top: -6, right: -6,
                    width: 20, height: 20, borderRadius: "50%",
                    background: agent.color, display: "flex",
                    alignItems: "center", justifyContent: "center",
                    fontSize: 10, fontWeight: 800, color: "#fff",
                  }}>{agent.step}</div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.9)" }}>
                    {agent.label}
                  </div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", maxWidth: 90 }}>
                    {agent.description.split(",")[0]}
                  </div>
                </div>
              </div>

              {/* Arrow connector */}
              {i < PIPELINE_STEPS.length - 1 && (
                <svg width="48" height="20" viewBox="0 0 48 20" style={{ margin: "0 2px", marginBottom: 36, flexShrink: 0 }}>
                  <line x1="4" y1="10" x2="38" y2="10"
                    stroke="rgba(99,91,255,0.3)" strokeWidth="2" strokeDasharray="4 4"
                    style={{ animation: "flowDash 1s linear infinite" }} />
                  <polygon points="38,5 48,10 38,15" fill="rgba(99,91,255,0.4)" />
                </svg>
              )}
            </div>
          ))}
        </div>

        {/* Input → Output demo strip */}
        <div style={{
          marginTop: 56, display: "flex", alignItems: "center",
          justifyContent: "center", gap: 32, flexWrap: "wrap",
        }}>
          <div style={{
            background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 14, padding: "20px 28px", maxWidth: 300,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#635bff", letterSpacing: "0.08em", marginBottom: 8 }}>
              YOUR INPUT
            </div>
            <div style={{ fontSize: 15, color: "rgba(255,255,255,0.7)", lineHeight: 1.5, fontStyle: "italic" }}>
              &ldquo;Build a project management tool with Kanban boards and team collaboration&rdquo;
            </div>
          </div>

          <svg width="48" height="24" viewBox="0 0 48 24">
            <line x1="0" y1="12" x2="38" y2="12" stroke="#0bbf8c" strokeWidth="2.5" />
            <polygon points="38,6 48,12 38,18" fill="#0bbf8c" />
          </svg>

          <div style={{
            background: "rgba(11,191,140,0.06)", border: "1px solid rgba(11,191,140,0.15)",
            borderRadius: 14, padding: "20px 28px", maxWidth: 300,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#0bbf8c", letterSpacing: "0.08em", marginBottom: 8 }}>
              OUTPUT
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["Source Code", "Docs", "Slides", "Architecture"].map(item => (
                <span key={item} style={{
                  padding: "4px 12px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                  background: "rgba(11,191,140,0.1)", color: "#0bbf8c",
                  border: "1px solid rgba(11,191,140,0.2)",
                }}>{item}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES GRID */}
      <section style={{
        padding: "60px 24px 80px", maxWidth: 1100, margin: "0 auto",
      }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <h2 style={{
            fontSize: 14, fontWeight: 700, letterSpacing: "0.12em",
            textTransform: "uppercase" as const, color: "#635bff", marginBottom: 12,
          }}>
            Built for Builders
          </h2>
          <h3 style={{
            fontSize: "clamp(24px, 3.5vw, 36px)", fontWeight: 800,
            letterSpacing: "-0.02em", color: "#fff",
          }}>
            Everything you need to ship
          </h3>
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: 20,
        }}>
          {FEATURES.map((f) => (
            <div key={f.title} className="land-feature-card">
              <div style={{ fontSize: 28, marginBottom: 14 }}>{f.icon}</div>
              <h4 style={{ fontSize: 17, fontWeight: 700, marginBottom: 8, color: "#fff" }}>
                {f.title}
              </h4>
              <p style={{ fontSize: 14, lineHeight: 1.6, color: "rgba(255,255,255,0.45)", margin: 0 }}>
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* STATS BAR */}
      <section style={{
        padding: "48px 24px", maxWidth: 900, margin: "0 auto",
        display: "flex", justifyContent: "center", gap: 64, flexWrap: "wrap",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}>
        {[
          { value: "6", label: "AI Agents" },
          { value: "5+", label: "LLM Providers" },
          { value: "<5min", label: "Quick Build" },
          { value: "∞", label: "Possibilities" },
        ].map((s) => (
          <div key={s.label} style={{ textAlign: "center" }}>
            <div style={{
              fontSize: 36, fontWeight: 900, letterSpacing: "-0.02em",
              background: "linear-gradient(135deg, #635bff, #a78bfa)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            } as React.CSSProperties}>
              {s.value}
            </div>
            <div style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", fontWeight: 600, marginTop: 4 }}>
              {s.label}
            </div>
          </div>
        ))}
      </section>

      {/* FINAL CTA */}
      <section style={{
        padding: "80px 24px", textAlign: "center",
        position: "relative",
      }}>
        <div style={{
          position: "absolute", bottom: 0, left: "50%", transform: "translateX(-50%)",
          width: 500, height: 300, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(99,91,255,0.1) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />
        <h2 style={{
          fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 900,
          letterSpacing: "-0.02em", marginBottom: 16,
        }}>
          Ready to build?
        </h2>
        <p style={{
          fontSize: 16, color: "rgba(255,255,255,0.45)", marginBottom: 32,
          maxWidth: 440, margin: "0 auto 32px",
        }}>
          Describe your product in one sentence. Your AI team handles the rest.
        </p>
        <button className="land-btn land-btn-primary" onClick={() => router.push("/register")}
          style={{ fontSize: 18, padding: "16px 40px" }}>
          Start Building — Free
          <span style={{ fontSize: 20 }}>→</span>
        </button>
      </section>

      {/* FOOTER */}
      <footer style={{
        padding: "32px 48px", display: "flex",
        alignItems: "center", justifyContent: "space-between",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        maxWidth: 1200, margin: "0 auto",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 24, height: 24, borderRadius: 6,
            background: "linear-gradient(135deg, #635bff, #7c3aed)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 900, fontSize: 9, color: "#fff",
          }}>FA</div>
          <span style={{ fontWeight: 700, fontSize: 14, color: "rgba(255,255,255,0.5)" }}>
            ForgeAI
          </span>
        </div>
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.25)" }}>
          Built with AI, for builders.
        </div>
      </footer>
    </div>
  );
}
