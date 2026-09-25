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
    <Suspense fallback={<div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>Loading...</div>}>
      <SettingsPage />
    </Suspense>
  );
}

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

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;
    Promise.all([
      getPlans().then((d) => { setPlans(d.plans); setStripeConfigured(d.stripe_configured); }),
      getSubscription().then(setSubscription),
      getUsage().then(setUsage),
    ]).catch(() => toast("warning", "Error", "Could not load billing data"));
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

  return (
    <div style={{ maxWidth: 880, margin: "0 auto", padding: "32px 20px" }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
        Settings
      </h1>
      <p style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 28 }}>
        Manage your account, billing, and usage
      </p>

      {/* Tab bar */}
      <div style={{
        display: "flex", gap: 2, marginBottom: 28,
        borderBottom: "1px solid var(--border)", paddingBottom: 0,
      }}>
        {(["billing", "profile", "usage"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: "10px 20px", fontSize: 13, fontWeight: 600,
            border: "none", background: "none", cursor: "pointer",
            color: tab === t ? "var(--accent)" : "var(--text-secondary)",
            borderBottom: tab === t ? "2px solid var(--accent)" : "2px solid transparent",
            transition: "all 0.15s", textTransform: "capitalize",
          }}>{t}</button>
        ))}
      </div>

      {tab === "billing" && (
        <div>
          {/* Current plan banner */}
          <div style={{
            padding: "16px 20px", borderRadius: 12, marginBottom: 24,
            background: "var(--accent-bg)", border: "1px solid var(--accent-border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 2 }}>Current plan</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "var(--accent)" }}>
                {subscription?.plan_name || "Free"}
              </div>
            </div>
            {currentPlan !== "free" && (
              <button onClick={handleManage} style={{
                padding: "8px 16px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                background: "none", border: "1px solid var(--border)", color: "var(--text-primary)",
                cursor: "pointer",
              }}>Manage subscription</button>
            )}
          </div>

          {subscription?.cancel_at_period_end && (
            <div style={{
              padding: "12px 16px", borderRadius: 8, marginBottom: 20,
              background: "rgba(237,95,116,0.06)", border: "1px solid rgba(237,95,116,0.15)",
              fontSize: 13, color: "var(--danger)",
            }}>
              Your subscription will cancel at the end of the current period
              {subscription.current_period_end && ` (${new Date(subscription.current_period_end).toLocaleDateString()})`}.
            </div>
          )}

          {/* Plan cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
            {Object.entries(plans).map(([key, plan]) => {
              const isCurrent = key === currentPlan;
              const isUpgrade = (key === "pro" && currentPlan === "free") || (key === "team" && currentPlan !== "team");
              return (
                <div key={key} style={{
                  padding: 24, borderRadius: 16,
                  background: "var(--bg-card)",
                  border: isCurrent ? "2px solid var(--accent)" : "1px solid var(--border)",
                  position: "relative",
                }}>
                  {isCurrent && (
                    <div style={{
                      position: "absolute", top: -10, left: 20,
                      padding: "2px 10px", borderRadius: 20, fontSize: 10, fontWeight: 700,
                      background: "var(--accent)", color: "#fff",
                    }}>CURRENT</div>
                  )}
                  <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
                    {plan.name}
                  </div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: "var(--text-primary)", marginBottom: 16 }}>
                    {plan.price_monthly === 0 ? "Free" : `$${plan.price_monthly}`}
                    {plan.price_monthly > 0 && (
                      <span style={{ fontSize: 13, fontWeight: 400, color: "var(--text-muted)" }}>/mo</span>
                    )}
                  </div>
                  <ul style={{ listStyle: "none", padding: 0, margin: "0 0 20px 0" }}>
                    {plan.features.map((f, i) => (
                      <li key={i} style={{
                        fontSize: 13, color: "var(--text-secondary)", padding: "4px 0",
                        display: "flex", alignItems: "center", gap: 8,
                      }}>
                        <span style={{ color: "var(--success)", fontSize: 14 }}>✓</span>
                        {f}
                      </li>
                    ))}
                  </ul>
                  {isCurrent ? (
                    <div style={{
                      padding: "8px 16px", borderRadius: 8, textAlign: "center",
                      fontSize: 13, fontWeight: 600, color: "var(--text-muted)",
                      background: "var(--bg-page)",
                    }}>Current plan</div>
                  ) : isUpgrade ? (
                    <button
                      onClick={() => handleUpgrade(key)}
                      disabled={!!upgrading || !stripeConfigured}
                      style={{
                        width: "100%", padding: "10px 16px", borderRadius: 8,
                        fontSize: 13, fontWeight: 700, border: "none", cursor: "pointer",
                        background: "var(--accent)", color: "#fff",
                        opacity: upgrading ? 0.6 : 1,
                      }}
                    >
                      {upgrading === key ? "Redirecting..." : !stripeConfigured ? "Coming soon" : `Upgrade to ${plan.name}`}
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === "profile" && (
        <div style={{
          padding: 24, borderRadius: 16,
          background: "var(--bg-card)", border: "1px solid var(--border)",
        }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", marginBottom: 20 }}>Profile</h3>
          <div style={{ display: "grid", gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                Email
              </label>
              <div style={{
                padding: "10px 14px", borderRadius: 8,
                background: "var(--bg-page)", border: "1px solid var(--border)",
                fontSize: 14, color: "var(--text-primary)",
              }}>{user.email}</div>
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                Display name
              </label>
              <div style={{
                padding: "10px 14px", borderRadius: 8,
                background: "var(--bg-page)", border: "1px solid var(--border)",
                fontSize: 14, color: "var(--text-primary)",
              }}>{user.display_name || "Not set"}</div>
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                Account created
              </label>
              <div style={{
                padding: "10px 14px", borderRadius: 8,
                background: "var(--bg-page)", border: "1px solid var(--border)",
                fontSize: 14, color: "var(--text-primary)",
              }}>{new Date(user.created_at).toLocaleDateString()}</div>
            </div>
            {user.oauth_provider && (
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                  Sign-in method
                </label>
                <div style={{
                  padding: "10px 14px", borderRadius: 8,
                  background: "var(--bg-page)", border: "1px solid var(--border)",
                  fontSize: 14, color: "var(--text-primary)", textTransform: "capitalize",
                }}>{user.oauth_provider}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "usage" && (
        <div>
          {/* Usage summary cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 24 }}>
            {[
              { label: "Total tokens", value: usage?.total_tokens?.toLocaleString() || "0" },
              { label: "Input tokens", value: usage?.total_input?.toLocaleString() || "0" },
              { label: "Output tokens", value: usage?.total_output?.toLocaleString() || "0" },
              { label: "Period", value: `Last ${usage?.period_days || 30} days` },
            ].map((stat, i) => (
              <div key={i} style={{
                padding: "16px 20px", borderRadius: 12,
                background: "var(--bg-card)", border: "1px solid var(--border)",
              }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  {stat.label}
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>

          {/* Usage by type */}
          {usage?.by_type && usage.by_type.length > 0 && (
            <div style={{
              padding: 20, borderRadius: 16,
              background: "var(--bg-card)", border: "1px solid var(--border)",
            }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", marginBottom: 16 }}>
                Usage by type
              </h3>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Type", "Count", "Input tokens", "Output tokens"].map((h) => (
                      <th key={h} style={{
                        textAlign: "left", padding: "8px 12px",
                        fontSize: 11, fontWeight: 700, color: "var(--text-muted)",
                        textTransform: "uppercase", letterSpacing: "0.05em",
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {usage.by_type.map((row, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ padding: "10px 12px", fontSize: 13, color: "var(--text-primary)", fontWeight: 600 }}>
                        {row.record_type.replace(/_/g, " ")}
                      </td>
                      <td style={{ padding: "10px 12px", fontSize: 13, color: "var(--text-secondary)" }}>
                        {row.count}
                      </td>
                      <td style={{ padding: "10px 12px", fontSize: 13, color: "var(--text-secondary)" }}>
                        {(row.total_input || 0).toLocaleString()}
                      </td>
                      <td style={{ padding: "10px 12px", fontSize: 13, color: "var(--text-secondary)" }}>
                        {(row.total_output || 0).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {(!usage?.by_type || usage.by_type.length === 0) && (
            <div style={{
              padding: 40, textAlign: "center", borderRadius: 16,
              background: "var(--bg-card)", border: "1px solid var(--border)",
            }}>
              <div style={{ fontSize: 14, color: "var(--text-muted)" }}>
                No usage data yet. Start a pipeline run or chat with an employee.
              </div>
            </div>
          )}

          {/* Plan limits */}
          {subscription && (
            <div style={{
              marginTop: 20, padding: 20, borderRadius: 16,
              background: "var(--bg-card)", border: "1px solid var(--border)",
            }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", marginBottom: 12 }}>
                Plan limits ({subscription.plan_name})
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                  Pipeline runs/mo: <strong style={{ color: "var(--text-primary)" }}>
                    {subscription.limits.pipeline_runs === -1 ? "Unlimited" : subscription.limits.pipeline_runs}
                  </strong>
                </div>
                <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                  Messages/mo: <strong style={{ color: "var(--text-primary)" }}>
                    {subscription.limits.employee_messages === -1 ? "Unlimited" : subscription.limits.employee_messages}
                  </strong>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
