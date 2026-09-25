"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";

const PIPELINE_AGENTS = [
  { icon: "👨‍💼", label: "CEO", desc: "Understands the problem", color: "#635bff" },
  { icon: "📋", label: "Business Analyst", desc: "Defines requirements", color: "#0bbf8c" },
  { icon: "🔍", label: "Researcher", desc: "Finds best approaches", color: "#f5a623" },
  { icon: "🏗️", label: "Architect", desc: "Designs the system", color: "#8b5cf6" },
  { icon: "💻", label: "Engineer", desc: "Builds working code", color: "#ef4444" },
  { icon: "📊", label: "Presenter", desc: "Creates deliverables", color: "#06b6d4" },
];

const EMPLOYEES = [
  { icon: "🏗️", name: "Arc", role: "Solution Architect", skills: ["System Design", "API Design", "Database Schemas"], color: "#8b5cf6" },
  { icon: "📋", name: "Sage", role: "Business Analyst", skills: ["Requirements", "Competitive Analysis", "Scoping"], color: "#0bbf8c" },
  { icon: "🔍", name: "Scout", role: "Research Specialist", skills: ["Tech Research", "Market Analysis", "Best Practices"], color: "#3b82f6" },
  { icon: "⚡", name: "Atlas", role: "Full-Stack Engineer", skills: ["Implementation", "Bug Fixes", "Code Review"], color: "#f59e0b" },
  { icon: "🛡️", name: "Sentinel", role: "QA & Security", skills: ["Testing", "Security Audits", "Performance"], color: "#ef4444" },
  { icon: "✍️", name: "Scribe", role: "Technical Writer", skills: ["Documentation", "API Docs", "Reports"], color: "#06b6d4" },
];

const DEMO_LINES = [
  "Build a real-time collaboration tool with video chat and shared whiteboards",
  "Create a personal finance tracker with AI-powered spending insights",
  "Design a restaurant ordering platform with kitchen display integration",
];

export default function LandingPage() {
  const router = useRouter();
  const [demoIdx, setDemoIdx] = useState(0);
  const [typed, setTyped] = useState("");
  const [activeAgent, setActiveAgent] = useState(-1);

  useEffect(() => {
    const line = DEMO_LINES[demoIdx];
    let i = 0;
    setTyped("");
    setActiveAgent(-1);
    const typeTimer = setInterval(() => {
      if (i <= line.length) {
        setTyped(line.slice(0, i));
        i++;
      } else {
        clearInterval(typeTimer);
        let agent = 0;
        const agentTimer = setInterval(() => {
          if (agent < PIPELINE_AGENTS.length) {
            setActiveAgent(agent);
            agent++;
          } else {
            clearInterval(agentTimer);
            setTimeout(() => {
              setDemoIdx((prev) => (prev + 1) % DEMO_LINES.length);
            }, 2000);
          }
        }, 600);
        return () => clearInterval(agentTimer);
      }
    }, 35);
    return () => clearInterval(typeTimer);
  }, [demoIdx]);

  return (
    <div style={{ minHeight: "100vh", background: "#060918", color: "#fff", fontFamily: "system-ui, -apple-system, sans-serif", overflowX: "hidden" }}>
      <style>{`
        @keyframes heroGlow { 0%, 100% { opacity: 0.3; transform: scale(1); } 50% { opacity: 0.6; transform: scale(1.05); } }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideIn { from { opacity: 0; transform: translateX(-16px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
        @keyframes typeCursor { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
        @keyframes orbitSlow { 0% { transform: rotate(0deg) translateX(280px) rotate(0deg); } 100% { transform: rotate(360deg) translateX(280px) rotate(-360deg); } }
        @keyframes pipeFlow { 0% { stroke-dashoffset: 20; } 100% { stroke-dashoffset: 0; } }
        .land-btn { display: inline-flex; align-items: center; gap: 8px; padding: 14px 32px; border-radius: 12px; font-size: 16px; font-weight: 700; cursor: pointer; transition: all 0.25s ease; border: none; text-decoration: none; }
        .land-btn:hover { transform: translateY(-2px); }
        .land-btn-primary { background: linear-gradient(135deg, #635bff 0%, #7c3aed 100%); color: #fff; box-shadow: 0 4px 24px rgba(99,91,255,0.35); }
        .land-btn-primary:hover { box-shadow: 0 8px 40px rgba(99,91,255,0.55); }
        .land-btn-secondary { background: rgba(11,191,140,0.12); color: #0bbf8c; border: 1.5px solid rgba(11,191,140,0.3); }
        .land-btn-secondary:hover { background: rgba(11,191,140,0.2); border-color: rgba(11,191,140,0.5); box-shadow: 0 4px 24px rgba(11,191,140,0.2); }
        .land-btn-ghost { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.85); border: 1px solid rgba(255,255,255,0.1); }
        .land-btn-ghost:hover { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.2); }
        .emp-card { background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 24px; transition: all 0.3s ease; cursor: default; }
        .emp-card:hover { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.12); transform: translateY(-6px); }
        .feat-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 20px; padding: 32px; transition: all 0.3s ease; position: relative; overflow: hidden; }
        .feat-card:hover { border-color: rgba(99,91,255,0.25); transform: translateY(-4px); }
        .feat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, var(--fc-color, #635bff), transparent); opacity: 0; transition: opacity 0.3s; }
        .feat-card:hover::before { opacity: 1; }
        .section-label { font-size: 13px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 12px; }
        .section-title { font-size: clamp(28px, 4vw, 44px); font-weight: 900; letter-spacing: -0.03em; line-height: 1.15; }
        @media (max-width: 768px) {
          .hero-grid { flex-direction: column !important; }
          .modes-grid { grid-template-columns: 1fr !important; }
          .emp-grid { grid-template-columns: repeat(2, 1fr) !important; }
          .feat-grid { grid-template-columns: 1fr !important; }
          .stats-bar { gap: 32px !important; }
          .footer-inner { flex-direction: column !important; gap: 16px !important; text-align: center; }
        }
        @media (max-width: 480px) {
          .emp-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>

      {/* NAV */}
      <nav style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "18px 32px", maxWidth: 1200, margin: "0 auto", position: "relative", zIndex: 20,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: "linear-gradient(135deg, #635bff, #7c3aed)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 900, fontSize: 14, color: "#fff",
          }}>FA</div>
          <span style={{ fontWeight: 800, fontSize: 20, letterSpacing: "-0.02em" }}>ForgeAI</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="land-btn land-btn-ghost" onClick={() => router.push("/login")}
            style={{ padding: "10px 24px", fontSize: 14 }}>Sign In</button>
          <button className="land-btn land-btn-primary" onClick={() => router.push("/register")}
            style={{ padding: "10px 24px", fontSize: 14 }}>Get Started Free</button>
        </div>
      </nav>

      {/* HERO */}
      <section style={{ position: "relative", padding: "80px 24px 100px", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{
          position: "absolute", top: -100, left: "50%", transform: "translateX(-50%)",
          width: 800, height: 500, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(99,91,255,0.12) 0%, rgba(124,58,237,0.05) 40%, transparent 70%)",
          animation: "heroGlow 8s ease-in-out infinite", pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", top: 60, right: -100, width: 300, height: 300, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(11,191,140,0.06) 0%, transparent 70%)",
          animation: "heroGlow 10s ease-in-out infinite 2s", pointerEvents: "none",
        }} />

        <div style={{ textAlign: "center", position: "relative", zIndex: 2, animation: "fadeUp 0.8s ease-out" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "7px 18px", borderRadius: 24,
            background: "rgba(99,91,255,0.08)", border: "1px solid rgba(99,91,255,0.18)",
            fontSize: 13, fontWeight: 600, color: "#a5a0ff", marginBottom: 28,
          }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#0bbf8c", boxShadow: "0 0 8px #0bbf8c" }} />
            AI Agents That Work As Your Team
          </div>

          <h1 style={{
            fontSize: "clamp(40px, 6vw, 72px)", fontWeight: 900, lineHeight: 1.05,
            letterSpacing: "-0.04em", marginBottom: 24,
          }}>
            <span style={{
              background: "linear-gradient(135deg, #fff 0%, rgba(255,255,255,0.75) 100%)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            } as React.CSSProperties}>
              Your AI
            </span>
            <br />
            <span style={{
              background: "linear-gradient(135deg, #635bff 0%, #a78bfa 40%, #06b6d4 100%)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
              backgroundSize: "200% 100%", animation: "shimmer 4s linear infinite",
            } as React.CSSProperties}>
              Software Company
            </span>
          </h1>

          <p style={{
            fontSize: 19, lineHeight: 1.7, color: "rgba(255,255,255,0.5)",
            maxWidth: 600, margin: "0 auto 40px",
          }}>
            Six AI employees that analyze, design, code, and document your product.
            Run them as a pipeline for one-shot builds, or chat with them as your persistent team.
          </p>

          <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="land-btn land-btn-primary" onClick={() => router.push("/register")}
              style={{ fontSize: 17, padding: "16px 36px" }}>
              Hire Your Team <span style={{ fontSize: 20 }}>&rarr;</span>
            </button>
            <button className="land-btn land-btn-ghost" onClick={() => {
              document.getElementById("two-modes")?.scrollIntoView({ behavior: "smooth" });
            }}>See How It Works</button>
          </div>
        </div>
      </section>

      {/* LIVE DEMO STRIP */}
      <section style={{ padding: "0 24px 80px", maxWidth: 900, margin: "0 auto" }}>
        <div style={{
          background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)",
          borderRadius: 20, padding: "28px 32px", position: "relative", overflow: "hidden",
        }}>
          <div style={{
            position: "absolute", top: 0, left: 0, right: 0, height: 2,
            background: "linear-gradient(90deg, #635bff, #0bbf8c, #635bff)",
            backgroundSize: "200% 100%", animation: "shimmer 3s linear infinite",
          }} />
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", color: "rgba(255,255,255,0.3)", marginBottom: 14, textTransform: "uppercase" as const }}>
            LIVE DEMO
          </div>

          {/* Typed input */}
          <div style={{
            background: "rgba(255,255,255,0.04)", borderRadius: 12, padding: "14px 18px",
            border: "1px solid rgba(99,91,255,0.15)", marginBottom: 20, minHeight: 48,
            display: "flex", alignItems: "center",
          }}>
            <span style={{ color: "rgba(255,255,255,0.6)", fontSize: 15, fontFamily: "monospace" }}>
              {typed}
              <span style={{ animation: "typeCursor 1s step-end infinite", color: "#635bff", fontWeight: 700 }}>|</span>
            </span>
          </div>

          {/* Agent flow */}
          <div style={{ display: "flex", alignItems: "center", gap: 0, justifyContent: "center", flexWrap: "wrap" }}>
            {PIPELINE_AGENTS.map((a, i) => {
              const isActive = i <= activeAgent;
              const isCurrent = i === activeAgent;
              return (
                <div key={a.label} style={{ display: "flex", alignItems: "center" }}>
                  <div style={{
                    display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
                    opacity: isActive ? 1 : 0.25, transition: "all 0.4s ease",
                    transform: isCurrent ? "scale(1.15)" : "scale(1)",
                  }}>
                    <div style={{
                      width: 44, height: 44, borderRadius: 12,
                      background: isActive ? `${a.color}20` : "rgba(255,255,255,0.03)",
                      border: `2px solid ${isActive ? a.color : "rgba(255,255,255,0.06)"}`,
                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
                      boxShadow: isCurrent ? `0 0 20px ${a.color}40` : "none",
                      transition: "all 0.4s ease",
                    }}>
                      {a.icon}
                    </div>
                    <span style={{ fontSize: 9, fontWeight: 700, color: isActive ? a.color : "rgba(255,255,255,0.2)", transition: "color 0.4s" }}>
                      {a.label.split(" ")[0]}
                    </span>
                  </div>
                  {i < PIPELINE_AGENTS.length - 1 && (
                    <div style={{
                      width: 32, height: 2, margin: "0 4px", marginBottom: 18,
                      background: i < activeAgent ? `linear-gradient(90deg, ${PIPELINE_AGENTS[i].color}, ${PIPELINE_AGENTS[i+1].color})` : "rgba(255,255,255,0.06)",
                      borderRadius: 1, transition: "background 0.4s ease",
                    }} />
                  )}
                </div>
              );
            })}
          </div>

          {/* Output preview */}
          {activeAgent >= PIPELINE_AGENTS.length - 1 && (
            <div style={{
              marginTop: 16, display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap",
              animation: "fadeUp 0.4s ease-out",
            }}>
              {["Source Code", "Architecture Docs", "Pitch Deck", "API Specs"].map(item => (
                <span key={item} style={{
                  padding: "5px 14px", borderRadius: 8, fontSize: 11, fontWeight: 700,
                  background: "rgba(11,191,140,0.1)", color: "#0bbf8c",
                  border: "1px solid rgba(11,191,140,0.2)",
                }}>{item}</span>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* TWO MODES */}
      <section id="two-modes" style={{ padding: "80px 24px", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div className="section-label" style={{ color: "#635bff" }}>Two Ways to Work</div>
          <h2 className="section-title" style={{ color: "#fff" }}>
            Pipeline builds. Employees persist.
          </h2>
          <p style={{ color: "rgba(255,255,255,0.4)", fontSize: 16, marginTop: 14, maxWidth: 520, margin: "14px auto 0" }}>
            Choose one-shot project generation or ongoing collaboration with AI teammates who learn and grow.
          </p>
        </div>

        <div className="modes-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* Pipeline Mode */}
          <div style={{
            background: "rgba(99,91,255,0.04)", border: "1.5px solid rgba(99,91,255,0.15)",
            borderRadius: 24, padding: "36px 32px", position: "relative", overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", top: -60, right: -60, width: 160, height: 160, borderRadius: "50%",
              background: "radial-gradient(circle, rgba(99,91,255,0.08) 0%, transparent 70%)", pointerEvents: "none",
            }} />
            <div style={{
              display: "inline-flex", padding: "5px 12px", borderRadius: 8,
              background: "rgba(99,91,255,0.1)", border: "1px solid rgba(99,91,255,0.2)",
              fontSize: 11, fontWeight: 800, color: "#a5a0ff", letterSpacing: "0.08em",
              textTransform: "uppercase" as const, marginBottom: 16,
            }}>Pipeline</div>
            <h3 style={{ fontSize: 24, fontWeight: 800, marginBottom: 10, color: "#fff", letterSpacing: "-0.02em" }}>
              One idea in, full product out
            </h3>
            <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.45)", marginBottom: 24 }}>
              Describe what you want to build. Six agents work sequentially — CEO analyzes, BA defines requirements, Researcher investigates,
              Architect designs, Engineer codes, Presenter delivers. You get source code, docs, and a pitch deck.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 24 }}>
              {PIPELINE_AGENTS.map((a) => (
                <div key={a.label} style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
                  borderRadius: 10, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)",
                }}>
                  <span style={{ fontSize: 14 }}>{a.icon}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: a.color }}>{a.label.split(" ")[0]}</span>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {["5 pipeline routes", "Auto-pilot mode", "GitHub push", "PPTX export"].map(f => (
                <span key={f} style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ color: "#635bff" }}>&#10003;</span> {f}
                </span>
              ))}
            </div>
          </div>

          {/* Team Mode */}
          <div style={{
            background: "rgba(11,191,140,0.03)", border: "1.5px solid rgba(11,191,140,0.12)",
            borderRadius: 24, padding: "36px 32px", position: "relative", overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", top: -60, right: -60, width: 160, height: 160, borderRadius: "50%",
              background: "radial-gradient(circle, rgba(11,191,140,0.06) 0%, transparent 70%)", pointerEvents: "none",
            }} />
            <div style={{
              display: "inline-flex", padding: "5px 12px", borderRadius: 8,
              background: "rgba(11,191,140,0.1)", border: "1px solid rgba(11,191,140,0.2)",
              fontSize: 11, fontWeight: 800, color: "#0bbf8c", letterSpacing: "0.08em",
              textTransform: "uppercase" as const, marginBottom: 16,
            }}>Employees</div>
            <h3 style={{ fontSize: 24, fontWeight: 800, marginBottom: 10, color: "#fff", letterSpacing: "-0.02em" }}>
              AI teammates that remember
            </h3>
            <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.45)", marginBottom: 24 }}>
              Chat with persistent AI employees who retain context across conversations, learn new skills over time,
              and collaborate with each other through delegation. They work while you&apos;re away.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 24 }}>
              {EMPLOYEES.map((e) => (
                <div key={e.name} style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
                  borderRadius: 10, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)",
                }}>
                  <span style={{ fontSize: 14 }}>{e.icon}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: e.color }}>{e.name}</span>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {["Long-term memory", "Skill learning", "Team delegation", "Activity feed"].map(f => (
                <span key={f} style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ color: "#0bbf8c" }}>&#10003;</span> {f}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* MEET YOUR TEAM */}
      <section style={{ padding: "80px 24px", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div className="section-label" style={{ color: "#0bbf8c" }}>Meet Your Team</div>
          <h2 className="section-title" style={{ color: "#fff" }}>
            Six specialists, always on call
          </h2>
        </div>

        <div className="emp-grid" style={{
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16,
        }}>
          {EMPLOYEES.map((e) => (
            <div key={e.name} className="emp-card" style={{ borderColor: `${e.color}15` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 14,
                  background: `${e.color}12`, border: `2px solid ${e.color}30`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
                }}>{e.icon}</div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "#fff" }}>{e.name}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: e.color }}>{e.role}</div>
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                {e.skills.map(s => (
                  <span key={s} style={{
                    fontSize: 10, fontWeight: 600, padding: "3px 10px", borderRadius: 6,
                    background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)",
                    color: "rgba(255,255,255,0.45)",
                  }}>{s}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section style={{ padding: "80px 24px", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <div className="section-label" style={{ color: "#635bff" }}>Why ForgeAI</div>
          <h2 className="section-title" style={{ color: "#fff" }}>Built different</h2>
        </div>

        <div className="feat-grid" style={{
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20,
        }}>
          {[
            { icon: "🧠", title: "Memory That Lasts", desc: "Employees remember past conversations, learn preferences, and build context over time. No more repeating yourself.", color: "#a78bfa" },
            { icon: "🔄", title: "Team Delegation", desc: "Employees assign tasks to each other. Ask Arc to design a system — they'll delegate security review to Sentinel automatically.", color: "#0bbf8c" },
            { icon: "⚡", title: "Multi-Model Power", desc: "Powered by DeepSeek, NVIDIA Nemotron, and more. Automatic fallback chains ensure every request succeeds.", color: "#f5a623" },
            { icon: "📦", title: "Production Output", desc: "Downloadable source code, architecture docs, PPTX decks, and DOCX reports — all generated and ready to use.", color: "#06b6d4" },
            { icon: "🛡️", title: "Built-in Security", desc: "Every code output is scanned for vulnerabilities. Fail-closed tool permissions ensure employees only access what they need.", color: "#ef4444" },
            { icon: "🔗", title: "GitHub Integration", desc: "Push generated code to a repo with one click. Branch creation, commit messages, and PR descriptions — all automatic.", color: "#635bff" },
          ].map((f) => (
            <div key={f.title} className="feat-card" style={{ "--fc-color": f.color } as React.CSSProperties}>
              <div style={{ fontSize: 32, marginBottom: 16 }}>{f.icon}</div>
              <h4 style={{ fontSize: 18, fontWeight: 800, marginBottom: 8, color: "#fff" }}>{f.title}</h4>
              <p style={{ fontSize: 13, lineHeight: 1.7, color: "rgba(255,255,255,0.4)", margin: 0 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* STATS */}
      <section style={{ padding: "56px 24px", maxWidth: 1000, margin: "0 auto" }}>
        <div className="stats-bar" style={{
          display: "flex", justifyContent: "center", gap: 80, flexWrap: "wrap",
          padding: "48px 0", borderTop: "1px solid rgba(255,255,255,0.06)", borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}>
          {[
            { value: "6", label: "AI Employees", color: "#635bff" },
            { value: "18", label: "Default Skills", color: "#0bbf8c" },
            { value: "5+", label: "LLM Providers", color: "#f5a623" },
            { value: "<5m", label: "To First Build", color: "#06b6d4" },
          ].map((s) => (
            <div key={s.label} style={{ textAlign: "center" }}>
              <div style={{
                fontSize: 42, fontWeight: 900, letterSpacing: "-0.03em", color: s.color,
              }}>{s.value}</div>
              <div style={{ fontSize: 13, color: "rgba(255,255,255,0.35)", fontWeight: 600, marginTop: 4 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* FINAL CTA */}
      <section style={{ padding: "100px 24px 80px", textAlign: "center", position: "relative" }}>
        <div style={{
          position: "absolute", bottom: 0, left: "50%", transform: "translateX(-50%)",
          width: 600, height: 400, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(99,91,255,0.08) 0%, transparent 60%)",
          pointerEvents: "none",
        }} />
        <div style={{ position: "relative", zIndex: 2 }}>
          <h2 style={{
            fontSize: "clamp(32px, 5vw, 52px)", fontWeight: 900,
            letterSpacing: "-0.03em", marginBottom: 16,
            background: "linear-gradient(135deg, #fff 0%, rgba(255,255,255,0.7) 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          } as React.CSSProperties}>
            Ready to hire your AI team?
          </h2>
          <p style={{
            fontSize: 17, color: "rgba(255,255,255,0.4)", marginBottom: 36,
            maxWidth: 460, margin: "0 auto 36px", lineHeight: 1.6,
          }}>
            Start with the pipeline for instant builds, or go straight to chatting with your persistent AI employees.
          </p>
          <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="land-btn land-btn-primary" onClick={() => router.push("/register")}
              style={{ fontSize: 18, padding: "18px 44px" }}>
              Get Started Free <span style={{ fontSize: 22 }}>&rarr;</span>
            </button>
            <button className="land-btn land-btn-secondary" onClick={() => router.push("/login")}
              style={{ fontSize: 16, padding: "16px 32px" }}>
              Sign In
            </button>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{
        padding: "28px 32px", borderTop: "1px solid rgba(255,255,255,0.06)",
        maxWidth: 1200, margin: "0 auto",
      }}>
        <div className="footer-inner" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 24, height: 24, borderRadius: 6,
              background: "linear-gradient(135deg, #635bff, #7c3aed)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontWeight: 900, fontSize: 9, color: "#fff",
            }}>FA</div>
            <span style={{ fontWeight: 700, fontSize: 14, color: "rgba(255,255,255,0.4)" }}>ForgeAI</span>
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.2)" }}>
            Your AI software company. Pipeline builds &bull; Persistent employees &bull; Built for builders.
          </div>
        </div>
      </footer>
    </div>
  );
}
