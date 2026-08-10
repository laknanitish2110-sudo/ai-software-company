"use client";

import { use } from "react";
import Dashboard from "@/components/Dashboard";

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <Dashboard projectId={id} />;
}
