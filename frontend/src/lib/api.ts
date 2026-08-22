const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export interface Project {
  id: string;
  problem_statement: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AgentOutput {
  id: string;
  project_id: string;
  role: string;
  content: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface ProjectState {
  project: Project;
  outputs: AgentOutput[];
  memory: Record<string, string>;
  current_agent: string | null;
  pending_approval: boolean;
}

export interface WSMessage {
  type: string;
  project_id: string;
  data: {
    role?: string;
    output_id?: string;
    content?: Record<string, unknown>;
    message?: string;
    token?: string;
    token_count?: number;
  };
}

export async function createProject(
  problemStatement: string
): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem_statement: problemStatement }),
  });
  return res.json();
}

export async function getProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects`);
  return res.json();
}

export async function getProjectState(
  projectId: string
): Promise<ProjectState> {
  const res = await fetch(`${API_BASE}/projects/${projectId}`);
  return res.json();
}

export async function approveOutput(
  projectId: string,
  outputId: string,
  approved: boolean,
  feedback?: string
): Promise<void> {
  await fetch(`${API_BASE}/projects/${projectId}/approve/${outputId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved, feedback }),
  });
}

export async function callEmployee(
  projectId: string,
  role: string,
  message: string
): Promise<{ role: string; response: string }> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/call`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, message }),
  });
  return res.json();
}

export async function getConversation(
  projectId: string,
  role: string
): Promise<{ role: string; messages: { role: string; content: string }[] }> {
  const res = await fetch(
    `${API_BASE}/projects/${projectId}/conversation/${role}`
  );
  return res.json();
}

export function downloadCode(projectId: string) {
  window.open(`${API_BASE}/projects/${projectId}/download/code`, "_blank");
}

export function downloadPptx(projectId: string) {
  window.open(`${API_BASE}/projects/${projectId}/download/pptx`, "_blank");
}

export function downloadDocx(projectId: string) {
  window.open(`${API_BASE}/projects/${projectId}/download/docx`, "_blank");
}

export function downloadWorkflow(projectId: string) {
  window.open(`${API_BASE}/projects/${projectId}/download/workflow`, "_blank");
}

export async function getIntegrationStatus(): Promise<{
  n8n_connected: boolean;
  webhook_url_set: boolean;
}> {
  const res = await fetch(`${API_BASE}/integrations/status`);
  return res.json();
}

export async function shareProject(
  projectId: string,
  shareType: "drive" | "sheets" | "email" | "all"
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ share_type: shareType }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Share failed");
  }
  return res.json();
}

export async function saveDemoCache(projectId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/demo/save/${projectId}`, { method: "POST" });
  return res.json();
}

export async function loadDemoCache(): Promise<ProjectState | null> {
  const res = await fetch(`${API_BASE}/demo/load`);
  if (!res.ok) return null;
  return res.json();
}

export async function getDemoStatus(): Promise<{ has_demo: boolean }> {
  const res = await fetch(`${API_BASE}/demo/status`);
  return res.json();
}

export function downloadDemoDeliverable(fileType: string) {
  window.open(`${API_BASE}/demo/download/${fileType}`, "_blank");
}

export interface IntrospectionData {
  role: string;
  label: string;
  model: string;
  system_prompt: string;
  max_tokens: number;
  timeout: number;
  timing: {
    model?: string;
    primary_model?: string;
    used_fallback?: boolean;
    elapsed_seconds?: number;
    max_tokens?: number;
    timeout?: number;
    context_length?: number;
  };
  output: AgentOutput | null;
  peer_review: Record<string, unknown> | null;
}

export async function getIntrospection(
  projectId: string,
  role: string
): Promise<IntrospectionData> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/introspection/${role}`);
  return res.json();
}

export function connectWebSocket(
  projectId: string,
  onMessage: (msg: WSMessage) => void
): WebSocket {
  const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api";
  const ws = new WebSocket(`${wsBase}/ws/${projectId}`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch { /* ignore malformed messages */ }
  };
  ws.onerror = () => { /* handled by close event */ };
  return ws;
}
