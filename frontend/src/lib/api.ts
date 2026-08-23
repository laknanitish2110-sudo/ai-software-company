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

async function checkedJson<T>(res: Response, fallbackMsg: string): Promise<T> {
  if (!res.ok) {
    let detail = fallbackMsg;
    try {
      const err = await res.json();
      detail = err.detail || err.message || fallbackMsg;
    } catch { /* ignore parse errors */ }
    throw new Error(detail);
  }
  return res.json();
}

export async function createProject(
  problemStatement: string,
  autoApprove: boolean = false
): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem_statement: problemStatement, auto_approve: autoApprove }),
  });
  return checkedJson(res, "Failed to create project");
}

export async function getProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects`);
  return checkedJson(res, "Failed to load projects");
}

export async function getProjectState(
  projectId: string
): Promise<ProjectState> {
  const res = await fetch(`${API_BASE}/projects/${projectId}`);
  return checkedJson(res, "Failed to load project state");
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
  return checkedJson(res, "Failed to call employee");
}

export async function getConversation(
  projectId: string,
  role: string
): Promise<{ role: string; messages: { role: string; content: string }[] }> {
  const res = await fetch(
    `${API_BASE}/projects/${projectId}/conversation/${role}`
  );
  return checkedJson(res, "Failed to load conversation");
}

async function safeDownload(url: string, fallbackMsg: string) {
  const res = await fetch(url, { method: "HEAD" });
  if (res.ok) {
    window.open(url, "_blank");
  } else {
    throw new Error(fallbackMsg);
  }
}

export function downloadCode(projectId: string) {
  return safeDownload(
    `${API_BASE}/projects/${projectId}/download/code`,
    "No generated code found. Run the pipeline first."
  );
}

export function downloadPptx(projectId: string) {
  return safeDownload(
    `${API_BASE}/projects/${projectId}/download/pptx`,
    "No presentation found. Pipeline must complete first."
  );
}

export function downloadDocx(projectId: string) {
  return safeDownload(
    `${API_BASE}/projects/${projectId}/download/docx`,
    "No report found. Pipeline must complete first."
  );
}

export function downloadWorkflow(projectId: string) {
  return safeDownload(
    `${API_BASE}/projects/${projectId}/download/workflow`,
    "No workflow JSON found. Only available for workflow/hybrid deliverables."
  );
}

export async function getIntegrationStatus(): Promise<{
  n8n_connected: boolean;
  webhook_url_set: boolean;
}> {
  const res = await fetch(`${API_BASE}/integrations/status`);
  return checkedJson(res, "Failed to check integration status");
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
  return checkedJson(res, "Failed to save demo cache");
}

export async function loadDemoCache(): Promise<ProjectState | null> {
  const res = await fetch(`${API_BASE}/demo/load`);
  if (!res.ok) return null;
  return res.json();
}

export async function getDemoStatus(): Promise<{ has_demo: boolean }> {
  const res = await fetch(`${API_BASE}/demo/status`);
  return checkedJson(res, "Failed to check demo status");
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
  return checkedJson(res, "Failed to load agent introspection");
}

export interface GeneratedFile {
  path: string;
  size: number;
  content: string;
  language: string;
}

export async function getFileContents(
  projectId: string
): Promise<{ files: GeneratedFile[]; count: number }> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/files/content`);
  if (!res.ok) return { files: [], count: 0 };
  return res.json();
}

export interface ReconnectingWebSocket {
  close(): void;
  addEventListener(event: string, handler: () => void): void;
}

export function connectWebSocket(
  projectId: string,
  onMessage: (msg: WSMessage) => void,
  onStatusChange?: (connected: boolean) => void
): ReconnectingWebSocket {
  const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api";
  let ws: WebSocket | null = null;
  let attempt = 0;
  let closed = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  const listeners: Record<string, (() => void)[]> = {};

  function connect() {
    if (closed) return;
    ws = new WebSocket(`${wsBase}/ws/${projectId}`);
    ws.onopen = () => {
      attempt = 0;
      onStatusChange?.(true);
      listeners["open"]?.forEach((fn) => fn());
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch { /* ignore malformed messages */ }
    };
    ws.onclose = () => {
      onStatusChange?.(false);
      listeners["close"]?.forEach((fn) => fn());
      if (!closed) {
        const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
        attempt++;
        reconnectTimer = setTimeout(connect, delay);
      }
    };
    ws.onerror = () => { /* handled by close event */ };
  }

  connect();

  return {
    close() {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    },
    addEventListener(event: string, handler: () => void) {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(handler);
    },
  };
}
