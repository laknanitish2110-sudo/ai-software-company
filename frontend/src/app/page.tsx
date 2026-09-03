"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import StartProject from "@/components/StartProject";
import AuthGuard from "@/components/AuthGuard";
import { useToast } from "@/components/Toast";
import { createProject, getProjects, getDemoStatus, loadDemoCache } from "@/lib/api";

interface RecentProject {
  id: string;
  problem_statement: string;
  status: string;
}

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [recentProjects, setRecentProjects] = useState<RecentProject[]>([]);
  const [hasDemo, setHasDemo] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    getProjects()
      .then((projects) => {
        const recent = projects
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          .slice(0, 3);
        setRecentProjects(recent);
      })
      .catch(() => {
        toast("warning", "Backend offline", "Could not load recent projects. Is the backend running?");
      });

    getDemoStatus()
      .then((s) => setHasDemo(s.has_demo))
      .catch(() => {});
  }, []);

  async function handleStart(problem: string, autoApprove: boolean = false, domain?: string | null) {
    setLoading(true);
    try {
      const project = await createProject(problem, autoApprove, domain);
      localStorage.setItem("lastProjectId", project.id);
      router.push(`/project/${project.id}`);
    } catch {
      toast("error", "Failed to start project", "Could not connect to the backend. Check deployment status.");
      setLoading(false);
    }
  }

  async function handleLoadDemo() {
    setLoading(true);
    try {
      const data = await loadDemoCache();
      if (data?.project) {
        router.push(`/project/${data.project.id}`);
      } else {
        toast("warning", "No demo found", "Run a successful pipeline first, then save it as a demo.");
      }
    } catch {
      toast("error", "Demo load failed", "Could not load the demo cache from the backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthGuard>
      <StartProject
        onStart={handleStart}
        loading={loading}
        recentProjects={recentProjects}
        hasDemo={hasDemo}
        onLoadDemo={handleLoadDemo}
      />
    </AuthGuard>
  );
}
