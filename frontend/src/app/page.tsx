"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import StartProject from "@/components/StartProject";
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

  useEffect(() => {
    getProjects()
      .then((projects) => {
        const recent = projects
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          .slice(0, 3);
        setRecentProjects(recent);
      })
      .catch(() => {});

    getDemoStatus()
      .then((s) => setHasDemo(s.has_demo))
      .catch(() => {});
  }, []);

  async function handleStart(problem: string) {
    setLoading(true);
    try {
      const project = await createProject(problem);
      localStorage.setItem("lastProjectId", project.id);
      router.push(`/project/${project.id}`);
    } catch (err) {
      console.error("Failed to start project:", err);
      alert("Failed to start project. Is the backend running?");
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
        alert("No demo cache found. Run a successful pipeline first.");
      }
    } catch {
      alert("Failed to load demo.");
    } finally {
      setLoading(false);
    }
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
