"use client";

import { useAuth } from "@/contexts/AuthContext";

export default function UserMenu() {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <div className="flex items-center justify-end gap-3 px-4 py-2 border-b border-[var(--border)] bg-[var(--bg-card)]">
      {user.avatar_url && (
        <img
          src={user.avatar_url}
          alt=""
          style={{ width: 22, height: 22, borderRadius: "50%" }}
        />
      )}
      <span className="text-xs text-[var(--text-muted)]">{user.display_name || user.email}</span>
      <button
        onClick={logout}
        className="text-xs text-[var(--text-secondary)] hover:text-[var(--danger)] transition-colors cursor-pointer"
      >
        Sign out
      </button>
    </div>
  );
}
