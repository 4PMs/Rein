import { toExecutionEvents, type ExecutionEvent } from "../domain/executionEvents";

export type Scenario = { id: string; name?: string; description?: string; policy?: string | null; demo?: boolean; [key: string]: unknown };
export type RunSummary = { run_id: string; scenario?: string | null; status: string; [key: string]: unknown };
export type RunConfig = { scenario: string; model?: string; provider?: string; runs_per_worker?: number; parallel_workers?: number; [key: string]: unknown };
export type RunDetail = { summary: RunSummary; overlay: Record<string, unknown>; live: Record<string, unknown> | null; events?: ExecutionEvent[] };

const staticMode = import.meta.env.VITE_STATIC_MODE === "true";
const apiBase = (import.meta.env.VITE_API_BASE || "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

async function staticJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Static demo unavailable: ${path}`);
  return response.json() as Promise<T>;
}

export const api = {
  staticMode,
  async getScenarios(): Promise<Scenario[]> {
    return staticMode ? staticJson<Scenario[]>("/demo/scenarios.json") : request<Scenario[]>("/api/meta/scenarios");
  },
  async getRuns(scenario?: string): Promise<RunSummary[]> {
    if (staticMode) return staticJson<RunSummary[]>("/demo/runs.json");
    return request<RunSummary[]>(`/api/runs${scenario ? `?scenario=${encodeURIComponent(scenario)}` : ""}`);
  },
  async startBatch(config: RunConfig): Promise<{ job_id: string }> {
    if (staticMode) return { job_id: `static-${config.scenario}` };
    return request<{ job_id: string }>("/api/runs/batch", { method: "POST", body: JSON.stringify({ model: "deepseek-flash", runs_per_worker: 1, parallel_workers: 1, ...config }) });
  },
  async getBatchStatus(jobId: string): Promise<any> {
    if (staticMode) return { job_id: jobId, completed: 1, total: 1, runs: [] };
    return request<any>(`/api/runs/batch/${encodeURIComponent(jobId)}`);
  },
  async getDetail(id: string): Promise<RunDetail> {
    if (staticMode) {
      const file = id.includes("003") ? "/demo/rein-003.json" : "/demo/rein.json";
      const demo = await staticJson<any>(file);
      return { summary: { run_id: id, scenario: demo.scenario, status: "completed", goal_success: demo.capability === "pass", roe_compliant: demo.restraint === "pass" }, overlay: {}, live: null, events: toExecutionEvents(demo) };
    }
    return request<RunDetail>(`/api/runs/${encodeURIComponent(id)}`);
  },
  async getActions(id: string): Promise<Record<string, unknown>[]> {
    if (staticMode) return toExecutionEvents(await staticJson<any>(id.includes("003") ? "/demo/rein-003.json" : "/demo/rein.json"));
    return request<Record<string, unknown>[]>(`/api/runs/${encodeURIComponent(id)}/actions`);
  },
  async getOverlay(id: string): Promise<Record<string, unknown>> {
    if (staticMode) return {};
    return request<Record<string, unknown>>(`/api/runs/${encodeURIComponent(id)}/overlay`);
  },
  async getEvents(id: string): Promise<ExecutionEvent[]> {
    if (staticMode) return (await this.getDetail(id)).events || [];
    return request<ExecutionEvent[]>(`/api/runs/${encodeURIComponent(id)}/events`);
  },
};

declare global { interface Window { ReinApi?: typeof api } }
if (typeof window !== "undefined") window.ReinApi = api;

export default api;
