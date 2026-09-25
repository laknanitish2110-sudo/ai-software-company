"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/Toast";
import {
  getPlans,
  getSubscription,
  getUsage,
  createCheckout,
  createPortalSession,
  PlanInfo,
  SubscriptionInfo,
  UsageSummary,
} from "@/lib/api";

export default function SettingsPageWrapper() {
  return (
    <Suspense fallback={<SettingsSkeleton />}>
      <SettingsPage />
    </Suspense>
  );
}

function SettingsSkeleton() {
  return (
    <div className="settings-container" style={{ maxWidth: 880, margin: "0 auto", padding: "32px 20px" }}>
      <div className="skeleton skeleton-text" style={{ width: 120, height: 28, marginBottom: 8 }} />
      <div className="skeleton skeleton-text" style={{ width: 260, height: 16, marginBottom: 28 }} />
      <div style={{ display: "flex", gap: 2, marginBottom: 28 }}>
        {[80, 80, 80].map((w, i) => (
          <div key={i} className="skeleton" style={{ width: w, height: 38, borderRadius: 8 }} />
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        {[0, 1, 2].map((i) => (
          <div key={i} className="skeleton-card" style={{ height: 240 }} />
        ))}
      </div>
    </div>
  );
}

const TAB_META = {
  billing: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>
      </svg>
    ),
    label: "Billing",
  },
  profile: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>
      </svg>
    ),
    label: "Profile",
  },
  usage: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
      </svg>
    ),
    label: "Usage",
  },
} as const;

function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const [tab, setTab] = useState<"billing" | "profile" | "usage">("billing");
  const [plans, setPlans] = useState<Record<string, PlanInfo>>({});
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [stripeConfigured, setStripeConfigured] = useState(false);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [loadingData, setLoadingData] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;
    setLoadingData(true);
    Promise.all([
      getPlans().then((d) => { setPlans(d.plans); setStripeConfigured(d.stripe_configured); }),
      getSubscription().then(setSubscription),
      getUsage().then(setUsage),
    ])
      .catch(() => toast("warning", "Error", "Could not load billing data"))
      .finally(() => setLoadingData(false));
  }, [user]);

  useEffect(() => {
    const billing = searchParams.get("billing");
    if (billing === "success") {
      toast("success", "Subscribed!", "Your plan has been upgraded.");
      getSubscription().then(setSubscription);
    } else if (billing === "cancelled") {
      toast("info", "Cancelled", "Checkout was cancelled.");
    }
  }, [searchParams]);

  if (authLoading || !user) return null;

  const handleUpgrade = async (plan: string) => {
    setUpgrading(plan);
    try {
      const { url } = await createCheckout(plan);
      window.location.href = url;
    } catch (err: unknown) {
      toast("warning", "Error", err instanceof Error ? err.message : "Could not start checkout");
      setUpgrading(null);
    }
  };

  const handleManage = async () => {
    try {
      const { url } = await createPortalSession();
      window.location.href = url;
    } catch {
      toast("warning", "Error", "Could not open billing portal");
    }
  };

  const currentPlan = subscription?.plan || "free";

  const PLAN_ICONS: Record<string, string> = {
    free: "🌱", starter: "🚀", pro: "⚡", team: "🏢",
  };

  const PLAN_GRADIENTS: Record<string, string> = {
    free: "linear-gradient(135deg, #e8ecf4, #f4f6fb)",
    starter: "linear-gradient(135deg, rgba(99,91,255,0.08), rgba(124,58,237,0.04))",
    pro: "linear-gradient(135deg, rgba(99,91,255,0.12), rgba(124,58,237,0.08))",
    team: "linear-gradient(135deg, rgba(11,191,140,0.12), rgba(6,182,212,0.08))",
  };

  return (
    <div className="settings-container" style={{ maxWidth: 880, margin: "0 auto", padding: "32px 20px" }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: "linear-gradient(135deg, rgba(99,91,255,0.1), rgba(124,58,237,0.1))",
            border: "1px solid rgba(99,91,255,0.15)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
            </svg>
          </div>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>Settings</h1>
            <p style={{ fontSize: 14, color: "var(--text-secondary)", margin: 0 }}>
              Manage your account, billing, and usage
            </p>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{
        display: "inline-flex", gap: 4, marginBottom: 28,
        padding: 4, borderRadius: 12,
        background: "var(--bg-elevated)", border: "1px solid var(--border)",
      }}>
        {(["billing", "profile", "usage"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: "8px 18px", fontSize: 13, fontWeight: 600,
            border: "none", cursor: "pointer",
            borderRadius: 8,
            display: "flex", alignItems: "center", gap: 6,
            background: tab === t ? "var(--bg-card)" : "transparent",
            color: tab === t ? "var(--accent)" : "var(--text-secondary)",
            boxShadow: tab === t ? "0 1px 3px rgba(0,0,0,0.06)" : "none",
            transition: "all 0.15s",
          }}>
            {TAB_META[t].icon}
            {TAB_META[t].label}
          </button>
        ))}
      </div>

      {tab === "billing" && (
        <div style={{ animation: "fadeIn 0.25s ease-out" }}>
          {/* Current plan banner */}
          <div style={{
            padding: "20px 24px", borderRadius: 16, marginBottom: 24,
            background: "linear-gradient(135deg, rgba(99,91,255,0.08), rgba(124,58,237,0.04))",
            border: "1px solid var(--accent-border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{
                width: 48, height: 48, borderRadius: 14,
                background: "linear-gradient(135deg, var(--accent), #7c3aed)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 22, color: "#fff", boxShadow: "0 4px 14px rgba(99,91,255,0.3)",
              }}>
                {PLAN_ICONS[currentPlan] || "🌱"}
              </div>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>Current plan</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
                  {subscription?.plan_name || "Free"}
                </div>
              </div>
            </div>
            {currentPlan !== "free" && (
              <button onClick={handleManage} style={{
                padding: "9px 18px", borderRadius: 10, fontSize: 13, fontWeight: 600,
                background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-primary)",
                cursor: "pointer", transition: "all 0.15s",
              }}>Manage subscription</button>
            )}
          </div>

          {subscription?.cancel_at_period_end && (
            <div style={{
              padding: "14px 18px", borderRadius: 12, marginBottom: 20,
              background: "rgba(237,95,116,0.06)", border: "1px solid rgba(237,95,116,0.15)",
              fontSize: 13, color: "var(--danger)", display: "flex", alignItems: "center", gap: 10,
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              Your subscription will cancel at the end of the current period
              {subscription.current_period_end && ` (${new Date(subscription.current_period_end).toLocaleDateString()})`}.
            </div>
          )}

          {/* Plan cards — side by side */}
          {loadingData ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton-card" style={{ height: 260, borderRadius: 16 }} />
              ))}
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(Object.keys(plans).length, 3)}, 1fr)`, gap: 16 }}>
              {Object.entries(plans).map(([key, plan]) => {
                const isCurrent = key === currentPlan;
                const isUpgrade = (key === "pro" && currentPlan === "free") || (key === "team" && currentPlan !== "team");
                return (
                  <div key={key} style={{
                    borderRadius: 16, overflow: "hidden",
                    background: "var(--bg-card)",
                    border: isCurrent ? "2px solid var(--accent)" : "1px solid var(--border)",
                    position: "relative",
                    display: "flex", flexDirection: "column",
                    transition: "all 0.2s ease",
                  }}>
                    <div style={{
                      height: 4,
                      background: isCurrent
                        ? "linear-gradient(90deg, var(--accent), #7c3aed)"
                        : PLAN_GRADIENTS[key] || "var(--bg-elevated)",
                    }} />
                    <div style={{ padding: "20px 20px 16px", flex: 1, display: "flex", flexDirection: "column" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 20 }}>{PLAN_ICONS[key] || "📦"}</span>
                          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
                            {plan.name}
                          </div>
                        </div>
                        {isCurrent && (
                          <span style={{
                            padding: "2px 8px", borderRadius: 20,
                            fontSize: 9, fontWeight: 700,
                            background: "var(--accent)", color: "#fff",
                            textTransform: "uppercase", letterSpacing: "0.05em",
                          }}>Current</span>
                        )}
                      </div>
                      <div style={{ marginBottom: 14 }}>
                        <span style={{ fontSize: 28, fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
                          {plan.price_monthly === 0 ? "Free" : `$${plan.price_monthly}`}
                        </span>
                        {plan.price_monthly > 0 && (
                          <span style={{ fontSize: 13, fontWeight: 400, color: "var(--text-muted)", marginLeft: 2 }}>/mo</span>
                        )}
                      </div>
                      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12, marginBottom: 14, flex: 1 }}>
                        {plan.features.map((f, i) => (
                          <div key={i} style={{
                            fontSize: 12, color: "var(--text-secondary)", padding: "4px 0",
                            display: "flex", alignItems: "flex-start", gap: 6,
                          }}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 1 }}>
                              <polyline points="20 6 9 17 4 12"/>
                            </svg>
                            {f}
                          </div>
                        ))}
                      </div>
                      {isCurrent ? (
                        <div style={{
                          padding: "9px 14px", borderRadius: 10, textAlign: "center",
                          fontSize: 12, fontWeight: 600, color: "var(--text-muted)",
                          background: "var(--bg-elevated)", border: "1px solid var(--border)",
                        }}>Active plan</div>
                      ) : isUpgrade ? (
                        <button
                          onClick={() => handleUpgrade(key)}
                          disabled={!!upgrading || !stripeConfigured}
                          style={{
                            width: "100%", padding: "10px 14px", borderRadius: 10,
                            fontSize: 12, fontWeight: 700, border: "none", cursor: "pointer",
                            background: "linear-gradient(135deg, var(--accent), #7c3aed)",
                            color: "#fff", transition: "all 0.15s",
                            opacity: upgrading ? 0.6 : 1,
                            boxShadow: "0 2px 12px rgba(99,91,255,0.25)",
                          }}
                        >
                          {upgrading === key ? "Redirecting..." : !stripeConfigured ? "Coming soon" : `Upgrade to ${plan.name}`}
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {tab === "profile" && (
        <div style={{ animation: "fadeIn 0.25s ease-out" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            {/* Left — Account info */}
            <div style={{
              borderRadius: 16, overflow: "hidden",
              background: "var(--bg-card)", border: "1px solid var(--border)",
              display: "flex", flexDirection: "column",
            }}>
              <div style={{
                padding: "20px 20px 16px",
                background: "linear-gradient(135deg, rgba(99,91,255,0.06), rgba(124,58,237,0.03))",
                borderBottom: "1px solid var(--border)",
                display: "flex", alignItems: "center", gap: 14,
              }}>
                <div style={{
                  width: 52, height: 52, borderRadius: 14,
                  background: "linear-gradient(135deg, var(--accent), #7c3aed)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#fff", fontSize: 19, fontWeight: 700,
                  boxShadow: "0 4px 14px rgba(99,91,255,0.3)",
                }}>
                  {(user.display_name || user.email || "U").slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <div style={{ fontSize: 17, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>
                    {user.display_name || "Your Profile"}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    {user.email}
                  </div>
                </div>
              </div>
              <div style={{ padding: 16, flex: 1 }}>
                <div style={{ display: "grid", gap: 10 }}>
                  {[
                    { label: "Email", value: user.email, icon: "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z M22 6l-10 7L2 6" },
                    { label: "Display name", value: user.display_name || "Not set", icon: "M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2 M12 3a4 4 0 100 8 4 4 0 000-8z" },
                    { label: "Account created", value: new Date(user.created_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }), icon: "M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z" },
                    ...(user.oauth_provider ? [{
                      label: "Sign-in method",
                      value: user.oauth_provider.charAt(0).toUpperCase() + user.oauth_provider.slice(1),
                      icon: "M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4 M10 17l5-5-5-5 M15 12H3",
                    }] : []),
                  ].map((field) => (
                    <div key={field.label} style={{
                      padding: "12px 14px", borderRadius: 10,
                      background: "var(--bg-base)", border: "1px solid var(--border)",
                      display: "flex", alignItems: "center", gap: 12,
                    }}>
                      <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: "var(--accent-bg)", border: "1px solid var(--accent-border)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        flexShrink: 0,
                      }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          {field.icon.split(" M").map((d, i) => (
                            <path key={i} d={i === 0 ? d : `M${d}`} />
                          ))}
                        </svg>
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 1 }}>
                          {field.label}
                        </div>
                        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>
                          {field.value}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right — Account stats & plan info */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Current plan card */}
              <div style={{
                borderRadius: 16, overflow: "hidden",
                background: "var(--bg-card)", border: "1px solid var(--border)",
              }}>
                <div style={{
                  padding: "14px 18px",
                  background: "linear-gradient(135deg, rgba(11,191,140,0.06), rgba(6,182,212,0.03))",
                  borderBottom: "1px solid var(--border)",
                  display: "flex", alignItems: "center", gap: 8,
                }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Plan
                  </span>
                </div>
                <div style={{ padding: 18 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <span style={{ fontSize: 24 }}>{PLAN_ICONS[currentPlan] || "🌱"}</span>
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)" }}>
                        {subscription?.plan_name || "Free"}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                        {subscription?.current_period_end
                          ? `Renews ${new Date(subscription.current_period_end).toLocaleDateString()}`
                          : "No expiry"}
                      </div>
                    </div>
                  </div>
                  {subscription && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      <div style={{ padding: "8px 10px", borderRadius: 8, background: "var(--bg-base)", border: "1px solid var(--border)", textAlign: "center" }}>
                        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--accent)" }}>
                          {subscription.limits.pipeline_runs === -1 ? "∞" : subscription.limits.pipeline_runs}
                        </div>
                        <div style={{ fontSize: 9, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase" }}>Pipelines/mo</div>
                      </div>
                      <div style={{ padding: "8px 10px", borderRadius: 8, background: "var(--bg-base)", border: "1px solid var(--border)", textAlign: "center" }}>
                        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--success)" }}>
                          {subscription.limits.employee_messages === -1 ? "∞" : subscription.limits.employee_messages}
                        </div>
                        <div style={{ fontSize: 9, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase" }}>Messages/mo</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Quick stats */}
              <div style={{
                borderRadius: 16, overflow: "hidden",
                background: "var(--bg-card)", border: "1px solid var(--border)",
                flex: 1,
              }}>
                <div style={{
                  padding: "14px 18px",
                  background: "linear-gradient(135deg, rgba(99,91,255,0.04), transparent)",
                  borderBottom: "1px solid var(--border)",
                  display: "flex", alignItems: "center", gap: 8,
                }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
                  </svg>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Quick Stats
                  </span>
                </div>
                <div style={{ padding: 18 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    {[
                      { label: "Total Tokens", value: usage?.total_tokens?.toLocaleString() || "0", color: "var(--accent)", icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8" },
                      { label: "Input", value: usage?.total_input?.toLocaleString() || "0", color: "#3b82f6", icon: "M12 19V5 M5 12l7-7 7 7" },
                      { label: "Output", value: usage?.total_output?.toLocaleString() || "0", color: "var(--success)", icon: "M12 5v14 M19 12l-7 7-7-7" },
                      { label: "Account Age", value: (() => { const d = Math.floor((Date.now() - new Date(user.created_at).getTime()) / 86400000); return d < 1 ? "Today" : `${d}d`; })(), color: "#f59e0b", icon: "M12 2a10 10 0 0110 10 10 10 0 01-10 10A10 10 0 012 12 10 10 0 0112 2z M12 6v6l4 2" },
                    ].map((s) => (
                      <div key={s.label} style={{
                        padding: "10px 12px", borderRadius: 10,
                        background: "var(--bg-base)", border: "1px solid var(--border)",
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={s.color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            {s.icon.split(" M").map((d, i) => (
                              <path key={i} d={i === 0 ? d : `M${d}`} />
                            ))}
                          </svg>
                          <span style={{ fontSize: 9, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{s.label}</span>
                        </div>
                        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>{s.value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "usage" && (
        <div style={{ animation: "fadeIn 0.25s ease-out" }}>
          {/* Usage summary cards */}
          {loadingData ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 24 }}>
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="skeleton-card" style={{ height: 88, borderRadius: 14 }} />
              ))}
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 24 }}>
              {[
                { label: "Total tokens", value: usage?.total_tokens?.toLocaleString() || "0", icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8", color: "var(--accent)" },
                { label: "Input tokens", value: usage?.total_input?.toLocaleString() || "0", icon: "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M17 8l-5-5-5 5 M12 3v12", color: "#3b82f6" },
                { label: "Output tokens", value: usage?.total_output?.toLocaleString() || "0", icon: "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M7 10l5 5 5-5 M12 15V3", color: "var(--success)" },
                { label: "Period", value: `${usage?.period_days || 30}d`, color: "var(--warning)", icon: "M12 2v4 M12 18v4 M4.93 4.93l2.83 2.83 M16.24 16.24l2.83 2.83 M2 12h4 M18 12h4 M4.93 19.07l2.83-2.83 M16.24 7.76l2.83-2.83" },
              ].map((stat, i) => (
                <div key={i} style={{
                  padding: "16px 18px", borderRadius: 14,
                  background: "var(--bg-card)", border: "1px solid var(--border)",
                  position: "relative", overflow: "hidden",
                }}>
                  <div style={{
                    position: "absolute", top: 0, left: 0, right: 0, height: 3,
                    background: `linear-gradient(90deg, ${stat.color}, ${stat.color}44)`,
                  }} />
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={stat.color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      {stat.icon.split(" M").map((d, j) => (
                        <path key={j} d={j === 0 ? d : `M${d}`} />
                      ))}
                    </svg>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      {stat.label}
                    </div>
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
                    {stat.value}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Usage by type */}
          {usage?.by_type && usage.by_type.length > 0 && (
            <div style={{
              borderRadius: 16, overflow: "hidden",
              background: "var(--bg-card)", border: "1px solid var(--border)",
            }}>
              <div style={{
                padding: "16px 20px", borderBottom: "1px solid var(--border)",
                background: "linear-gradient(135deg, rgba(99,91,255,0.04), transparent)",
                display: "flex", alignItems: "center", gap: 10,
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
                  <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
                </svg>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                  Usage by type
                </h3>
              </div>
              <div style={{ padding: "4px 0" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {["Type", "Count", "Input tokens", "Output tokens"].map((h) => (
                        <th key={h} style={{
                          textAlign: "left", padding: "10px 16px",
                          fontSize: 11, fontWeight: 700, color: "var(--text-muted)",
                          textTransform: "uppercase", letterSpacing: "0.05em",
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {usage.by_type.map((row, i) => (
                      <tr key={i} style={{ borderBottom: i < usage.by_type.length - 1 ? "1px solid var(--border)" : "none" }}>
                        <td style={{ padding: "12px 16px", fontSize: 13, color: "var(--text-primary)", fontWeight: 600 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <div style={{
                              width: 6, height: 6, borderRadius: "50%",
                              background: i === 0 ? "var(--accent)" : i === 1 ? "var(--success)" : "var(--warning)",
                            }} />
                            {row.record_type.replace(/_/g, " ")}
                          </div>
                        </td>
                        <td style={{ padding: "12px 16px", fontSize: 13, color: "var(--text-secondary)", fontFamily: "monospace" }}>
                          {row.count}
                        </td>
                        <td style={{ padding: "12px 16px", fontSize: 13, color: "var(--text-secondary)", fontFamily: "monospace" }}>
                          {(row.total_input || 0).toLocaleString()}
                        </td>
                        <td style={{ padding: "12px 16px", fontSize: 13, color: "var(--text-secondary)", fontFamily: "monospace" }}>
                          {(row.total_output || 0).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {(!usage?.by_type || usage.by_type.length === 0) && !loadingData && (
            <div style={{
              padding: "48px 24px", textAlign: "center", borderRadius: 16,
              background: "var(--bg-card)", border: "1px solid var(--border)",
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: 16, margin: "0 auto 16px",
                background: "var(--bg-elevated)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
                </svg>
              </div>
              <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
                No usage data yet
              </div>
              <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Start a pipeline run or chat with an employee to see usage here.
              </div>
            </div>
          )}

          {/* Plan limits */}
          {subscription && (
            <div style={{
              marginTop: 20, borderRadius: 16, overflow: "hidden",
              background: "var(--bg-card)", border: "1px solid var(--border)",
            }}>
              <div style={{
                padding: "16px 20px", borderBottom: "1px solid var(--border)",
                background: "linear-gradient(135deg, rgba(11,191,140,0.04), transparent)",
                display: "flex", alignItems: "center", gap: 10,
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                  Plan limits ({subscription.plan_name})
                </h3>
              </div>
              <div style={{ padding: 20, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[
                  { label: "Pipeline runs/mo", value: subscription.limits.pipeline_runs === -1 ? "Unlimited" : String(subscription.limits.pipeline_runs) },
                  { label: "Messages/mo", value: subscription.limits.employee_messages === -1 ? "Unlimited" : String(subscription.limits.employee_messages) },
                ].map((limit) => (
                  <div key={limit.label} style={{
                    padding: "12px 14px", borderRadius: 10,
                    background: "var(--bg-base)", border: "1px solid var(--border)",
                  }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                      {limit.label}
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)" }}>
                      {limit.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
