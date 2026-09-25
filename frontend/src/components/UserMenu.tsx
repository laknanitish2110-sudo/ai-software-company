"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useState, useRef, useEffect, useCallback } from "react";
import { getActivityFeed, markActivitySeen, type ActivityItem } from "@/lib/api";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const { theme, resolved, setTheme } = useTheme();
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<ActivityItem[]>([]);
  const [unseenCount, setUnseenCount] = useState(0);
  const notifRef = useRef<HTMLDivElement>(null);

  const loadNotifs = useCallback(async () => {
    try {
      const data = await getActivityFeed(10, false);
      setNotifications(data.activities);
      setUnseenCount(data.unseen_count);
    } catch {}
  }, []);

  useEffect(() => {
    if (!user) return;
    loadNotifs();
    const interval = setInterval(loadNotifs, 15000);
    return () => clearInterval(interval);
  }, [user, loadNotifs]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  if (!user) return null;

  const NAV = [
    { href: "/", label: "Home" },
    { href: "/employees", label: "Team" },
    { href: "/goals", label: "Goals" },
    { href: "/analytics", label: "Analytics" },
    { href: "/settings", label: "Settings" },
  ];

  const initials = (user.display_name || user.email || "U").slice(0, 2).toUpperCase();

  return (
    <nav style={{
      display: "flex", alignItems: "center", height: 52,
      padding: "0 20px", borderBottom: "1px solid var(--border)",
      background: "var(--bg-card)", gap: 8,
    }}>
      <Link href="/" style={{
        display: "flex", alignItems: "center", gap: 8,
        textDecoration: "none", marginRight: 24, flexShrink: 0,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background: "linear-gradient(135deg, #635bff, #7c3aed)",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontSize: 12, fontWeight: 800,
        }}>FA</div>
        <span style={{
          fontSize: 15, fontWeight: 700, color: "var(--text-primary)",
          letterSpacing: "-0.02em",
        }}>ForgeAI</span>
      </Link>

      <div style={{ display: "flex", gap: 2 }}>
        {NAV.map((n) => {
          const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
          return (
            <Link key={n.href} href={n.href} style={{
              padding: "6px 14px", borderRadius: 8, fontSize: 13, fontWeight: 500,
              textDecoration: "none", transition: "all 0.15s",
              background: active ? "var(--accent-bg)" : "transparent",
              color: active ? "var(--accent)" : "var(--text-secondary)",
            }}>{n.label}</Link>
          );
        })}
      </div>

      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }} ref={menuRef}>
        {/* Notification bell */}
        <div style={{ position: "relative" }} ref={notifRef}>
          <button
            onClick={async () => {
              setNotifOpen(!notifOpen);
              if (!notifOpen && unseenCount > 0) {
                try { await markActivitySeen(); setUnseenCount(0); } catch {}
              }
            }}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 32, height: 32, borderRadius: 8, border: "1px solid var(--border)",
              background: "transparent", cursor: "pointer", color: "var(--text-muted)",
              transition: "all 0.15s", position: "relative",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent-border)"; e.currentTarget.style.color = "var(--accent)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/>
            </svg>
            {unseenCount > 0 && (
              <span style={{
                position: "absolute", top: -4, right: -4,
                width: 16, height: 16, borderRadius: "50%",
                background: "var(--danger)", color: "#fff",
                fontSize: 9, fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>{unseenCount > 9 ? "9+" : unseenCount}</span>
            )}
          </button>
          {notifOpen && (
            <div style={{
              position: "absolute", top: 40, right: 0,
              width: 300, maxHeight: 360, borderRadius: 12, padding: 4,
              background: "var(--bg-card)", border: "1px solid var(--border)",
              boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
              zIndex: 200, overflowY: "auto", animation: "fadeIn 0.15s ease-out",
            }}>
              <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)", marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>Notifications</span>
              </div>
              {notifications.length === 0 ? (
                <div style={{ padding: "20px 12px", textAlign: "center", fontSize: 12, color: "var(--text-muted)" }}>
                  No notifications yet
                </div>
              ) : notifications.map((n) => {
                const icons: Record<string, string> = {
                  delegation_completed: "v", session_completed: "o", skill_learned: "*",
                  scheduled_task_completed: "⏰", memory_created: "🧠",
                };
                const colors: Record<string, string> = {
                  delegation_completed: "var(--success)", session_completed: "var(--accent)", skill_learned: "var(--warning)",
                  scheduled_task_completed: "var(--info)", memory_created: "#8b5cf6",
                };
                return (
                  <div key={n.id} style={{
                    padding: "8px 12px", borderRadius: 8, marginBottom: 2,
                    display: "flex", gap: 8, alignItems: "flex-start",
                    background: n.seen ? "transparent" : "var(--accent-bg)",
                  }}>
                    <span style={{ fontSize: 12, color: colors[n.event_type] || "var(--text-muted)", flexShrink: 0, marginTop: 1 }}>
                      {icons[n.event_type] || "-"}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{n.title}</div>
                      {n.detail && (
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {n.detail.length > 80 ? n.detail.slice(0, 80) + "..." : n.detail}
                        </div>
                      )}
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                        {new Date(n.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <button
          onClick={() => setTheme(resolved === "dark" ? "light" : "dark")}
          title={`Switch to ${resolved === "dark" ? "light" : "dark"} mode`}
          style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            width: 32, height: 32, borderRadius: 8, border: "1px solid var(--border)",
            background: "transparent", cursor: "pointer", color: "var(--text-muted)",
            transition: "all 0.15s",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent-border)"; e.currentTarget.style.color = "var(--accent)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}
        >
          {resolved === "dark" ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          )}
        </button>
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          style={{
            display: "flex", alignItems: "center", gap: 8,
            background: "none", border: "1px solid var(--border)", borderRadius: 24,
            padding: "4px 12px 4px 4px", cursor: "pointer", transition: "border-color 0.15s",
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = "var(--accent-border)"}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = "var(--border)"}
        >
          {user.avatar_url ? (
            <img src={user.avatar_url} alt="" style={{ width: 26, height: 26, borderRadius: "50%" }} />
          ) : (
            <div style={{
              width: 26, height: 26, borderRadius: "50%",
              background: "var(--accent-bg)", color: "var(--accent)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 10, fontWeight: 700,
            }}>{initials}</div>
          )}
          <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 500, maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {user.display_name || user.email}
          </span>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ color: "var(--text-muted)", transition: "transform 0.15s", transform: menuOpen ? "rotate(180deg)" : "none" }}>
            <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        {menuOpen && (
          <div style={{
            position: "absolute", top: 48, right: 20,
            width: 180, borderRadius: 12, padding: 4,
            background: "var(--bg-card)", border: "1px solid var(--border)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.1), 0 2px 8px rgba(0,0,0,0.05)",
            zIndex: 100, animation: "fadeIn 0.15s ease-out",
          }}>
            <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)", marginBottom: 4 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                {user.display_name || "User"}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user.email}
              </div>
            </div>
            <button
              onClick={() => { setMenuOpen(false); logout(); }}
              style={{
                width: "100%", textAlign: "left", padding: "8px 12px",
                borderRadius: 8, border: "none", background: "none",
                fontSize: 12, color: "var(--danger)", cursor: "pointer",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = "rgba(237,95,116,0.06)"}
              onMouseLeave={(e) => e.currentTarget.style.background = "none"}
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
