"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import LandingPage from "@/components/LandingPage";
import StartProject from "@/components/StartProject";
import OnboardingModal from "@/components/OnboardingModal";
import { useToast } from "@/components/Toast";
import { createProject, getProjects, getDemoStatus, loadDemoCache, deleteProject, renameProject } from "@/lib/api";

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
  const [showOnboarding, setShowOnboarding] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    if (!user) return;
    getProjects()
      .then((projects) => {
        const sorted = projects
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setRecentProjects(sorted);
        try {
          const dismissed = localStorage.getItem("onboarding_dismissed");
          if (projects.length === 0 && !dismissed) {
            setShowOnboarding(true);
          }
        } catch {}
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

  function dismissOnboarding() {
    setShowOnboarding(false);
    try { localStorage.setItem("onboarding_dismissed", "1"); } catch {}
  }

  return (
    <>
      {showOnboarding && (
        <OnboardingModal
          onDismiss={dismissOnboarding}
          onTryPipeline={() => {
            dismissOnboarding();
          }}
          onTryEmployee={() => {
            dismissOnboarding();
            router.push("/employees");
          }}
        />
      )}
      <StartProject
        onStart={handleStart}
        loading={loading}
        recentProjects={recentProjects}
        hasDemo={hasDemo}
        onLoadDemo={handleLoadDemo}
        onDeleteProject={async (id) => {
          try {
            await deleteProject(id);
            setRecentProjects((prev) => prev.filter((p) => p.id !== id));
            toast("success", "Deleted", "Project removed successfully.");
          } catch { toast("error", "Error", "Failed to delete project."); }
        }}
        onRenameProject={async (id, name) => {
          try {
            await renameProject(id, name);
            setRecentProjects((prev) => prev.map((p) => p.id === id ? { ...p, problem_statement: name } : p));
          } catch { toast("error", "Error", "Failed to rename project."); }
        }}
      />
    </>
  );
}
