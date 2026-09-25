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

const TOKEN_KEY = "auth_token";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  const token = getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function fetchWithTimeout(
  url: string,
  options?: RequestInit,
  timeoutMs: number = 120000
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function checkedJson<T>(res: Response, fallbackMsg: string): Promise<T> {
  if (res.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem("auth_user");
    window.location.href = "/login";
    throw new Error("Session expired");
  }
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
  autoApprove: boolean = false,
  domain?: string | null,
  route?: string | null
): Promise<Project> {
  const body: Record<string, unknown> = { problem_statement: problemStatement, auto_approve: autoApprove };
  if (domain) body.domain = domain;
  if (route) body.route = route;
  const res = await fetchWithTimeout(`${API_BASE}/projects`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  return checkedJson(res, "Failed to create project");
}

export async function getProjects(): Promise<Project[]> {
  const res = await fetchWithTimeout(`${API_BASE}/projects`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load projects");
}

export async function deleteProject(projectId: string): Promise<{ status: string; deleted: boolean }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to delete project");
}

export async function getProjectBudget(
  projectId: string
): Promise<Record<string, unknown>> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/budget`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load budget");
}

export interface CostSummary {
  project_id: string;
  totals: {
    total_calls: number;
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_tokens: number;
    total_cost: number;
  };
  per_agent: Array<{
    role: string;
    calls: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated_cost: number;
    model: string;
  }>;
  budget: {
    llm_calls: number;
    total_tokens: number;
    max_llm_calls: number;
    max_tokens: number;
    budget_status: string;
  };
}

export async function getProjectCosts(projectId: string): Promise<CostSummary> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/costs`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load costs");
}

export async function getProjectExecutions(
  projectId: string
): Promise<Record<string, unknown>[]> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/executions`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load executions");
}

export async function cancelExecution(
  executionId: string
): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/executions/${executionId}/cancel`, {
    method: "POST",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to cancel execution");
}

export async function listGeneratedFiles(
  projectId: string
): Promise<{ project_id: string; files: string[]; count: number }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/files`, { headers: authHeaders() });
  return checkedJson(res, "Failed to list files");
}

export async function getProjectState(
  projectId: string
): Promise<ProjectState> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load project state");
}

export async function approveOutput(
  projectId: string,
  outputId: string,
  approved: boolean,
  feedback?: string
): Promise<void> {
  await fetchWithTimeout(`${API_BASE}/projects/${projectId}/approve/${outputId}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ approved, feedback }),
  });
}

export async function callEmployee(
  projectId: string,
  role: string,
  message: string
): Promise<{ role: string; response: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/call`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ role, message }),
  });
  return checkedJson(res, "Failed to call employee");
}

export async function getConversation(
  projectId: string,
  role: string
): Promise<{ role: string; messages: { role: string; content: string }[] }> {
  const res = await fetchWithTimeout(
    `${API_BASE}/projects/${projectId}/conversation/${role}`,
    { headers: authHeaders() }
  );
  return checkedJson(res, "Failed to load conversation");
}

async function safeDownload(url: string, fallbackMsg: string) {
  const res = await fetchWithTimeout(url, { method: "HEAD", headers: authHeaders() });
  if (res.ok) {
    const token = getAuthToken();
    const sep = url.includes("?") ? "&" : "?";
    window.open(token ? `${url}${sep}token=${token}` : url, "_blank");
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

export function downloadBundle(projectId: string) {
  return safeDownload(
    `${API_BASE}/projects/${projectId}/download/bundle`,
    "No deployable bundle available. Build must succeed first."
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
  const res = await fetchWithTimeout(`${API_BASE}/integrations/status`, { headers: authHeaders() });
  return checkedJson(res, "Failed to check integration status");
}

export async function getModelConfig(): Promise<{
  agents: Record<string, { model: string; provider: string; display: { model: string; provider: string; providerColor: string } }>;
  providers: Record<string, boolean>;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/models`, { headers: authHeaders() });
  return checkedJson(res, "Failed to fetch model config");
}

export async function shareProject(
  projectId: string,
  shareType: "drive" | "sheets" | "email" | "all"
): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/share`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ share_type: shareType }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Share failed");
  }
  return res.json();
}

export async function saveDemoCache(projectId: string): Promise<{ status: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/demo/save/${projectId}`, {
    method: "POST",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to save demo cache");
}

export async function loadDemoCache(): Promise<ProjectState | null> {
  const res = await fetchWithTimeout(`${API_BASE}/demo/load`, { headers: authHeaders() });
  if (!res.ok) return null;
  return res.json();
}

export async function getDemoStatus(): Promise<{ has_demo: boolean }> {
  const res = await fetchWithTimeout(`${API_BASE}/demo/status`, { headers: authHeaders() });
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

export async function reviseAgent(
  projectId: string,
  role: string,
  feedback: string
): Promise<{ status: string; role: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/revise`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ role, feedback }),
  });
  return checkedJson(res, "Failed to start revision");
}

export async function generateShareLink(
  projectId: string
): Promise<{ token: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/share-link`, {
    method: "POST",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to generate share link");
}

export async function getSharedProject(
  token: string
): Promise<ProjectState> {
  const res = await fetchWithTimeout(`${API_BASE}/shared/${token}`);
  return checkedJson(res, "Shared project not found");
}

export async function getIntrospection(
  projectId: string,
  role: string
): Promise<IntrospectionData> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/introspection/${role}`, {
    headers: authHeaders(),
  });
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
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/files/content`, {
    headers: authHeaders(),
  });
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
    const token = getAuthToken();
    const tokenParam = token ? `?token=${token}` : "";
    ws = new WebSocket(`${wsBase}/ws/${projectId}${tokenParam}`);
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

export async function callEmployeeStream(
  projectId: string,
  role: string,
  message: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/call/stream`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ role, message }),
  });

  if (!res.ok || !res.body) {
    onError("Stream connection failed");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.token) onToken(data.token);
          if (data.done) onDone();
          if (data.error) onError(data.error);
        } catch { /* skip malformed SSE lines */ }
      }
    }
  }
  onDone();
}

export async function applyFileChanges(projectId: string, files: { path: string; content: string }[]): Promise<{ status: string; updated_files: string[]; count: number }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/files/apply`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ files }),
  });
  return checkedJson(res, "Failed to apply file changes");
}

export async function saveGitHubToken(token: string): Promise<{ status: string; github_username: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/settings/github-token`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ token }),
  });
  return checkedJson(res, "Failed to save GitHub token");
}

export async function checkGitHubToken(): Promise<{ has_token: boolean; github_username?: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/settings/github-token`, { headers: authHeaders() });
  return checkedJson(res, "Failed to check GitHub token");
}

export async function pushToGitHub(
  projectId: string,
  repoName: string,
  description?: string,
  isPrivate?: boolean,
): Promise<{ status: string; repo_url: string; commit_sha: string; files_pushed: number }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/push-to-github`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ repo_name: repoName, description: description || "", private: isPrivate || false }),
  });
  return checkedJson(res, "Failed to push to GitHub");
}

export async function getPreviewStatus(projectId: string): Promise<{ active: boolean; preview_url: string | null; has_static_preview?: boolean; timeout_seconds: number }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/preview`, { headers: authHeaders() });
  return checkedJson(res, "Failed to check preview status");
}

export function getStaticPreviewUrl(projectId: string): string {
  return `${API_BASE}/projects/${projectId}/preview/static`;
}

export async function stopPreview(projectId: string): Promise<{ status: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/projects/${projectId}/preview/stop`, {
    method: "POST",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to stop preview");
}

// ─── Persistent Employee Platform ──────────────────────────────────

export interface Employee {
  id: string;
  user_id: string;
  name: string;
  role: string;
  persona: string | null;
  avatar_url: string | null;
  status: string;
  config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  session_count?: number;
  memory_count?: number;
  last_active?: string | null;
}

export interface EmployeeSession {
  id: string;
  employee_id: string;
  project_id: string | null;
  status: string;
  summary: string | null;
  started_at: string;
  ended_at: string | null;
  last_activity: string;
}

export interface SessionMessage {
  id: string;
  session_id: string;
  role: string;
  content: string;
  tool_calls: string | null;
  tool_results: string | null;
  created_at: string;
}

export interface Memory {
  id: string;
  employee_id: string;
  type: string;
  content: string;
  source: string | null;
  source_id: string | null;
  confidence: number;
  importance: number;
  tags: string[] | null;
  created_at: string;
  last_accessed: string | null;
  last_verified: string | null;
  stale_after: string | null;
  is_active: number;
}

export interface ToolPermission {
  id: string;
  employee_id: string;
  tool: string;
  action: string;
  permission: string;
  granted_by: string | null;
  updated_at: string;
}

export async function listEmployees(): Promise<Employee[]> {
  const res = await fetchWithTimeout(`${API_BASE}/employees`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load employees");
}

export async function provisionTeam(): Promise<{ provisioned: number; employees: Employee[] }> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/provision`, {
    method: "POST", headers: authHeaders(),
  });
  return checkedJson(res, "Failed to provision team");
}

export async function seedDefaultSkills(): Promise<{ seeded: number }> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/seed-skills`, {
    method: "POST", headers: authHeaders(),
  });
  return checkedJson(res, "Failed to seed skills");
}

export interface ActivityItem {
  id: string;
  employee_id: string | null;
  employee_name: string | null;
  event_type: string;
  title: string;
  detail: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  seen: number;
}

export async function getActivityFeed(limit = 50, unseenOnly = false): Promise<{ activities: ActivityItem[]; unseen_count: number }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (unseenOnly) params.set("unseen_only", "true");
  const res = await fetchWithTimeout(`${API_BASE}/activity?${params}`, { headers: authHeaders() });
  return checkedJson(res, "Failed to fetch activity");
}

export async function markActivitySeen(): Promise<void> {
  await fetchWithTimeout(`${API_BASE}/activity/mark-seen`, {
    method: "POST", headers: authHeaders(),
  });
}

export async function createEmployee(data: {
  name: string; role: string; persona?: string; avatar_url?: string; config?: Record<string, unknown>;
}): Promise<Employee> {
  const res = await fetchWithTimeout(`${API_BASE}/employees`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  return checkedJson(res, "Failed to create employee");
}

export async function getEmployee(id: string): Promise<Employee> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${id}`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load employee");
}

export async function updateEmployee(id: string, data: Partial<Pick<Employee, "name" | "role" | "persona" | "avatar_url" | "config">>): Promise<Employee> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${id}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  return checkedJson(res, "Failed to update employee");
}

export async function archiveEmployee(id: string): Promise<{ status: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to archive employee");
}

export async function createEmployeeSession(employeeId: string): Promise<EmployeeSession> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/sessions`, {
    method: "POST",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to create session");
}

export async function listEmployeeSessions(employeeId: string, limit = 20): Promise<EmployeeSession[]> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/sessions?limit=${limit}`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load sessions");
}

export async function getSessionWithMessages(sessionId: string): Promise<EmployeeSession & { messages: SessionMessage[] }> {
  const res = await fetchWithTimeout(`${API_BASE}/sessions/${sessionId}`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load session");
}

export async function sendEmployeeMessage(sessionId: string, content: string): Promise<{ user_message: SessionMessage; employee_message: SessionMessage }> {
  const res = await fetchWithTimeout(`${API_BASE}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ content }),
  });
  return checkedJson(res, "Failed to send message");
}

export async function endEmployeeSession(sessionId: string): Promise<{ status: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/sessions/${sessionId}/end`, {
    method: "POST",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to end session");
}

export async function listMemories(employeeId: string, type?: string, search?: string, limit = 50): Promise<Memory[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (type) params.set("type", type);
  if (search) params.set("search", search);
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/memories?${params}`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load memories");
}

export async function createMemory(employeeId: string, data: {
  type: string; content: string; source?: string; confidence?: number; importance?: number; tags?: string[]; stale_after?: string;
}): Promise<Memory> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/memories`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  return checkedJson(res, "Failed to create memory");
}

export async function updateMemory(id: string, data: Partial<Pick<Memory, "content" | "confidence" | "importance" | "tags" | "is_active">>): Promise<Memory> {
  const res = await fetchWithTimeout(`${API_BASE}/memories/${id}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(data),
  });
  return checkedJson(res, "Failed to update memory");
}

export async function deactivateMemory(id: string): Promise<{ status: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/memories/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to deactivate memory");
}

export interface ConsolidationResult {
  status: string;
  decayed: number;
  merged: number;
  deactivated: number;
  groups_processed: number;
}

export async function consolidateMemories(employeeId: string): Promise<ConsolidationResult> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/consolidate`, {
    method: "POST",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to consolidate memories");
}

export async function getEmployeePermissions(employeeId: string): Promise<ToolPermission[]> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/permissions`, { headers: authHeaders() });
  return checkedJson(res, "Failed to load permissions");
}

export async function updateEmployeePermission(employeeId: string, tool: string, action: string, permission: string): Promise<ToolPermission> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/permissions`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ tool, action, permission }),
  });
  return checkedJson(res, "Failed to update permission");
}

export interface DelegationTask {
  id: string;
  from_employee_id: string;
  to_employee_id: string;
  user_id: string;
  task: string;
  context: string | null;
  status: "pending" | "running" | "completed" | "failed";
  result: string | null;
  project_id: string | null;
  session_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export async function listDelegations(employeeId: string): Promise<DelegationTask[]> {
  const res = await fetchWithTimeout(`${API_BASE}/delegations?employee_id=${employeeId}`, {
    headers: authHeaders(),
  });
  const data = await checkedJson<{ delegations: DelegationTask[] }>(res, "Failed to list delegations");
  return data.delegations;
}

export async function getDelegation(taskId: string): Promise<DelegationTask> {
  const res = await fetchWithTimeout(`${API_BASE}/delegations/${taskId}`, {
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to get delegation");
}

export async function listWorkspaceFiles(employeeId: string, directory = ""): Promise<string[]> {
  const params = directory ? `?directory=${encodeURIComponent(directory)}` : "";
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/workspace${params}`, {
    headers: authHeaders(),
  });
  const data = await checkedJson<{ files: string[] }>(res, "Failed to list workspace files");
  return data.files;
}

export async function readWorkspaceFile(employeeId: string, path: string): Promise<string> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/workspace/file?path=${encodeURIComponent(path)}`, {
    headers: authHeaders(),
  });
  const data = await checkedJson<{ path: string; content: string }>(res, "Failed to read file");
  return data.content;
}

// --- Skills ---

export interface EmployeeSkill {
  id: string;
  employee_id: string;
  name: string;
  description: string;
  trigger_pattern: string | null;
  procedure: string;
  examples: string[] | null;
  times_used: number;
  success_rate: number;
  created_at: string;
  last_used: string | null;
  is_active: boolean;
}

export async function listSkills(employeeId: string): Promise<EmployeeSkill[]> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/skills`, {
    headers: authHeaders(),
  });
  const data = await checkedJson<{ skills: EmployeeSkill[] }>(res, "Failed to list skills");
  return data.skills;
}

export async function extractSkills(employeeId: string, sessionId?: string): Promise<{ extracted: number; skills: EmployeeSkill[] }> {
  const params = sessionId ? `?session_id=${sessionId}` : "";
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/skills/extract${params}`, {
    method: "POST",
    headers: authHeaders(),
  });
  return checkedJson(res, "Failed to extract skills");
}

export async function deactivateSkill(employeeId: string, skillId: string): Promise<void> {
  const res = await fetchWithTimeout(`${API_BASE}/employees/${employeeId}/skills/${skillId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  await checkedJson(res, "Failed to deactivate skill");
}
