"use client";

import { ToastProvider } from "./Toast";
import { AuthProvider } from "@/contexts/AuthContext";
import ErrorBoundary from "./ErrorBoundary";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AuthProvider>{children}</AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
