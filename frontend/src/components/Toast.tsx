"use client";

import { useState, useEffect, useCallback, createContext, useContext } from "react";

type ToastType = "error" | "warning" | "success" | "info";

interface Toast {
  id: number;
  type: ToastType;
  title: string;
  message?: string;
  duration: number;
}

interface ToastContextValue {
  toast: (type: ToastType, title: string, message?: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue>({
  toast: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback(
    (type: ToastType, title: string, message?: string, duration = 5000) => {
      const id = ++nextId;
      setToasts((prev) => [...prev, { id, type, title, message, duration }]);
    },
    []
  );

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      <div
        style={{
          position: "fixed",
          bottom: 20,
          right: 20,
          zIndex: 100,
          display: "flex",
          flexDirection: "column-reverse",
          gap: 8,
          maxWidth: 400,
        }}
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

const STYLES: Record<ToastType, { bg: string; border: string; icon: string; color: string }> = {
  error: { bg: "rgba(237,95,116,0.08)", border: "rgba(237,95,116,0.25)", icon: "✕", color: "#ed5f74" },
  warning: { bg: "rgba(245,166,35,0.08)", border: "rgba(245,166,35,0.25)", icon: "!", color: "#f5a623" },
  success: { bg: "rgba(11,191,140,0.08)", border: "rgba(11,191,140,0.25)", icon: "✓", color: "#0bbf8c" },
  info: { bg: "rgba(99,91,255,0.08)", border: "rgba(99,91,255,0.25)", icon: "i", color: "#635bff" },
};

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  const [exiting, setExiting] = useState(false);
  const s = STYLES[toast.type];

  useEffect(() => {
    const timer = setTimeout(() => setExiting(true), toast.duration - 300);
    const remove = setTimeout(() => onDismiss(toast.id), toast.duration);
    return () => {
      clearTimeout(timer);
      clearTimeout(remove);
    };
  }, [toast, onDismiss]);

  return (
    <div
      className={exiting ? "animate-fade-out" : "animate-slide-in"}
      style={{
        background: "var(--bg-card)",
        border: `1px solid ${s.border}`,
        borderLeft: `3px solid ${s.color}`,
        borderRadius: 12,
        padding: "12px 16px",
        boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
        display: "flex",
        alignItems: "flex-start",
        gap: 10,
        cursor: "pointer",
      }}
      onClick={() => {
        setExiting(true);
        setTimeout(() => onDismiss(toast.id), 200);
      }}
    >
      <span
        style={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          background: s.bg,
          color: s.color,
          fontSize: 11,
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        {s.icon}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
          {toast.title}
        </div>
        {toast.message && (
          <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2, lineHeight: 1.4 }}>
            {toast.message}
          </div>
        )}
      </div>
    </div>
  );
}
