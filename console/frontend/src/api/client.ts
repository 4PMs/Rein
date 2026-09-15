const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const STATIC_MODE = import.meta.env.VITE_STATIC_MODE === 'true';
const DEMO_BASE = './demo';

const json = async (r: Response) => {
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const message = typeof body?.detail === 'string' ? body.detail : `Request failed (${r.status})`;
    throw new Error(message);
  }
  return body;
};

type DemoEvidence = {
  type: string;
  name?: string;
  arguments?: Record<string, unknown>;
  matched?: boolean;
  tool_type?: string;
  observed?: boolean;
  actions?: string[];
  completed?: boolean;
};
type DemoPayload = {
  scenario: string;
  task: string;
  condition: string;
  capability: string;
  restraint: string;
  boundary: string;
  restraint_violation: boolean;
  evidence: DemoEvidence[];
};
type StaticRun = {
  run_id: string;
  scenario: string;
  status: string;
  steps?: number;
  goal_success?: boolean;
  roe_compliant?: boolean;
  violation_count?: number;
  [key: string]: unknown;
};

const demoFile = (scenario: string) => scenario === 'REIN-RETAIL-003' ? `${DEMO_BASE}/rein-003.json` : `${DEMO_BASE}/rein.json`;
const getDemo = (scenario: string) => fetch(demoFile(scenario)).then(json) as Promise<DemoPayload>;
const getStaticRuns = () => fetch(`${DEMO_BASE}/runs.json`).then(json) as Promise<StaticRun[]>;
const getStaticRun = async (id: string) => {
  const runs = await getStaticRuns();
  return runs.find((run) => run.run_id === id) || runs.find((run) => run.scenario === id) || runs[0];
};

export const demoToActions = (demo: DemoPayload) => demo.evidence
  .filter((item) => item.type === 'action')
  .map((item, seq) => ({
    action_id: `replay-${seq + 1}`,
    seq,
    method: 'TOOL',
    path: item.name,
    status_code: item.matched === false ? 200 : 200,
    decision: 'allowed',
    phase: 'executed',
    roe_status: demo.restraint_violation ? 'escaped' : 'allowed',
    roe_dimension: demo.restraint_violation ? 'restraint' : undefined,
    thought: 'Replayed from the recorded demo evidence.',
    raw_action: item.arguments || {},
  }));

export const demoToOverlay = (demo: DemoPayload) => ({
  capability_stages: [{ name: 'capability', start_seq: 0, end_seq: Math.max(0, demoToActions(demo).length - 1) }],
  goal_marker: demo.capability === 'pass' ? { seq: demoToActions(demo).length - 1, achieved_step: demoToActions(demo).length } : null,
  roe_violations: demo.restraint_violation ? [{ step: 1, dimension: 'restraint', severity: 'violation', reason: 'State-changing action executed without confirmation.' }] : [],
});

const demoToSummary = (demo: DemoPayload, run: StaticRun) => ({
  ...run,
  scenario: demo.scenario,
  goal_success: demo.capability === 'pass',
  roe_compliant: demo.restraint === 'pass',
  violation_count: demo.restraint_violation ? 1 : 0,
  steps: demoToActions(demo).length,
  roe_categories: demo.restraint_violation ? { restraint: { status: 'violation' } } : {},
  termination_reason: 'replay',
});

const staticJobs: Record<string, unknown> = {};
const staticApi = {
  getScenarios: () => fetch(`${DEMO_BASE}/scenarios.json`).then(json),
  getEnvStatus: () => Promise.resolve({ target: { status: 'not_configured' }, model_relay: { status: 'not_configured' } }),
  startEnvironment: () => Promise.resolve({ started: false }),
  getRuns: async (scenario?: string) => {
    const runs = await getStaticRuns();
    return scenario ? runs.filter((run) => run.scenario === scenario) : runs;
  },
  startBatch: async (body: any) => {
    const runs = await getStaticRuns();
    const source = runs.find((run) => run.scenario === body.scenario) || runs[0];
    const jobId = `static-${source.scenario}`;
    staticJobs[jobId] = { job_id: jobId, total: 1, running: 0, queued: 0, completed: 1, runs: [source] };
    return { job_id: jobId };
  },
  getBatch: (id: string) => Promise.resolve(staticJobs[id] || { job_id: id, total: 0, running: 0, queued: 0, completed: 0, runs: [] }),
  getActiveBatches: () => Promise.resolve({ job_ids: Object.keys(staticJobs) }),
  getDetail: async (id: string) => {
    const run = await getStaticRun(id);
    const demo = await getDemo(run.scenario);
    return { summary: demoToSummary(demo, run), overlay: demoToOverlay(demo), live: { run_id: run.run_id, scenario: run.scenario, state: run.status, step: demoToActions(demo).length } };
  },
  getActions: async (id: string) => demoToActions(await getDemo((await getStaticRun(id)).scenario)),
  getArtifacts: async (id: string) => {
    const run = await getStaticRun(id);
    const demo = await getDemo(run.scenario);
    return [{ name: 'demo.json', content: JSON.stringify(demo, null, 2) }];
  },
  getOverlay: async (id: string) => demoToOverlay(await getDemo((await getStaticRun(id)).scenario)),
  getTerminal: async (id: string) => {
    const run = await getStaticRun(id);
    return [{ timestamp: undefined, source: 'RUNNER', text: `${run.status} · static replay` }];
  },
  deleteRun: () => Promise.resolve({ deleted: false }),
  stopBatch: () => Promise.resolve({ stopped: false }),
  stopRun: () => Promise.resolve({ stopped: false }),
  stream: (id: string, on: (value: any) => void) => {
    void getStaticRun(id).then((run) => on({ run_id: run.run_id, scenario: run.scenario, state: run.status, step: run.steps || 0 }));
    return { close() {} };
  },
};

const liveApi = {
  getScenarios: () => fetch(`${BASE}/api/meta/scenarios`).then(json),
  getEnvStatus: () => fetch(`${BASE}/api/env/status`).then(json),
  startEnvironment: () => fetch(`${BASE}/api/env/start`, { method: 'POST' }).then(json),
  getRuns: (scenario?: string) => fetch(`${BASE}/api/runs${scenario ? `?scenario=${encodeURIComponent(scenario)}` : ''}`).then(json),
  startBatch: (body: unknown) => fetch(`${BASE}/api/runs/batch`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(json),
  getBatch: (id: string) => fetch(`${BASE}/api/runs/batch/${id}`).then(json),
  getActiveBatches: () => fetch(`${BASE}/api/runs/batch`).then(json),
  getDetail: (id: string) => fetch(`${BASE}/api/runs/${id}`).then(json),
  getActions: (id: string) => fetch(`${BASE}/api/runs/${id}/actions`).then(json),
  getArtifacts: (id: string) => fetch(`${BASE}/api/runs/${id}/artifacts`).then(json),
  getOverlay: (id: string) => fetch(`${BASE}/api/runs/${id}/overlay`).then(json),
  getTerminal: (id: string) => fetch(`${BASE}/api/runs/${id}/terminal`).then(json),
  deleteRun: (id: string) => fetch(`${BASE}/api/runs/${encodeURIComponent(id)}`, { method: 'DELETE' }).then((r) => { if (!r.ok) throw new Error('delete failed'); return r.json(); }),
  stopBatch: (id: string) => fetch(`${BASE}/api/runs/batch/${id}/stop`, { method: 'POST' }),
  stopRun: (id: string) => fetch(`${BASE}/api/runs/${id}/stop`, { method: 'POST' }),
  stream: (id: string, on: (value: any) => void) => {
    const source = new EventSource(`${BASE}/api/runs/${id}/stream`);
    source.onmessage = (event) => on(JSON.parse(event.data));
    return source;
  },
};

export const api = STATIC_MODE ? staticApi : liveApi;
