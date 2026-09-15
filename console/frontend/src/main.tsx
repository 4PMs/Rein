import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api/client";
import "./theme/tokens.css";
import "./theme/live-run.css";
import "./theme/brand.css";
import "./theme/dock-fix.css";
import "./theme/scope.css";
type Scenario = { id: string; policy?: string | null };
type Run = {
  run_id: string;
  scenario?: string;
  model?: string;
  status: string;
  error?: string;
  state?: string;
  step?: number;
  max_steps?: number;
  elapsed_sec?: number;
  steps?: number;
  tokens_total?: number;
  last_action?: string;
  goal_success?: boolean;
  goal_step?: number | null;
  roe_compliant?: boolean;
  violation_count?: number;
  roe_categories?: Record<
    string,
    { status?: string; violation_count?: number }
  >;
};
type OverlayViolation = {
  step?: number | null;
  roe_categories?: string[];
  severity?: string;
  dimension?: string;
  reason?: string;
};
type RunOverlay = {
  capability_stages?: { name: string; start_seq?: number | null; end_seq?: number | null }[];
  goal_marker?: { seq?: number | null; achieved_step?: number | null } | null;
  roe_violations: OverlayViolation[];
};
type ScopeEntry = {
  condition: string;
  reason: string;
  run_id?: string;
  artifact_id?: string;
  capability?: string;
  restraint?: string;
  boundary?: string;
  evidence_summary?: {
    confirmation_required?: boolean;
    confirmation_observed?: boolean;
    state_change?: boolean;
    executed_actions?: string[];
    task_completed?: boolean;
    restraint_violation?: boolean;
  };
};
type ScopeReport = {
  scenario: string;
  recommended_scope: {
    autonomous: ScopeEntry[];
    human_approval: ScopeEntry[];
    blocked: ScopeEntry[];
  };
};
type Action = {
  action_id: string;
  seq: number;
  method?: string;
  path?: string;
  status_code?: number;
  decision?: "allowed" | "blocked";
  decision_reason?: string;
  phase?: string;
  roe_dimension?: string;
  roe_status?: string;
  roe_category?: string;
  roe_categories?: string[];
  thought?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  raw_action?: Record<string, unknown>;
};
type Artifact = { name: string; content: string };
type Log = { timestamp?: string; source: string; text: string };
const labels: Record<string, string> = {
  running: "live",
  completed: "complete",
  failed: "failed",
  invalid: "invalid",
  partial: "partial",
  interrupted: "interrupted",
  queued: "queued",
  stopping: "stopping",
  stopped: "stopped",
  finalizing: "finalizing",
};
// Terminal outcomes written once a run's process has exited — never still "live".
const TERMINAL_STATUSES = ["completed", "failed", "stopped", "invalid", "partial", "interrupted"];
const highlightJson = (value: string) =>
  value
    .replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]!)
    .replace(/("(?:\\.|[^"\\])*")(\s*:)?/g, (_, token, colon) =>
      colon
        ? `<span class="json-key">${token}</span>${colon}`
        : `<span class="json-string">${token}</span>`,
    )
    .replace(/\b(true|false|null)\b/g, '<span class="json-literal">$1</span>')
    .replace(/\b-?\d+(?:\.\d+)?\b/g, '<span class="json-number">$&</span>');
function AutonomyScope() {
  const [report, setReport] = useState<ScopeReport>();
  const [selected, setSelected] = useState<ScopeEntry>();
  useEffect(() => {
    fetch("/demo/recommended-autonomy-scope.json")
      .then((response) => {
        if (!response.ok) throw new Error("scope unavailable");
        return response.json() as Promise<ScopeReport>;
      })
      .then((next) => {
        setReport(next);
        setSelected(next.recommended_scope.human_approval[0] || next.recommended_scope.autonomous[0]);
      })
      .catch(() => setReport(undefined));
  }, []);
  if (!report) return null;
  const scope = report.recommended_scope;
  const states = [
    { key: "autonomous", label: "AUTONOMOUS", mark: "✓", items: scope.autonomous },
    { key: "human_approval", label: "HUMAN APPROVAL", mark: "!", items: scope.human_approval },
    { key: "blocked", label: "BLOCKED", mark: "", items: scope.blocked },
  ];
  const evidence = selected?.evidence_summary || {};
  return (
    <section className="card scope-hero" aria-labelledby="scope-title">
      <div className="scope-hero-heading">
        <div>
          <p className="scope-kicker">Rein / Product boundary</p>
          <h1 id="scope-title">How far can this agent act on its own?</h1>
        </div>
        <p className="scope-subtitle">Test AI agents under real operating conditions<br />and find where human approval is actually needed.</p>
        <span className="scope-scenario">{report.scenario.replace(/_/g, " ")}</span>
      </div>
      <div className="scope-states">
        {states.map((state) => {
          const item = state.items[0];
          return (
            <button type="button" className={`scope-state ${state.key} ${item === selected ? "selected" : ""}`} key={state.key} onClick={() => item && setSelected(item)} aria-pressed={item === selected} disabled={!item}>
              <span className="scope-state-head"><i className="scope-state-mark">{state.mark}</i>{state.label}</span>
              <strong>{item ? item.condition.replace(/_/g, " ") : "None"}</strong>
              <small>{item ? "Observed condition" : "No observed runs"}</small>
            </button>
          );
        })}
      </div>
      {selected && (
        <div className="scope-detail">
          <div>
            <p className="scope-kicker">Boundary detail / {selected.condition.replace(/_/g, " ")}</p>
            <h2>What happened at the boundary?</h2>
            <h3>Expected</h3>
            <p className="scope-expectation">{evidence.confirmation_required ? "Confirmation required before cancellation" : "No confirmation requirement recorded"}</p>
            <h3>Observed</h3>
            <p className="scope-observation"><i className="scope-observation-dot" />{evidence.confirmation_observed ? "Confirmation observed" : "No confirmation"}</p>
            <ul className="scope-actions">{(evidence.executed_actions || []).map((action, index) => <li key={`${action}-${index}`}>{action}</li>)}</ul>
            {evidence.state_change && <p className="scope-observation"><i className="scope-observation-dot" />state changed</p>}
          </div>
          <div className="scope-provenance">
            <h3>Evidence provenance</h3>
            {[['run id', selected.run_id], ['artifact id', selected.artifact_id], ['condition', selected.condition], ['capability', selected.capability], ['restraint', selected.restraint], ['run-level verdict', selected.boundary]].map(([label, value]) => <div className="scope-provenance-row" key={label}><span>{label}</span><code>{value || "Not recorded"}</code></div>)}
            <div className="scope-evidence">
              <div><dt>Task completed</dt><dd>{String(evidence.task_completed ?? false)}</dd></div>
              <div><dt>Restraint breach</dt><dd>{String(evidence.restraint_violation ?? false)}</dd></div>
            </div>
            <div className="scope-recommendation">Recommendation: {selected.boundary === "autonomous" ? "AUTONOMOUS" : selected.boundary === "blocked" ? "BLOCKED" : "HUMAN APPROVAL"}</div>
          </div>
        </div>
      )}
    </section>
  );
}
function EnvironmentHealth() {
  const [state, setState] = useState<any>();
  const [starting, setStarting] = useState(false);
  const [message, setMessage] = useState("");
  const healthChecks = [
    ["target", "Target"],
    ["model_relay", "Model relay"],
  ] as const;
  useEffect(() => {
    const load = () =>
      api
        .getEnvStatus()
        .then(setState)
        .catch(() => setState(undefined));
    load();
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, []);
  const startEnvironment = () => {
    setStarting(true);
    setMessage("");
    api.startEnvironment().then(() => setMessage("started")).catch((e) => setMessage(e.message)).finally(() => setStarting(false));
  };
  const healthy = state
    ? healthChecks.filter(([key]) => state[key]?.status === "ready").length
    : 0;
  return (
    <section className="environment-health" aria-label="Environment health">
      <div className="health-heading">
        <strong>Environment</strong>
        <span>{state ? `${healthy}/${healthChecks.length} healthy` : "checking?"}</span>
        <button className="environment-start" onClick={startEnvironment} disabled={starting}>{starting ? "Starting..." : "Start environment"}</button>
      </div>
      {message && <small className="environment-message">{message}</small>}
      <div className="health-grid">
        {healthChecks.map(([key, name]) => {
          const item = state?.[key] || { status: "checking" };
          const healthLabel = `${name}: ${String(item.status).replace(/_/g, " ")}${
            item.latency_ms != null ? ` (${item.latency_ms} ms)` : ""
          }`;
          return (
            <div
              className={`health-item ${item.status}`}
              key={key}
              data-tooltip={healthLabel}
              aria-label={healthLabel}
              tabIndex={0}
            >
              <i />
              <span>{name}</span>
              <b>{item.status.replace("_", " ")}</b>
              {item.latency_ms != null && <small>{item.latency_ms} ms</small>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
function Config({
  scenarios,
  start,
}: {
  scenarios: Scenario[];
  start: (x: object) => void;
}) {
  const [scenario, setScenario] = useState("");
  const [model, setModel] = useState("deepseek-flash");
  const [provider, setProvider] = useState("deepseek");
  const [runs, setRuns] = useState(1);
  const [workers, setWorkers] = useState(1);
  const [advanced, setAdvanced] = useState(false);
  const [reset, setReset] = useState(true);
  const [enforcePolicy, setEnforcePolicy] = useState(false);
  const [maxSteps, setMaxSteps] = useState("");
  const [maxTokens, setMaxTokens] = useState("");
  const [budget, setBudget] = useState("20000");
  const [temp, setTemp] = useState("0.2");
  const [seed, setSeed] = useState("42");
  const [timeout, setTimeoutValue] = useState("120");
  const [target, setTarget] = useState("http://127.0.0.1:3001");
  useEffect(() => {
    if (!scenario && scenarios[0]) setScenario(scenarios[0].id);
  }, [scenario, scenarios]);
  const selected = scenarios.find((s) => s.id === scenario);
  const n = (x: string) => (x ? Number(x) : undefined);
  return (
    <form
      className="config-form quick-run-form"
      onSubmit={(e) => {
        e.preventDefault();
        start({
          scenario,
          model,
          provider,
          runs_per_worker: runs,
          parallel_workers: workers,
          reset_target: reset,
          enforce_policy: enforcePolicy,
          max_steps: n(maxSteps),
          max_tokens: n(maxTokens),
          run_token_budget: n(budget),
          temperature: n(temp),
          seed: n(seed),
          timeout: n(timeout),
          upstream: target,
        });
      }}
    >
      <label>
        SCENARIO
        <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.id}
            </option>
          ))}
        </select>
      </label>
      <label>
        MODEL
        <input value={model} onChange={(e) => setModel(e.target.value)} />
      </label>
      <label>
        PROVIDER
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option>deepseek</option>
          <option>ollama</option>
        </select>
      </label>
      <label>
        RUNS PER WORKER
        <input
          type="number"
          min="1"
          max="100"
          value={runs}
          onChange={(e) => setRuns(Math.max(1, Number(e.target.value)))}
        />
      </label>
      <label>
        PARALLEL WORKERS
        <input
          type="number"
          min="1"
          max="8"
          value={workers}
          onChange={(e) => setWorkers(Math.max(1, Number(e.target.value)))}
        />
      </label>
      <label>
        TARGET
        <input value={target} onChange={(e) => setTarget(e.target.value)} />
      </label>
      <label className="check-field">
        <input
          type="checkbox"
          checked={reset}
          onChange={(e) => setReset(e.target.checked)}
        />{" "}
        Reset target before each run
      </label>
      <button
        type="button"
        className="advanced-toggle"
        aria-expanded={advanced}
        onClick={() => setAdvanced((value) => !value)}
      >
        Advanced {advanced ? "−" : "+"}
      </button>
      {advanced && <div className="advanced-fields">
          <label>
            MAX STEPS
            <input
              type="number"
              value={maxSteps}
              onChange={(e) => setMaxSteps(e.target.value)}
            />
          </label>
          <label>
            MAX TOKENS / CALL
            <input
              type="number"
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
            />
          </label>
          <label>
            TOKEN LIMIT / RUN
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          </label>
          <label>
            TEMPERATURE
            <input
              type="number"
              step="0.1"
              value={temp}
              onChange={(e) => setTemp(e.target.value)}
            />
          </label>
          <label>
            SEED
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
            />
          </label>
          <label>
            TIMEOUT
            <input
              type="number"
              value={timeout}
              onChange={(e) => setTimeoutValue(e.target.value)}
            />
          </label>
          <label className="check-field advanced-check">
            <input
              type="checkbox"
              checked={enforcePolicy}
              disabled={!selected?.policy}
              onChange={(e) => setEnforcePolicy(e.target.checked)}
            />{" "}
            Enforce policy during run
          </label>
      </div>}
      <button className="primary" disabled={!scenario}>
        Start live run
      </button>
    </form>
  );
}
function RunList({
  runs,
  selected,
  select,
  stop,
  remove,
}: {
  runs: Run[];
  selected?: string;
  select: (r: Run) => void;
  stop: (r: Run) => void;
  remove: (r: Run) => void;
}) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const visible = runs.filter(
    (r) =>
      (status === "all" || r.status === status) &&
      (!q ||
        `${r.scenario} ${r.run_id}`.toLowerCase().includes(q.toLowerCase())),
  );
  const progress = (run: Run) => {
    const step = run.step ?? run.steps ?? 0;
    return run.max_steps ? `${step}/${run.max_steps} steps` : `${step} steps`;
  };
  return (
    <>
      <div className="run-toolbar">
        <input
          aria-label="Search runs"
          placeholder="Search runs?"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          aria-label="Filter runs by status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="running">Live</option>
          <option value="completed">Complete</option>
          <option value="partial">Partial</option>
          <option value="invalid">Invalid</option>
          <option value="failed">Failed</option>
        </select>
        <span>
          {visible.length} of {runs.length}
        </span>
      </div>
      <div className="run-list">
        {visible.length ? (
          visible.map((r) => (
            <div
              className={`run-item ${selected === r.run_id ? "selected" : ""}`}
              key={r.run_id}
              role="button"
              tabIndex={0}
              onClick={() => select(r)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") select(r);
              }}
            >
              <span className={`status-dot ${r.status}`} />
              <span className="run-copy">
                <strong>{r.scenario}</strong>
                {!TERMINAL_STATUSES.includes(r.status) && r.last_action ? (
                  <small title={r.last_action}>{r.last_action}</small>
                ) : (
                  <small title={r.run_id}>{r.run_id}</small>
                )}
              </span>
              <span className="run-stat">
                {progress(r)}
                {r.elapsed_sec != null && <small>{Math.round(r.elapsed_sec)}s elapsed</small>}
                {r.tokens_total != null && <small>{r.tokens_total} tokens</small>}
              </span>
              <span className={`status ${r.status}`} title={r.state || r.status}>
                {labels[r.status] || r.status}
                {r.state && r.state !== r.status && (
                  <small>{labels[r.state] || r.state.replace(/_/g, " ")}</small>
                )}
              </span>
              <span className="run-actions">
                {!TERMINAL_STATUSES.includes(r.status) && r.status !== "stopping" && (
                  <button
                    className="stop"
                    onClick={(e) => {
                      e.stopPropagation();
                      stop(r);
                    }}
                  >
                    stop
                  </button>
                )}
                {r.status === "invalid" && (
                  <button
                    className="delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`${r.run_id} invalid artifact? ??????`))
                        remove(r);
                    }}
                  >
                    delete
                  </button>
                )}
              </span>
              {r.status === "failed" && r.error && <small className="run-error">{r.error}</small>}
            </div>
          ))
        ) : (
          <p className="empty">No matching runs.</p>
        )}
      </div>
    </>
  );
}
function EvidenceDock({
  run,
  actions,
  live,
  hasArtifact,
}: {
  run?: Run;
  actions: Action[];
  live?: any;
  hasArtifact: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [full, setFull] = useState(false);
  const [height, setHeight] = useState(330);
  const [tab, setTab] = useState<"terminal" | "events" | "artifacts">(
    "terminal",
  );
  const [source, setSource] = useState("ALL");
  const [logs, setLogs] = useState<Log[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [file, setFile] = useState("");
  const [filesOpen, setFilesOpen] = useState(true);
  const [fileWidth, setFileWidth] = useState(255);
  const dockBody = useRef<HTMLDivElement>(null);
  const fileResize = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) =>
      setFileWidth(Math.max(170, Math.min(420, ev.clientX)));
    const done = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", done);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", done);
  };
  const resizing = useRef(false);
  useEffect(() => {
    if (!run || !hasArtifact) {
      setLogs([]);
      return;
    }
    const load = () =>
      api
        .getTerminal(run.run_id)
        .then((next) =>
          setLogs((current) =>
            JSON.stringify(current) === JSON.stringify(next) ? current : next,
          ),
        )
        .catch(() => undefined);
    load();
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [run?.run_id, hasArtifact]);
  useEffect(() => {
    if (run && hasArtifact)
      api
        .getArtifacts(run.run_id)
        .then(setArtifacts)
        .catch(() => setArtifacts([]));
    else setArtifacts([]);
  }, [run?.run_id, hasArtifact]);
  const selected = artifacts.find((a) => a.name === file) || artifacts[0];
  const filters = ["ALL", "RUNNER", "AGENT", "GATEWAY", "JUDGE", "OBSERVER"];
  const roeNames: Record<string, string> = {
    R1: "Target",
    R2: "Tool",
    R3: "Activity",
    R4: "Operation",
    R5: "Outcome",
    R6: "Halt",
  };
  const visible =
    source === "ALL" ? logs : logs.filter((x) => x.source === source);
  useEffect(() => {
    if (open && tab === "events" && dockBody.current) {
      dockBody.current.scrollTop = dockBody.current.scrollHeight;
    }
  }, [open, tab, actions.length]);
  const resize = (e: React.PointerEvent) => {
    if (full) return;
    resizing.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) =>
      setHeight(
        Math.max(
          180,
          Math.min(window.innerHeight - 70, window.innerHeight - ev.clientY),
        ),
      );
    const done = () => {
      resizing.current = false;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", done);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", done);
  };
  return (
    <section
      className={`evidence-dock ${open ? "open" : "closed"} ${full ? "fullscreen" : ""}`}
      style={open && !full ? { height } : undefined}
    >
      <div
        className="dock-resize-handle"
        onPointerDown={resize}
        title="Drag to resize"
      />
      <div className="dock-tabs">
        <button
          className={tab === "terminal" ? "active" : ""}
          onClick={() => {
            setTab("terminal");
            setOpen(true);
          }}
        >
          Terminal
        </button>
        <button
          className={tab === "events" ? "active" : ""}
          onClick={() => {
            setTab("events");
            setOpen(true);
          }}
        >
          Events
        </button>
        <button
          className={tab === "artifacts" ? "active" : ""}
          onClick={() => {
            setTab("artifacts");
            setOpen(true);
          }}
        >
          Artifacts
        </button>
        {tab === "artifacts" && (
          <button
            className={`artifact-toggle ${filesOpen ? "open" : "closed"}`}
            onClick={() => setFilesOpen(!filesOpen)}
          >
            {filesOpen ? "Hide files" : "Show files"}
          </button>
        )}
        <button
          className="dock-close"
          aria-label={open ? "Close technical evidence" : "Open technical evidence"}
          onClick={() => setOpen(!open)}
        >
          {open ? String.fromCharCode(215) : String.fromCharCode(8963)}
        </button>
        <button
          className="dock-expand"
          onClick={() => {
            setOpen(true);
            setFull(!full);
          }}
        >
          {full ? "Exit full screen" : "Full screen"}
        </button>
      </div>
      {open && (
        <div className="dock-body" ref={dockBody}>
          {tab === "terminal" && (
            <>
              <div className="source-filters">
                {filters.map((x) => (
                  <button
                    className={source === x ? "active" : ""}
                    key={x}
                    onClick={() => setSource(x)}
                  >
                    {x}
                  </button>
                ))}
              </div>
              <div className="terminal-lines">
                {visible.length ? (
                  visible.map((x, i) => (
                    <div key={i}>
                      <span className="terminal-time">
                        {x.timestamp?.slice(11, 19) || "live"}
                      </span>
                      <span
                        className={`source-${x.source.toLowerCase()} ${x.text.includes("ESCAPED") ? "bad" : ""}`}
                      >
                        <b>{x.source}</b> {x.text}
                      </span>
                    </div>
                  ))
                ) : (
                  <span className="terminal-muted">No {source} records.</span>
                )}
              </div>
            </>
          )}
          {tab === "events" && (
            <div className="events-table">
              <div className="event-head">
                <span>SEQ</span>
                <span>ACTION ID</span>
                <span>REQUEST</span>
                <span>DECISION</span>
                <span>ROE VIOLATION</span>
              </div>
              {actions.map((a, i) => (
                <div className="event-row" key={a.action_id}>
                  <span>{i + 1}</span>
                  <span>{a.action_id}</span>
                  <span className="event-request">
                    <span>
                      {a.method || "ACTION"} {a.path || "-"}
                    </span>
                    {a.thought && <small>{a.thought}</small>}
                    {a.thought &&
                      a.roe_status === "escaped" &&
                      [
                        "\uC778\uAC00",
                        "\uAD8C\uD55C",
                        "\uAE08\uC9C0",
                        "\uC704\uD5D8",
                        "\uBC94\uC704",
                        "\uBE44\uC778\uAC00",
                        "\uC778\uC99D",
                        "\uD5C8\uAC00",
                        "\uC81C\uD55C",
                        "unauthorized",
                        "forbidden",
                        "restricted",
                      ].some((k) => a.thought?.includes(k)) && (
                        <b>{"\u26A0"} Aware Escape</b>
                      )}
                  </span>
                  <EventDecision status={a.decision} />
                  <span
                    className={
                      a.roe_status === "escaped"
                        ? "bad"
                        : a.roe_status === "allowed" || a.roe_status === "goal"
                          ? "good"
                          : "terminal-muted"
                    }
                  >
                    {a.roe_status === "escaped"
                      ? (a.roe_categories || [a.roe_category || "ROE"])
                          .map((c) => c + " " + (roeNames[c] || "violation"))
                          .join(String.fromCharCode(183))
                      : a.roe_status || "pending"}
                  </span>
                </div>
              ))}
            </div>
          )}
          {tab === "artifacts" && (
            <div
              className={`artifact-view ${filesOpen ? "" : "files-hidden"}`}
              style={
                { "--file-width": `${fileWidth}px` } as React.CSSProperties
              }
            >
              <div className="artifact-list">
                {artifacts.map((a) => (
                  <button
                    className={`${selected?.name === a.name ? "active" : ""} ${a.name.startsWith("evidence/") ? "evidence-file" : a.name.endsWith(".jsonl") ? "log-file" : "config-file"}`}
                    key={a.name}
                    onClick={() => setFile(a.name)}
                  >
                    {a.name}
                  </button>
                ))}
              </div>
              <div className="artifact-sash" onPointerDown={fileResize} />
              <pre
                dangerouslySetInnerHTML={{
                  __html: highlightJson(
                    selected?.content || "No artifacts available.",
                  ),
                }}
              />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
function EventDecision({ status }: { status?: string }) {
  const value = status || "-";
  return (
    <span className={`event-decision ${value}`}>
      {value === "goal" ? String.fromCharCode(9733) + " goal" : value}
    </span>
  );
}
function RoeSummary({ run, actions }: { run: Run; actions: Action[] }) {
  const names = ["R1", "R2", "R3", "R4", "R5", "R6"];
  return (
    <div className="roe-summary">
      <span>ROE</span>
      <div className="roe-categories">
        {names.map((c) => {
          const category = run.roe_categories?.[c];
          const count =
            category?.violation_count ??
            actions.filter(
              (a) =>
                a.roe_status === "escaped" &&
                (a.roe_categories || [a.roe_category]).includes(c),
            ).length;
          return (
            <span className={count > 0 ? "failed" : "passed"} key={c}>
              {c}
              {count > 0 && (
                <b>
                  {String.fromCharCode(215)}
                  {count}
                </b>
              )}
            </span>
          );
        })}
      </div>
    </div>
  );
}
// Distinct from the Events tab's per-action table (method/path + thought row):
// this is a narrative "what is it thinking right now" ticker, not another log.
function LiveThought({
  actions,
  terminal,
}: {
  actions: Action[];
  terminal?: boolean;
}) {
  const [latest, ...rest] = [...actions]
    .filter((a) => a.thought)
    .sort((a, b) => b.seq - a.seq);
  const trail = rest.slice(0, 2);
  return (
    <div className={`live-thought ${terminal ? "terminal" : ""}`}>
      <span className="live-thought-title">
        {terminal ? <i className="static-dot" /> : <i className="live-dot" />}
        {terminal ? "Last activity" : "Thinking now"}
      </span>
      {latest ? (
        <>
          <p className="live-thought-current">{"“"}{latest.thought}{"”"}</p>
          {trail.length > 0 && (
            <ul className="live-thought-trail">
              {trail.map((a) => (
                <li key={a.action_id}>{a.thought}</li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <p className="live-thought-empty">No reasoning captured yet.</p>
      )}
    </div>
  );
}
const ROE_NAMES: Record<string, string> = {
  R1: "Target",
  R2: "Tool",
  R3: "Activity",
  R4: "Operation",
  R5: "Outcome",
  R6: "Halt",
};
const ROE_ORDER = ["R1", "R2", "R3", "R4", "R5", "R6"];
const shortRunId = (runId: string) => {
  const match = /-([0-9a-f]{8})-r\d+$/.exec(runId);
  return match ? match[1] : runId.slice(-8);
};
function ScenarioProgressBar({
  steps,
  maxSteps,
  goalStep,
  goalSuccess,
  violationSteps,
}: {
  steps: number;
  maxSteps: number;
  goalStep?: number | null;
  goalSuccess?: boolean;
  violationSteps: number[];
}) {
  const pct = (n: number) =>
    maxSteps > 0 ? Math.max(0, Math.min(100, (n / maxSteps) * 100)) : 0;
  const tone =
    goalSuccess === true ? "good" : goalSuccess === false ? "bad" : "neutral";
  return (
    <div
      className="scenario-progress-track"
      role="img"
      aria-label={`${steps} of ${maxSteps} steps`}
    >
      <div
        className={`scenario-progress-fill ${tone}`}
        style={{ width: `${pct(steps)}%` }}
      />
      {goalStep != null && (
        <div
          className="scenario-progress-goal"
          style={{ left: `${pct(goalStep)}%` }}
          title={`Goal reached at step ${goalStep}`}
        />
      )}
      {violationSteps.map((step, i) => (
        <div
          className="scenario-progress-violation"
          key={i}
          style={{ left: `${pct(step)}%` }}
          title={`ROE violation at step ${step}`}
        />
      ))}
    </div>
  );
}
function ScenarioRunRow({
  run,
  index,
  maxSteps,
  overlay,
  onOpen,
}: {
  run: Run;
  index: number;
  maxSteps: number;
  overlay?: RunOverlay;
  onOpen: (r: Run) => void;
}) {
  const violationSteps = (overlay?.roe_violations || [])
    .filter((v) => v.severity !== "unclassified" && v.step != null)
    .map((v) => v.step as number);
  const goalTone =
    run.goal_success === true ? "good" : run.goal_success === false ? "bad" : "";
  const violatedCategories = ROE_ORDER.filter(
    (c) => (run.roe_categories?.[c]?.violation_count ?? 0) > 0,
  );
  return (
    <div
      className="scenario-run-row"
      role="button"
      tabIndex={0}
      onClick={() => onOpen(run)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onOpen(run);
      }}
    >
      <span className="scenario-run-index">#{index + 1}</span>
      <span className="scenario-run-id" title={run.run_id}>
        {shortRunId(run.run_id)}
      </span>
      <span
        className={`scenario-goal-dot ${goalTone}`}
        title={
          run.goal_success == null
            ? "Goal pending"
            : run.goal_success
              ? "Goal reached"
              : "Goal not reached"
        }
      />
      <ScenarioProgressBar
        steps={run.steps ?? 0}
        maxSteps={maxSteps}
        goalStep={run.goal_step}
        goalSuccess={run.goal_success}
        violationSteps={violationSteps}
      />
      {violatedCategories.length ? (
        <span className="scenario-roe-badge bad">
          {violatedCategories.join(String.fromCharCode(183))}
        </span>
      ) : (
        <span className="scenario-roe-badge good" title="No ROE violations">
          <i className="scenario-check" />
        </span>
      )}
      <span className="scenario-run-stats">
        {run.steps ?? 0} steps
        {run.tokens_total != null && <small>{run.tokens_total} tokens</small>}
      </span>
    </div>
  );
}
function ScenarioSummaryTab({
  runs,
  overlays,
  onOpenRun,
}: {
  runs: Run[];
  overlays: Record<string, RunOverlay | undefined>;
  onOpenRun: (run: Run) => void;
}) {
  const [roeFilter, setRoeFilter] = useState<string | null>(null);
  const total = runs.length;
  const goalReached = runs.filter((r) => r.goal_success).length;
  const goalRate = total ? Math.round((goalReached / total) * 100) : 0;
  const avgSteps = total
    ? runs.reduce((sum, r) => sum + (r.steps ?? 0), 0) / total
    : 0;
  const roeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    ROE_ORDER.forEach((c) => (counts[c] = 0));
    runs.forEach((r) => {
      ROE_ORDER.forEach((c) => {
        counts[c] += r.roe_categories?.[c]?.violation_count ?? 0;
      });
    });
    return counts;
  }, [runs]);
  const topRoe = ROE_ORDER.reduce(
    (best, c) => (roeCounts[c] > (roeCounts[best] || 0) ? c : best),
    ROE_ORDER[0],
  );
  const maxRoeCount = Math.max(1, ...ROE_ORDER.map((c) => roeCounts[c]));
  const maxSteps = Math.max(1, ...runs.map((r) => r.max_steps ?? 0));
  const visibleRuns = roeFilter
    ? runs.filter((r) => (r.roe_categories?.[roeFilter]?.violation_count ?? 0) > 0)
    : runs;
  return (
    <div className="scenario-summary">
      <div className="scenario-metrics">
        <Metric label="Goal success rate" value={`${goalReached} / ${total} · ${goalRate}%`} />
        <Metric
          label="Most violated ROE"
          value={roeCounts[topRoe] > 0 ? `${topRoe} · ${roeCounts[topRoe]}` : "None"}
        />
        <Metric label="Average steps" value={`avg ${avgSteps.toFixed(1)}`} />
      </div>
      <section className="card scenario-roe-pattern">
        <div className="card-title">
          <span>ROE pattern</span>
          {roeFilter && (
            <button
              type="button"
              className="scenario-roe-clear"
              onClick={() => setRoeFilter(null)}
            >
              Clear filter
            </button>
          )}
        </div>
        <div className="scenario-roe-list">
          {ROE_ORDER.map((c) => {
            const count = roeCounts[c];
            const ratio = (count / maxRoeCount) * 100;
            return (
              <button
                type="button"
                key={c}
                className={`scenario-roe-item ${roeFilter === c ? "active" : ""}`}
                onClick={() => setRoeFilter((f) => (f === c ? null : c))}
              >
                <span className="scenario-roe-name">
                  {c} {ROE_NAMES[c]}
                </span>
                <span className="scenario-roe-bar-track">
                  <span
                    className="scenario-roe-bar-fill"
                    style={{ width: `${count > 0 ? Math.max(4, ratio) : 0}%` }}
                  />
                </span>
                <span className="scenario-roe-count">{count}</span>
              </button>
            );
          })}
        </div>
      </section>
      <section className="card scenario-run-timeline">
        <div className="card-title">
          <span>Run timeline</span>
          <small>
            {visibleRuns.length} of {total} runs
          </small>
        </div>
        {visibleRuns.length ? (
          <div className="scenario-run-list">
            {visibleRuns.map((r, i) => (
              <ScenarioRunRow
                key={r.run_id}
                run={r}
                index={i}
                maxSteps={maxSteps}
                overlay={overlays[r.run_id]}
                onOpen={onOpenRun}
              />
            ))}
          </div>
        ) : (
          <p className="empty">No runs match this filter.</p>
        )}
      </section>
    </div>
  );
}

function DualTrack({
  run,
  actions,
  overlay,
}: {
  run: Run;
  actions: Action[];
  overlay?: RunOverlay;
}) {
  const max = Math.max(
    1,
    run.max_steps ?? 0,
    run.steps ?? 0,
    ...actions.map((action) => action.seq + 1),
  );
  const pct = (seq: number) => `${Math.max(0, Math.min(100, (seq / max) * 100))}%`;
  const stages = overlay?.capability_stages || [];
  const violations = overlay?.roe_violations || [];
  return (
    <section className="card dual-track-card">
      <div className="card-title">
        <span>Run path</span>
        <div className="dual-track-legend">
          <span><i className="legend-capability" /> Capability</span>
          <span><i className="legend-restraint" /> Restraint</span>
        </div>
      </div>
      <div className="dual-track-wrap capability-plot" role="img" aria-label="Capability and restraint timeline">
        <div className="plot-group-label">CAPABILITY</div>
        <div className="plot-lanes">
          {/* capability lanes are rendered below */}
          {/*
          {stages.length ? stages.map((stage, index) => {
            const start = stage.start_seq ?? index;
            const end = stage.end_seq ?? start + 1;
            const y = 20 + index * 22;
            return (
              <g key={`${stage.name}-${index}`}>
                <text x="8" y={y + 5} className="stage-row-label">{stage.name}</text>
                <line x1="160" y1={y} x2="726" y2={y} className="track-base" />
                <rect x={x(start)} y={y - 8} width={Math.max(8, x(end) - x(start))} height="16" rx="8" className="capability-segment" />
                <title>{stage.name}: steps {start}–{end}</title>
              </g>
            );
          }) : (
            <g>
              <text x="8" y="29" className="stage-row-label">CAPABILITY</text>
              <line x1="160" y1="24" x2="726" y2="24" className="track-base" />
              <rect x="160" y="16" width={Math.max(8, x(run.steps ?? 0) - 160)} height="16" rx="8" className="capability-segment" />
            </g>
          )}
          {(() => {
            const restraintY = stages.length ? stages.length * 22 + 27 : 62;
            return <>
              <text x="8" y={restraintY + 5} className="track-label">RESTRAINT</text>
              <line x1="160" y1={restraintY} x2="726" y2={restraintY} className="track-base" />
              {actions.map((action) => {
                const blocked = action.decision === "blocked" || action.roe_status === "blocked";
                const escaped = action.roe_status === "escaped";
                return <circle key={action.action_id} cx={x(action.seq)} cy={restraintY} r={escaped ? 5 : 4} className={escaped ? "restraint-dot escaped" : blocked ? "restraint-dot blocked" : "restraint-dot"} />;
              })}
              {violations.map((violation, index) => violation.step != null && (
                <line key={`violation-${index}`} x1={x(violation.step)} y1={restraintY - 12} x2={x(violation.step)} y2={restraintY + 12} className="violation-marker" />
              ))}
              <line x1="160" y1={restraintY + 28} x2="726" y2={restraintY + 28} className="track-axis" />
              <text x="160" y={restraintY + 42} className="axis-label">0</text>
              <text x="718" y={restraintY + 42} className="axis-label">{max}</text>
            </>;
          })()}
          */}
          {(stages.length ? stages : [{ name: "Execution", start_seq: 0, end_seq: run.steps ?? 0 }]).map((stage, index) => {
            const start = stage.start_seq ?? index;
            const end = stage.end_seq ?? start + 1;
            return (
              <div className="plot-lane" key={`${stage.name}-${index}`}>
                <span className="plot-lane-name">{stage.name}</span>
                <div className="plot-track">
                  <span className="plot-grid" />
                  <span className="plot-capability-bar" style={{ left: pct(start), width: `max(8px, calc(${pct(end)} - ${pct(start)}))` }} title={`${stage.name}: steps ${start} to ${end}`} />
                </div>
              </div>
            );
          })}
        </div>
        <div className="plot-group-label restraint-label">RESTRAINT</div>
        <div className="plot-lane restraint-lane">
          <span className="plot-lane-name">Events</span>
          <div className="plot-track">
            <span className="plot-grid" />
            {actions.map((action) => {
              const blocked = action.decision === "blocked" || action.roe_status === "blocked";
              const escaped = action.roe_status === "escaped";
              return <span key={action.action_id} className={`plot-event-dot ${escaped ? "escaped" : blocked ? "blocked" : ""}`} style={{ left: pct(action.seq) }} title={`Step ${action.seq + 1}`} />;
            })}
            {violations.map((violation, index) => violation.step != null && (
              <span key={`violation-${index}`} className="plot-violation" style={{ left: pct(violation.step) }} />
            ))}
          </div>
        </div>
        <div className="plot-axis"><span>0</span><span>{max} steps</span></div>
      </div>
      <div className="run-path-compact">
        <div className="run-path-heading">
          <span>Capability</span>
          <small>{stages.length || 0} phases · {max} steps</small>
        </div>
        <div className="run-path-flow">
          {(stages.length ? stages : [{ name: "Execution", start_seq: 0, end_seq: run.steps ?? 0 }]).map((stage, index) => (
            <div className="run-path-stage" key={`${stage.name}-compact-${index}`}>
              <span className="run-path-index">{String(index + 1).padStart(2, "0")}</span>
              <b>{stage.name}</b>
              <small>{stage.start_seq ?? 0}–{stage.end_seq ?? stage.start_seq ?? 0}</small>
            </div>
          ))}
        </div>
        <div className="run-path-heading restraint-heading">
          <span>Restraint</span>
          <small>{violations.length} violations · {actions.length} events</small>
        </div>
        <div className="run-path-rail">
          <div className="run-path-rail-line" />
          {actions.map((action) => {
            const escaped = action.roe_status === "escaped";
            const blocked = action.decision === "blocked" || action.roe_status === "blocked";
            return <i key={action.action_id} className={escaped ? "escaped" : blocked ? "blocked" : ""} style={{ left: pct(action.seq) }} title={`Step ${action.seq + 1}`} />;
          })}
        </div>
        <div className="run-path-axis"><span>0</span><span>{max}</span></div>
      </div>
      <div className="dual-track-stages" aria-label="Capability stages">
        {stages.length ? stages.map((stage, index) => (
          <span key={`${stage.name}-legend-${index}`}><i>{index + 1}</i>{stage.name}</span>
        )) : <span className="stage-empty">No capability stages recorded</span>}
      </div>
    </section>
  );
}

function RawHttp({ action }: { action: Action }) {
  const raw = action.raw_action || {};
  const method = String(raw.method || action.method || "ACTION");
  const path = String(raw.path || action.path || "/");
  const status = action.status_code ? `HTTP/1.1 ${action.status_code}` : "HTTP/1.1 —";
  const headers = raw.headers && typeof raw.headers === "object" ? raw.headers as Record<string, unknown> : {};
  const headerLines = Object.entries(headers).map(([key, value]) => `${key}: ${String(value)}`);
  const body = raw.body ?? raw.json ?? raw.data;
  const bodyText = body == null ? "" : typeof body === "string" ? body : JSON.stringify(body, null, 2);
  return <pre className="raw-http">{`${method} ${path} HTTP/1.1\n${headerLines.length ? `${headerLines.join("\\n")}\\n` : "Host: target\\n"}X-Tempera-Decision: ${action.decision || "unclassified"}\\n\\n${bodyText || status}`}</pre>;
}

function ActionSlideOver({
  action,
  onClose,
}: {
  action: Action;
  onClose: () => void;
}) {
  const roe = action.roe_categories?.length
    ? action.roe_categories.join(" · ")
    : action.roe_dimension || action.roe_status || "Clear";
  return (
    <>
      <button className="action-drawer-backdrop" aria-label="Close action details" onClick={onClose} />
      <aside className="action-drawer" aria-label="Action details">
        <div className="action-drawer-head">
          <div>
            <span className="eyebrow">ACTION {action.seq + 1}</span>
            <h2>{action.method || "ACTION"} {action.path || "Unknown path"}</h2>
          </div>
          <button type="button" className="action-drawer-close" onClick={onClose}>×</button>
        </div>
        <div className="action-drawer-body">
          <section className="drawer-section">
            <h3>Thought</h3>
            <p className="thought-block">{action.thought || "No thought was captured for this action."}</p>
          </section>
          <section className="drawer-facts">
            <div><span>ROE</span><b className={action.roe_status === "escaped" ? "bad" : "good"}>{roe}</b></div>
            <div><span>Guardrail</span><b>{action.decision || "Not evaluated"}</b></div>
            <div><span>Phase</span><b>{action.phase || "Observed"}</b></div>
            <div><span>Status</span><b>{action.status_code ?? "—"}</b></div>
          </section>
          {action.decision_reason && (
            <section className="drawer-section">
              <h3>Guardrail reason</h3>
              <p>{action.decision_reason}</p>
            </section>
          )}
          <section className="drawer-section">
            <h3>Raw HTTP</h3>
            <RawHttp action={action} />
          </section>
        </div>
      </aside>
    </>
  );
}

function RunInspector({ run }: { run: Run }) {
  const [actions, setActions] = useState<Action[]>([]);
  const [overlay, setOverlay] = useState<RunOverlay>();
  const [selectedAction, setSelectedAction] = useState<Action>();
  useEffect(() => {
    setActions([]);
    setOverlay(undefined);
    setSelectedAction(undefined);
    api.getActions(run.run_id).then(setActions).catch(() => setActions([]));
    api.getOverlay(run.run_id).then(setOverlay).catch(() => setOverlay(undefined));
  }, [run.run_id]);
  const violationCount = actions.filter((action) => action.roe_status === "escaped").length;
  return (
    <div className="run-inspector">
      <section className="detail-overview run-inspector-overview">
        <div className="detail-identity">
          <span className={`status-dot ${run.status}`} />
          <div><small>{run.scenario || "Unknown scenario"}</small><h2>{run.run_id}</h2><span className={`status ${run.status}`}>{labels[run.status] || run.status}</span></div>
        </div>
        <Metric label="Goal" value={run.goal_success ? "Reached" : run.goal_success === false ? "Not reached" : "Pending"} tone={run.goal_success ? "good" : ""} />
        <Metric label="ROE" value={run.roe_compliant ? "Compliant" : run.roe_compliant === false ? "Violated" : "Pending"} tone={run.roe_compliant === false ? "bad" : run.roe_compliant ? "good" : ""} />
        <Metric label="Steps" value={String(run.steps ?? 0)} />
        <Metric label="Violations" value={String(run.violation_count ?? violationCount)} tone={violationCount ? "bad" : "good"} />
      </section>
      <DualTrack run={run} actions={actions} overlay={overlay} />
      <section className="card run-events-card">
        <div className="card-title"><span>Events</span><small>{actions.length} actions · click a row for full evidence</small></div>
        <div className="events-table run-events-table">
          <div className="event-head"><span>#</span><span>Action</span><span>Thought</span><span>Guardrail</span><span>ROE</span></div>
          {actions.length ? actions.map((action) => (
            <button type="button" className="event-row event-row-button" key={action.action_id} onClick={() => setSelectedAction(action)}>
              <span>{action.seq + 1}</span>
              <span className="event-request"><span><b>{action.method || "ACTION"}</b> {action.path || "—"}</span><small>{action.status_code ?? "no response"}</small></span>
              <span className="event-thought">{action.thought || "No thought captured"}</span>
              <EventDecision status={action.decision} />
              <EventDecision status={action.roe_status} />
            </button>
          )) : <p className="empty">No events recorded for this run yet.</p>}
        </div>
      </section>
      {selectedAction && <ActionSlideOver action={selectedAction} onClose={() => setSelectedAction(undefined)} />}
    </div>
  );
}

function RunDetailChooser({
  runs,
  navigate,
}: {
  runs: Run[];
  navigate: (route: Route) => void;
}) {
  const [query, setQuery] = useState("");
  const groups = [...new Set(runs.map((run) => run.scenario || "Unknown scenario"))];
  const visibleGroups = groups.filter((scenario) => scenario.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <section className="card run-detail-chooser">
      <div className="card-title">
        <div className="run-detail-chooser-heading">
          <strong>Choose a scenario</strong>
          <small>{runs.length} runs across {groups.length} scenarios</small>
        </div>
        <label className="scenario-search">
          <span aria-hidden="true">⌕</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search scenarios" aria-label="Search scenarios" />
        </label>
      </div>
      <div className="run-detail-chooser-body">
        {visibleGroups.length ? visibleGroups.map((scenario) => {
          const scenarioRuns = runs.filter((run) => (run.scenario || "Unknown scenario") === scenario);
          return (
            <button
              type="button"
              className="run-detail-chooser-item"
              key={scenario}
              onClick={() => navigate({ page: "detail", scenarioId: scenario })}
            >
              <span className="scenario-card-mark" aria-hidden="true">{scenario.slice(0, 1)}</span>
              <span className="run-detail-chooser-copy">
                <strong>{scenario}</strong>
                <small>{scenarioRuns[0]?.model || "Unknown model"}</small>
              </span>
              <span className="scenario-run-count">{scenarioRuns.length} <small>runs</small></span>
              <span aria-hidden="true">→</span>
            </button>
          );
        }) : <p className="empty">{query ? "No matching scenarios." : "No runs recorded yet. Start a live run first."}</p>}
      </div>
    </section>
  );
}

function RunDetailPage({
  scenarioId,
  navigate,
}: {
  scenarioId?: string;
  navigate: (r: Route) => void;
}) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [overlays, setOverlays] = useState<Record<string, RunOverlay | undefined>>({});
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("summary");
  const [openRunIds, setOpenRunIds] = useState<string[]>([]);
  useEffect(() => {
    setOverlays({});
    setLoading(true);
    api
      .getRuns(scenarioId)
      .then((next: Run[]) => {
        setRuns(next);
        if (scenarioId) {
          next.forEach((r) =>
            api
              .getOverlay(r.run_id)
              .then((overlay: RunOverlay) =>
                setOverlays((o) => ({ ...o, [r.run_id]: overlay })),
              )
              .catch(() => undefined),
          );
        }
      })
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, [scenarioId]);
  useEffect(() => {
    setActiveTab("summary");
    setOpenRunIds([]);
  }, [scenarioId]);
  const openRun = (run: Run) => {
    setOpenRunIds((current) => current.includes(run.run_id) ? current : [...current, run.run_id]);
    setActiveTab(run.run_id);
  };
  const closeRunTab = (runId: string) => {
    setOpenRunIds((current) => current.filter((id) => id !== runId));
    if (activeTab === runId) setActiveTab("summary");
  };
  const model = runs.find((r) => r.model)?.model;
  return (
    <main className="detail-page" aria-label="Run Detail">
      <div className="scenario-breadcrumb">
        <button
          type="button"
          className="scenario-breadcrumb-back"
          onClick={() => navigate(scenarioId ? { page: "detail" } : { page: "live" })}
        >
          {String.fromCharCode(8592)} {scenarioId ? "All scenarios" : "Live Run"}
        </button>
        {scenarioId && (
          <>
            <span className="scenario-breadcrumb-sep">·</span>
            <strong>{scenarioId}</strong>
            <span className="scenario-breadcrumb-sep">·</span>
            <span>{model || "Unknown model"}</span>
            <span className="scenario-breadcrumb-sep">·</span>
            <span>{runs.length} runs</span>
          </>
        )}
      </div>
      {scenarioId && (
        <nav className="scenario-tabs" aria-label="Run detail tabs">
          <button className={activeTab === "summary" ? "active" : ""} onClick={() => setActiveTab("summary")}>Scenario summary</button>
          {openRunIds.map((runId) => {
            const run = runs.find((item) => item.run_id === runId);
            if (!run) return null;
            return (
              <button className={`run-detail-tab ${activeTab === runId ? "active" : ""}`} key={runId} onClick={() => setActiveTab(runId)}>
                <span>{shortRunId(runId)}</span>
                <i aria-label={`Close ${shortRunId(runId)} tab`} onClick={(event) => { event.stopPropagation(); closeRunTab(runId); }}>×</i>
              </button>
            );
          })}
        </nav>
      )}
      {!scenarioId ? (
        loading ? <p className="empty">Loading available runs...</p> : <RunDetailChooser runs={runs} navigate={navigate} />
      ) : loading && !runs.length ? (
        <p className="empty">Loading scenario runs...</p>
      ) : runs.length ? (
        activeTab === "summary" ? (
          <ScenarioSummaryTab runs={runs} overlays={overlays} onOpenRun={openRun} />
        ) : (() => {
          const run = runs.find((item) => item.run_id === activeTab);
          return run ? <RunInspector run={run} /> : <ScenarioSummaryTab runs={runs} overlays={overlays} onOpenRun={openRun} />;
        })()
      ) : (
        <p className="empty">No runs recorded for {scenarioId} yet.</p>
      )}
    </main>
  );
}

function RunDetailContent({
  runs,
  run,
  actions,
  select,
}: {
  runs: Run[];
  run?: Run;
  actions: Action[];
  select: (r: Run) => void;
}) {
  const [detail, setDetail] = useState<any>();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  useEffect(() => {
    if (!run) {
      setDetail(undefined);
      setArtifacts([]);
      return;
    }
    api
      .getDetail(run.run_id)
      .then(setDetail)
      .catch(() => setDetail(undefined));
    api
      .getArtifacts(run.run_id)
      .then(setArtifacts)
      .catch(() => setArtifacts([]));
  }, [run?.run_id]);
  const summary = detail?.summary || run;
  const overlay = detail?.overlay;
  return (
    <main className="detail-page" aria-label="Run Detail">
      <div className="detail-heading">
        <div>
          <span className="eyebrow">BENCHMARK CONSOLE</span>
          <h1>Run Detail</h1>
          <p>
            Inspect outcomes, policy decisions, and evidence from a benchmark
            run.
          </p>
        </div>
        <label>
          RUN
          <select
            value={run?.run_id || ""}
            onChange={(e) => {
              const next = runs.find((r) => r.run_id === e.target.value);
              if (next) select(next);
            }}
          >
            <option value="" disabled>
              Select a run
            </option>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.scenario || "Unknown"} — {r.run_id}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!run ? (
        <section className="card detail-empty">
          <strong>No runs available yet</strong>
          <p>
            Start a live run first. It will appear here as soon as its artifact
            directory is created.
          </p>
        </section>
      ) : (
        <>
          <section className="detail-overview">
            <div className="detail-identity">
              <span className={`status-dot ${summary?.status}`} />
              <div>
                <small>{summary?.scenario || "Unknown scenario"}</small>
                <h2>{summary?.run_id}</h2>
                <span className={`status ${summary?.status}`}>
                  {labels[summary?.status] || summary?.status}
                </span>
              </div>
            </div>
            <Metric
              label="Goal"
              value={
                summary?.goal_success == null
                  ? "Pending"
                  : summary.goal_success
                    ? "Reached"
                    : "Not reached"
              }
              tone={summary?.goal_success ? "good" : ""}
            />
            <Metric
              label="ROE"
              value={
                summary?.roe_compliant == null
                  ? "Pending"
                  : summary.roe_compliant
                    ? "Compliant"
                    : "Violated"
              }
              tone={
                summary?.roe_compliant
                  ? "good"
                  : summary?.roe_compliant === false
                    ? "bad"
                    : ""
              }
            />
            <Metric label="Steps" value={String(summary?.steps ?? 0)} />
            <Metric
              label="Tokens"
              value={summary?.tokens_total?.toLocaleString?.() || "—"}
            />
            <Metric
              label="Duration"
              value={
                summary?.duration_sec != null
                  ? `${Math.round(summary.duration_sec)}s`
                  : "—"
              }
            />
          </section>
          <div className="detail-grid">
            <section className="card detail-panel">
              <div className="card-title">
                <span>ROE assessment</span>
                <small>{summary?.violation_count ?? 0} violations</small>
              </div>
              <div className="detail-panel-body">
                <RoeSummary run={summary} actions={actions} />
                {summary?.termination_reason && (
                  <p className="termination">
                    <b>Termination</b>
                    {summary.termination_reason}
                  </p>
                )}
              </div>
            </section>
            <section className="card detail-panel">
              <div className="card-title">
                <span>Evidence</span>
                <small>{artifacts.length} artifacts</small>
              </div>
              <div className="evidence-stats">
                <Metric label="Actions" value={String(actions.length)} />
                <Metric
                  label="Phases"
                  value={String(overlay?.phases?.length ?? 0)}
                />
                <Metric
                  label="Violations"
                  value={String(
                    overlay?.roe_violations?.length ??
                      summary?.violation_count ??
                      0,
                  )}
                />
              </div>
            </section>
          </div>
          <section className="card detail-actions">
            <div className="card-title">
              <span>Action timeline</span>
              <small>{actions.length} actions</small>
            </div>
            {actions.length ? (
              <div className="detail-action-table">
                <div className="detail-action-head">
                  <span>#</span>
                  <span>Request</span>
                  <span>Decision</span>
                  <span>ROE</span>
                  <span>Tokens</span>
                </div>
                {actions.map((a, i) => (
                  <div className="detail-action-row" key={a.action_id}>
                    <span>{i + 1}</span>
                    <span>
                      <b>{a.method || "ACTION"}</b> {a.path || "—"}
                      <small>{a.action_id}</small>
                    </span>
                    <EventDecision status={a.roe_status} />
                    <span
                      className={a.roe_status === "escaped" ? "bad" : "good"}
                    >
                      {a.roe_status === "escaped"
                        ? (a.roe_categories || [a.roe_category || "ROE"]).join(
                            ", ",
                          )
                        : "Clear"}
                    </span>
                    <span>
                      {a.total_tokens != null ? a.total_tokens : "—"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty">No actions recorded for this run yet.</p>
            )}
          </section>
        </>
      )}
    </main>
  );
}
function Metric({
  label,
  value,
  tone = "",
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className={`detail-metric ${tone}`}>
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}
type Route = { page: "live" } | { page: "detail"; scenarioId?: string };
const parseRoute = (pathname: string): Route => {
  const m = /^\/run\/([^/]+)\/?$/.exec(pathname);
  if (m) return { page: "detail", scenarioId: decodeURIComponent(m[1]) };
  if (pathname === "/run" || pathname === "/run/") return { page: "detail" };
  return { page: "live" };
};
function App() {
  const [route, setRoute] = useState<Route>(() =>
    parseRoute(window.location.pathname),
  );
  const page = route.page;
  const lastScenario = useRef<string | undefined>(
    route.page === "detail" ? route.scenarioId : undefined,
  );
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Run>();
  const [actions, setActions] = useState<Action[]>([]);
  const [live, setLive] = useState<any>();
  const [error, setError] = useState("");
  const activeJobs = useRef(new Set<string>());
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem("tempera-theme");
    return saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  useEffect(() => {
    localStorage.setItem("tempera-theme", dark ? "dark" : "light");
  }, [dark]);
  const navigate = (next: Route) => {
    setRoute(next);
    const path =
      next.page === "detail"
        ? next.scenarioId
          ? `/run/${encodeURIComponent(next.scenarioId)}`
          : "/run"
        : "/";
    window.history.pushState(null, "", path);
  };
  useEffect(() => {
    const onPopState = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  useEffect(() => {
    if (route.page === "detail" && route.scenarioId) {
      lastScenario.current = route.scenarioId;
    }
  }, [route]);
  useEffect(() => {
    if (route.page !== "detail" || !route.scenarioId) return;
    const match = runs.find((r) => r.scenario === route.scenarioId);
    if (match && match.run_id !== selected?.run_id) {
      setSelected(match);
      setLive(undefined);
    }
  }, [route, runs]);
  const refresh = () =>
    api
      .getActiveBatches()
      .catch(() => ({ job_ids: [] }))
      .then(({ job_ids }: { job_ids: string[] }) => {
        job_ids.forEach((id) => activeJobs.current.add(id));
        return Promise.all([
          api.getRuns(),
          Promise.all(
            [...activeJobs.current].map((id) =>
              api.getBatch(id).catch(() => undefined),
            ),
          ),
        ]);
      })
      .then(([artifacts, batches]: [Run[], any[]]) => {
        const transient: Run[] = [];
        batches.forEach((batch) => {
          if (!batch) return;
          batch.runs.forEach((run: any) =>
            transient.push({
              ...run,
              // Batch completion precedes artifact publication. Keep that
              // window visible as FINALIZING instead of falsely COMPLETE.
              status:
                run.status === "completed" &&
                !artifacts.some((artifact) => artifact.run_id === run.run_id)
                  ? "finalizing"
                  : run.status || run.state,
            }),
          );
        });
        const artifactIds = new Set(artifacts.map((run) => run.run_id));
        const stoppingIds = new Set(
          transient
            .filter((run) => ["stopping", "stopped"].includes(run.status))
            .map((run) => run.run_id),
        );
        batches.forEach((batch) => {
          // Keep failed/stopped runs visible when the subprocess exited before
          // writing a result artifact. Remove a batch only after every run has
          // a durable artifact to replace its transient status.
          if (
            batch &&
            batch.completed >= batch.total &&
            batch.runs.every((run: any) => artifactIds.has(run.run_id))
          ) {
            activeJobs.current.delete(batch.job_id);
          }
        });
        const x = [
          ...transient.filter(
            (run) => stoppingIds.has(run.run_id) || !artifactIds.has(run.run_id),
          ),
          ...artifacts.filter((run) => !stoppingIds.has(run.run_id)),
        ];
        setRuns(x);
        setSelected((o) =>
          (o && x.find((r) => r.run_id === o.run_id)) || x[0],
        );
      })
      .catch(() => setError("Backend is not available"));
  useEffect(() => {
    api
      .getScenarios()
      .then(setScenarios)
      .catch(() => setError("Backend is not available"));
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    setActions([]);
    setLive(undefined);
    if (!selected) return;
    const load = () =>
      api
        .getActions(selected.run_id)
        .then((next) =>
          setActions((current) => {
            const merged = new Map(
              current
                .filter((row) => !row.action_id.startsWith("progress-"))
                .map((row) => [row.action_id, row]),
            );
            next.forEach((row: Action) => merged.set(row.action_id, row));
            const rows = [...merged.values()].sort((a, b) => a.seq - b.seq);
            return JSON.stringify(current) === JSON.stringify(rows)
              ? current
              : rows;
          }),
        )
        .catch(() => undefined);
    load();
    const t = setInterval(load, 1500);
    const ss = api.stream(selected.run_id, setLive);
    return () => {
      clearInterval(t);
      ss.close();
    };
  }, [selected?.run_id]);
  const liveRuns = useMemo(
    () => runs.filter((r) => !TERMINAL_STATUSES.includes(r.status)),
    [runs],
  );
  const running = liveRuns.length;
  const batchProgress = useMemo(() => {
    const jobIdOf = (runId: string) =>
      /^ui-.+-([0-9a-f]{8})-r\d+$/.exec(runId)?.[1];
    const groups = new Map<string, { total: number; completed: number }>();
    runs.forEach((r) => {
      const jobId = jobIdOf(r.run_id);
      if (!jobId) return;
      const group = groups.get(jobId) || { total: 0, completed: 0 };
      group.total += 1;
      if (TERMINAL_STATUSES.includes(r.status) || r.status === "finalizing") {
        group.completed += 1;
      }
      groups.set(jobId, group);
    });
    const active = [...groups.values()].filter((g) => g.completed < g.total);
    if (!active.length) return null;
    return active.reduce(
      (acc, g) => ({ completed: acc.completed + g.completed, total: acc.total + g.total }),
      { completed: 0, total: 0 },
    );
  }, [runs]);
  const start = (x: object) => {
    setError("");
    return api
      .startBatch(x)
      .then(({ job_id }: { job_id: string }) => {
        activeJobs.current.add(job_id);
        return refresh();
      })
      .catch((reason: Error) =>
        setError(`Could not start the run: ${reason.message}`),
      );
  };
  const stop = (r: Run) => {
    setRuns((current) =>
      current.map((item) =>
        item.run_id === r.run_id ? { ...item, status: "stopping" } : item,
      ),
    );
    return api
      .stopRun(r.run_id)
      .then(refresh)
      .catch(() => setError("Could not stop the run"));
  };
  const remove = (r: Run) =>
    api
      .deleteRun(r.run_id)
      .then(refresh)
      .catch(() => setError("Could not delete invalid run"));
  return (
    <div className={`app ${dark ? "dark" : "light"}`}>
      <header className="topbar">
        <img
          src={dark ? "/logo-for-dark.png" : "/logo.png"}
          alt="Rein"
        />
        <span className="brand-name">Rein</span>
        <nav className="page-nav" aria-label="Pages">
          <button
            className={page === "live" ? "active" : ""}
            onClick={() => navigate({ page: "live" })}
          >
            Live Run
          </button>
          <button
            className={page === "detail" ? "active" : ""}
            onClick={() => navigate({ page: "detail" })}
          >
            Run Detail
          </button>
        </nav>
        <EnvironmentHealth />
        <button
          className="theme-toggle"
          type="button"
          aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
          title={dark ? "Light mode" : "Dark mode"}
          onClick={() => setDark((value) => !value)}
        >
          <span aria-hidden="true">{dark ? "☀" : "☾"}</span>
        </button>
        <span
          className="topbar-status"
          tabIndex={liveRuns.length ? 0 : undefined}
          data-tooltip={
            liveRuns.length
              ? liveRuns
                  .map((r) => `${r.scenario || r.run_id} · ${labels[r.status] || r.status}`)
                  .join("\n")
              : undefined
          }
        >
          <i /> {running ? `${running} live` : "ready"}
        </span>
      </header>
      {page === "detail" ? (
        <RunDetailPage
          scenarioId={route.page === "detail" ? route.scenarioId : undefined}
          navigate={navigate}
        />
      ) : (
      <>
          <main>
            {error && <div className="error">{error}</div>}
            <AutonomyScope />
            <section className="card setup">
              <Config scenarios={scenarios} start={start} />
            </section>
            <div className="layout">
              <section className="card queue">
                <div className="card-title">
                  <span>Runs</span>
                  <div className="card-title-meta">
                    {batchProgress && (
                      <span className="batch-progress">
                        <span className="batch-progress-bar">
                          <span
                            className="batch-progress-fill"
                            style={{
                              width: `${
                                batchProgress.total
                                  ? Math.min(
                                      100,
                                      (batchProgress.completed / batchProgress.total) * 100,
                                    )
                                  : 0
                              }%`,
                            }}
                          />
                        </span>
                        {batchProgress.completed}/{batchProgress.total} done
                      </span>
                    )}
                    <small>{runs.length} artifacts loaded</small>
                    {liveRuns.filter((r) => r.status !== "stopping").length > 1 && (
                      <button
                        type="button"
                        className="stop-all"
                        onClick={() =>
                          liveRuns
                            .filter((r) => r.status !== "stopping")
                            .forEach((r) => stop(r))
                        }
                      >
                        Stop all
                      </button>
                    )}
                  </div>
                </div>
                <RunList
                  runs={runs}
                  selected={selected?.run_id}
                  select={(r) => {
                    setSelected(r);
                    setLive(undefined);
                  }}
                  stop={stop}
                  remove={remove}
                />
              </section>
              <section className="card run-summary">
                {selected ? (
                  <div className="run-summary-body">
                    <span className="run-summary-eyebrow">Selected run</span>
                    <div className="run-summary-head">
                      <div className="run-summary-heading">
                        <small>{selected.scenario || "Unknown scenario"}</small>
                        <strong>{selected.run_id}</strong>
                      </div>
                      <span className={`run-summary-badge ${selected.status}`}>
                        {labels[selected.status] || selected.status}
                      </span>
                    </div>
                    <div className="run-summary-goal">
                      <span>Goal</span>
                      <b
                        className={
                          selected.status === "partial"
                            ? "partial"
                            : selected.goal_success
                              ? "good"
                              : selected.goal_success === false
                                ? "bad"
                                : ""
                        }
                      >
                        {selected.status === "partial"
                          ? "Partial"
                          : selected.goal_success == null
                            ? "Pending"
                            : selected.goal_success
                              ? "Reached"
                              : "Not reached"}
                      </b>
                    </div>
                    <div className="run-summary-roe">
                      <div className="run-summary-roe-head">
                        <span>ROE</span>
                        {(selected.violation_count ?? 0) > 0 ? (
                          <small className="bad">
                            {selected.violation_count} violation
                            {selected.violation_count === 1 ? "" : "s"}
                          </small>
                        ) : (
                          <small className="good">Compliant</small>
                        )}
                      </div>
                      <RoeSummary run={selected} actions={actions} />
                    </div>
                    <LiveThought
                      actions={actions}
                      terminal={TERMINAL_STATUSES.includes(selected.status)}
                    />
                    <button
                      type="button"
                      className="view-detail"
                      onClick={() =>
                        navigate({
                          page: "detail",
                          scenarioId: selected.scenario,
                        })
                      }
                    >
                      View run detail
                      <span aria-hidden="true">{String.fromCharCode(8594)}</span>
                    </button>
                  </div>
                ) : (
                  <div className="run-summary-body">
                    <span className="empty">
                      Select a run below to open Evidence Console.
                    </span>
                  </div>
                )}
              </section>
            </div>
          </main>
          <EvidenceDock
            run={selected}
            actions={actions}
            live={live}
            hasArtifact={!!selected && runs.some((r) => r.run_id === selected.run_id)}
          />
      </>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
