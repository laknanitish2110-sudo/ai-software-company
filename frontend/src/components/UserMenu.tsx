"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useState, useRef, useEffect } from "react";

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

  if (!user) return null;

  const NAV = [
    { href: "/", label: "Home" },
    { href: "/employees", label: "Team" },
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

      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }} ref={menuRef}>
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
