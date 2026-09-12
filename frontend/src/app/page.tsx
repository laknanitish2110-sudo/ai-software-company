"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import LandingPage from "@/components/LandingPage";
import StartProject from "@/components/StartProject";
import { useToast } from "@/components/Toast";
import { createProject, getProjects, getDemoStatus, loadDemoCache } from "@/lib/api";

interface RecentProject {
  id: string;
  problem_statement: string;
  status: string;
}

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(false);
  const [recentProjects, setRecentProjects] = useState<RecentProject[]>([]);
  const [hasDemo, setHasDemo] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    if (!user) return;
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
  }, [user]);

  async function handleStart(problem: string, autoApprove: boolean = false, domain?: string | null, route?: string) {
    setLoading(true);
    try {
      const project = await createProject(problem, autoApprove, domain, route);
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

  if (authLoading) {
    return (
      <div style={{
        minHeight: "100vh", background: "#060918",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <div style={{
          width: 32, height: 32, border: "3px solid rgba(99,91,255,0.2)",
          borderTopColor: "#635bff", borderRadius: "50%",
          animation: "spin 0.6s linear infinite",
        }} />
      </div>
    );
  }

  if (!user) {
    return <LandingPage />;
  }

  return (
    <StartProject
      onStart={handleStart}
      loading={loading}
      recentProjects={recentProjects}
      hasDemo={hasDemo}
      onLoadDemo={handleLoadDemo}
    />
  );
}
