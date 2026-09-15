import asyncio
import json
import os
import socket
import shutil
import subprocess
import time
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yaml
from dotenv import load_dotenv

from .loader import RunLoader, _lines, _read
from .models import RunConfig
from .runner import RunnerService

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)
(ROOT / "runs").mkdir(exist_ok=True)
app = FastAPI(title="Tempera Console")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
loader = RunLoader(ROOT / "runs")
runner = RunnerService(ROOT)


@app.get("/api/meta/scenarios")
def scenarios():
    discovered = {}
    paths = sorted(
        {
            *((ROOT / "scenarios").glob("*/scenario.yaml")),
            *((ROOT / "scenarios").glob("rein/**/*.yaml")),
        }
    )
    for path in paths:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        scenario_id = doc.get("id") or path.parent.name
        goal = doc.get("goal") or {}
        description = goal.get("description") or doc.get("condition", "")
        policy = path.parent / "policy.yaml"
        if not policy.is_file():
            policy = next(iter(path.parent.glob("*-policy.yaml")), None)
        discovered.setdefault(
            scenario_id,
            {
                "id": scenario_id,
                "name": scenario_id,
                "description": description,
                "policy": policy.name if policy else None,
            },
        )
    return [discovered[scenario_id] for scenario_id in sorted(discovered)]


@app.get("/api/meta/models")
def models():
    return [{"id": "deepseek-flash", "provider": "deepseek"}, {"id": "llama3", "provider": "ollama"}]


def _http_probe(url: str):
    started = time.perf_counter()
    try:
        with urlopen(url, timeout=1.5) as response:
            return {"status": "ready" if response.status < 500 else "degraded", "code": response.status, "latency_ms": round((time.perf_counter() - started) * 1000)}
    except HTTPError as error:
        return {"status": "degraded", "code": error.code, "latency_ms": round((time.perf_counter() - started) * 1000)}
    except OSError:
        return {"status": "offline", "latency_ms": round((time.perf_counter() - started) * 1000)}


def _tcp_probe(host: str, port: int):
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return {"status": "ready", "latency_ms": round((time.perf_counter() - started) * 1000)}
    except OSError:
        return {"status": "offline", "latency_ms": round((time.perf_counter() - started) * 1000)}


@app.get("/api/env/status")
def env_status(target: str = "http://127.0.0.1:3001"):
    # The relay is accessed by the host-side console through the published
    # port. The Docker service name (e.g. tempera-model-relay) is only
    # resolvable from inside the Docker network. Gateway containers are
    # created per run, so they are not a preflight dependency here.
    relay = os.environ.get("TEMPERA_MODEL_ENDPOINT")
    relay_probe = _http_probe("http://127.0.0.1:8090/healthz") if relay else {"status": "not_configured"}
    return {"target": _http_probe(f"{target.rstrip('/')}/health"), "model_relay": relay_probe}


@app.post("/api/env/start")
def start_environment():
    """Start the two long-lived Docker services required before a live run."""
    subprocess.run(["docker", "network", "create", "target-net"], capture_output=True, text=True)
    def ensure(name: str, image: str, args: list[str]):
        inspect = subprocess.run(["docker", "inspect", name], capture_output=True, text=True)
        if inspect.returncode == 0:
            result = subprocess.run(["docker", "start", name], capture_output=True, text=True)
        else:
            result = subprocess.run(["docker", "run", "-d", "--name", name, *args, image], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(500, f"Could not start {name}: {(result.stderr or result.stdout).strip()[-500:]}")
        return name

    # Target carries per-run observer settings, so a stale existing container
    # must be recreated instead of merely started.
    subprocess.run(["docker", "rm", "-f", "tempera-juice"], capture_output=True, text=True)
    ensure("tempera-juice", "tempera-juice-shop:latest", [
        "--network", "target-net", "--add-host=host.docker.internal:host-gateway",
        "-e", "NODE_ENV=ctf", "-e", "CTF_KEY=tempera-test-001",
        "-e", "TEMPERA_DB_OBSERVER=host.docker.internal:8765",
        "-e", "TEMPERA_DB_OBSERVER_TOKEN", "-p", "127.0.0.1:3001:3000",
    ])
    relay_state = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", "tempera-model-relay"], capture_output=True, text=True)
    if relay_state.returncode == 0 and relay_state.stdout.strip().lower() != "true":
        subprocess.run(["docker", "rm", "tempera-model-relay"], capture_output=True, text=True)
    ensure("tempera-model-relay", "tempera-model-relay:stage4", [
        "-p", "127.0.0.1:8090:8090", "-e", "TEMPERA_MODEL_UPSTREAM",
        "-e", "TEMPERA_MODEL_ALLOWED_ENDPOINTS", "-e", "DEEPSEEK_API_KEY",
        "-e", "TEMPERA_PROVIDER=deepseek", "-e", "TEMPERA_MODEL=deepseek-flash",
    ])
    return {"started": True}


@app.post("/api/runs/batch", status_code=202)
def start_batch(config: RunConfig):
    if not (ROOT / "scenarios" / config.scenario / "scenario.yaml").is_file():
        raise HTTPException(400, "unknown scenario")
    return {"job_id": runner.start_batch(config)}


@app.get("/api/runs/batch")
def active_batches():
    return {"job_ids": runner.active_job_ids()}


@app.get("/api/runs/batch/{job_id}")
def batch_status(job_id: str):
    try:
        return runner.status(job_id)
    except KeyError:
        raise HTTPException(404, "job not found")


@app.post("/api/runs/batch/{job_id}/stop")
def stop_batch(job_id: str):
    try:
        runner.stop(job_id)
        return {"job_id": job_id, "status": "stopping"}
    except KeyError:
        raise HTTPException(404, "job not found")


@app.get("/api/runs")
def runs(scenario: str | None = None):
    result = []
    for path in loader.dirs():
        summary = loader.load_summary(path)
        if not summary.scenario:
            continue
        if scenario and summary.scenario != scenario:
            continue
        result.append(summary.model_dump())
        if len(result) == 200:
            break
    return result


def _run_dir(run_id: str) -> Path:
    path = ROOT / "runs" / run_id
    if not path.is_dir():
        raise HTTPException(404, "run not found")
    return path


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str):
    path = _run_dir(run_id)
    return {"summary": loader.load_summary(path).model_dump(), "overlay": loader.load_overlay(path).model_dump(), "live": loader.load_live_status(path)}


@app.delete("/api/runs/{run_id}")
def delete_invalid_run(run_id: str):
    if Path(run_id).name != run_id:
        raise HTTPException(400, "invalid run id")
    path = ROOT / "runs" / run_id
    if not path.is_dir():
        raise HTTPException(404, "run not found")
    if loader.load_summary(path).status != "invalid":
        raise HTTPException(409, "only invalid runs can be deleted")
    shutil.rmtree(path)
    return {"run_id": run_id, "deleted": True}


@app.post("/api/runs/{run_id}/stop")
def stop_run(run_id: str):
    try:
        runner.stop_run(run_id)
        return {"run_id": run_id, "status": "stopping"}
    except KeyError:
        raise HTTPException(404, "run not active")


@app.get("/api/runs/{run_id}/actions")
def actions(run_id: str):
    return [row.model_dump() for row in loader.load_actions(_run_dir(run_id))]


@app.get("/api/runs/{run_id}/overlay")
def overlay(run_id: str):
    return loader.load_capability_overlay(_run_dir(run_id)).model_dump()


@app.get("/api/runs/{run_id}/artifacts")
def artifacts(run_id: str):
    def display_content(candidate: Path, content: str) -> str:
        if candidate.suffix == ".jsonl":
            records = []
            for line in content.splitlines():
                if not line.strip():
                    continue
                try:
                    records.append(json.dumps(json.loads(line), ensure_ascii=False, indent=2))
                except json.JSONDecodeError:
                    return content
            return "\n\n".join(records)
        try:
            return json.dumps(json.loads(content), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return content

    path = _run_dir(run_id)
    result = []
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_file() or candidate.suffix not in {".json", ".jsonl"}:
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
            result.append({"name": candidate.relative_to(path).as_posix(), "content": display_content(candidate, content)})
        except OSError:
            continue
    return result


@app.get("/api/runs/{run_id}/terminal")
def terminal(run_id: str):
    path = _run_dir(run_id)
    records = []
    for name in ("lifecycle.jsonl", "events.jsonl"):
        file = path / name
        if not file.is_file():
            continue
        for row in _lines(file):
            stage = row.get("stage") or row.get("type")
            if name == "events.jsonl":
                source = "GATEWAY"
                attrs = row.get("attributes") or {}
                target = attrs.get("path") or row.get("target", "-")
                text = f"{attrs.get('method', 'REQUEST')} {unquote(urlsplit(target).path if str(target).startswith(('http://', 'https://')) else str(target))} → {attrs.get('status', '-')}"
            elif stage == "proposed":
                source = "AGENT"
                action = row.get("raw_action") or {}
                text = f"step {row.get('seq', 0) + 1} · {action.get('method', 'ACTION')} {unquote(str(action.get('path', '-')))}"
            elif stage == "policy_decision":
                source = "JUDGE"
                text = f"policy_decision={row.get('decision', '-')} · {row.get('reason', '')}".rstrip(" ·")
            else:
                source = "RUNNER"
                text = f"{stage or 'event'}"
            records.append({"timestamp": row.get("timestamp"), "source": source, "text": text})
    result = _read(path / "result.json", {}) or {}
    for violation in (result.get("roe") or {}).get("violations", []):
        records.append({"timestamp": result.get("timestamp"), "source": "JUDGE", "text": f"{', '.join(violation.get('roe_categories', [])) or 'ROE'} · ESCAPED"})
    # A target/provisioning failure also writes goal.success=false, but that is
    # not a Judge evaluation. Only emit a Judge result once an agent step or a
    # completed run exists.
    termination = result.get("termination") or {}
    has_agent_evaluation = (
        termination.get("step") is not None
        or result.get("status") in {"completed", "partial"}
    )
    if has_agent_evaluation and (result.get("goal") or {}).get("success") is not None:
        records.append({"timestamp": result.get("timestamp"), "source": "JUDGE", "text": f"goal_reached={bool(result.get('goal', {}).get('success'))}"})
    for observer in result.get("observers") or []:
        records.append({"timestamp": result.get("timestamp"), "source": "OBSERVER", "text": str(observer)})
    records.append({"timestamp": result.get("timestamp"), "source": "RUNNER", "text": f"{result.get('status', 'running')} · result.json written"})
    for row in _lines(path / "progress.jsonl"):
        if row.get("type") == "roe_evaluated":
            continue
        state = row.get("state") or ""
        records.append({"timestamp": row.get("ts"), "source": "RUNNER", "text": f"{row.get('type', 'progress')} / {state}".strip(" /")})
    records.sort(key=lambda row: row.get("timestamp") or "")
    return records


@app.get("/api/runs/{run_id}/stream")
async def stream(run_id: str):
    if Path(run_id).name != run_id:
        raise HTTPException(400, "invalid run id")
    path = ROOT / "runs" / run_id
    async def events():
        while True:
            live = loader.load_live_status(path) if path.is_dir() else None
            if live:
                yield f"data: {json.dumps(live.model_dump())}\n\n"
            if live and live.state in {
                "completed", "failed", "invalid", "interrupted", "partial", "stopped",
            }:
                break
            await asyncio.sleep(1)
    return StreamingResponse(events(), media_type="text/event-stream")
