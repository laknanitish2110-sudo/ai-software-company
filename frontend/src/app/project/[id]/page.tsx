"use client";

import { use } from "react";
import Dashboard from "@/components/Dashboard";
import AuthGuard from "@/components/AuthGuard";

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <AuthGuard>
      <Dashboard projectId={id} />
    </AuthGuard>
  );
}
