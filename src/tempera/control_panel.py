"""Small local web control panel for the benchmark runner."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from threading import Event, Lock
from uuid import uuid4

import yaml
from flask import Flask, jsonify, request, render_template_string


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tempera Run Desk</title>
<style>
:root{font:15px/1.45 system-ui,sans-serif;color:#17202a;background:#f5f7fb}*{box-sizing:border-box}body{max-width:1180px;margin:32px auto;padding:0 18px}h1{margin:0 0 6px;font-size:28px}h2{font-size:16px;margin:0 0 14px}.muted{color:#6b7280}.grid{display:grid;grid-template-columns:330px 1fr;gap:18px}.card{background:white;border:1px solid #e4e7ec;border-radius:14px;padding:18px;box-shadow:0 3px 14px #1f29370b}.fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}.full{grid-column:1/-1}label{display:grid;gap:5px;color:#4b5563;font-size:12px}input,select{width:100%;border:1px solid #d1d5db;border-radius:8px;padding:9px;background:white;font:inherit}button{border:0;border-radius:9px;padding:11px 14px;background:#2563eb;color:white;font-weight:700;cursor:pointer;width:100%;margin-top:14px}button:disabled{opacity:.5}.checks{display:flex;gap:16px;margin-top:12px}.checks label{display:flex;align-items:center;display:flex;gap:6px}.checks input{width:auto}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px}.stat{background:#111827;color:white;border-radius:12px;padding:13px}.stat b{display:block;font-size:23px}.run{border-top:1px solid #edf0f4;padding:11px 0;display:flex;justify-content:space-between;gap:12px;cursor:pointer}.run:hover{background:#f8fafc}.pill{padding:3px 8px;border-radius:999px;background:#eef2ff;color:#3730a3;font-size:12px;white-space:nowrap}.ok{background:#dcfce7;color:#166534}.bad{background:#fee2e2;color:#991b1b}.empty{color:#9ca3af;text-align:center;padding:34px 0}.modal{position:fixed;inset:0;background:#11182766;display:grid;place-items:center;padding:20px}.modal-card{background:white;border-radius:14px;padding:22px;max-width:620px;width:100%;max-height:85vh;overflow:auto}.modal-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.modal-grid div{background:#f5f7fb;border-radius:8px;padding:10px}.modal-close{float:right;width:auto;margin:0;padding:4px 10px;background:#e5e7eb;color:#111827}@media(max-width:800px){.grid{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}}
</style></head><body><h1>Tempera Run Desk</h1><p class="muted">시나리오를 고르고 옵션을 넣은 뒤 여러 번 실행합니다.</p>
<div class="grid"><section class="card"><h2>실행 설정</h2><form id="form"><div class="fields">
<label class="full">시나리오<select name="scenario" id="scenario"></select></label>
<label>모델<input name="model" value="deepseek-chat" required></label><label>Provider<select name="provider"><option value="deepseek">deepseek</option><option value="ollama">ollama</option></select></label>
<label class="full">Target URL<input name="upstream" value="http://127.0.0.1:3001"></label>
<label>반복 횟수<input name="repeat" type="number" min="1" max="100" value="1"></label><label>병렬 슬롯<input name="parallel" type="number" min="1" max="8" value="1"></label>
<label>Max steps<input name="max_steps" type="number" min="1" placeholder="시나리오 기본값"></label><label>Max tokens<input name="max_tokens" type="number" min="1" placeholder="제한 없음"></label>
<label>Run token budget<input name="run_token_budget" type="number" min="1" placeholder="제한 없음"></label><label>Temperature<input name="temperature" type="number" step="0.1" min="0" placeholder="기본값"></label>
<label>Seed<input name="seed" type="number" placeholder="자동"></label><label>Timeout (초)<input name="timeout" type="number" min="1" placeholder="시나리오 기본값"></label>
</div><div class="checks"><label><input name="reset_target" type="checkbox"> target reset</label><label><input name="enforce_policy" type="checkbox"> policy enforce</label></div><button id="submit">실행 시작</button></form><p id="message" class="muted"></p></section>
<section><div class="stats"><div class="stat"><span>전체</span><b id="total">0</b></div><div class="stat"><span>성공</span><b id="success">0</b></div><div class="stat"><span>실패</span><b id="failed">0</b></div><div class="stat"><span>평균 step</span><b id="steps">-</b></div></div><div class="card"><h2>최근 실행</h2><div id="runs" class="empty">아직 실행 결과가 없습니다.</div></div></section></div>
<div id="modal" hidden></div><script>
const $=s=>document.querySelector(s); const form=$('#form');
let activeJob=null;const stopButton=document.createElement('button');stopButton.textContent='실행 중지';stopButton.disabled=false;stopButton.style.background='#dc2626';form.after(stopButton);stopButton.onclick=async()=>{await fetch('/api/jobs/stop-all',{method:'POST'});$('#message').textContent='중지 요청을 보냈습니다.'};
function val(name){const x=form.elements[name]; return x.type==='checkbox'?x.checked:(x.value||null)}
async function load(){const selected=$('#scenario').value;const [s,r]=await Promise.all([fetch('/api/scenarios').then(x=>x.json()),fetch('/api/runs').then(x=>x.json())]);const current=$('#scenario').value;const keep=s.some(x=>x.id===current)?current:(s.some(x=>x.id===selected)?selected:(s[0]?.id||''));$('#scenario').innerHTML=s.map(x=>`<option value="${x.id}">${x.id} — ${x.description||''}</option>`).join('');$('#scenario').value=keep;draw(r)}
function draw(r){$('#total').textContent=r.summary.total;$('#success').textContent=r.summary.success;$('#failed').textContent=r.summary.failed;$('#steps').textContent=r.summary.avg_steps??'-';$('#runs').className=r.runs.length?'':'empty';$('#runs').innerHTML=r.runs.length?r.runs.map((x,i)=>`<div class="run" onclick="showDetail(${i})"><span><b>${x.scenario}</b> <span class="muted">${x.run_id}</span><br><span class="muted">${x.model} · ${x.steps??'-'} steps · ${x.tokens??'-'} tokens · ${x.source}</span></span><span class="pill ${x.success?'ok':x.status==='failed'?'bad':''}">${x.success?'SUCCESS':x.status||'running'}</span></div>`).join(''):'아직 실행 결과가 없습니다.';window.currentRuns=r.runs}
function showDetail(i){const x=window.currentRuns[i],d=x.detail||{},roe=Object.entries(d.roe||{}).map(([k,v])=>`<div class="roe-item ${v==='pass'?'roe-pass':v==='violation'?'roe-fail':'roe-na'}"><b>${k}</b><small>${v}</small></div>`).join('');$('#modal').hidden=false;$('#modal').innerHTML=`<div class="modal" onclick="if(event.target===this)closeDetail()"><div class="modal-card"><button class="modal-close" onclick="closeDetail()">닫기</button><h2 class="modal-title">${x.scenario} · ${x.run_id}</h2><div class="modal-grid"><div><b>상태</b><span>${x.status}</span></div><div><b>결과</b><span>${x.success?'성공':'실패'}</span></div><div><b>Steps</b><span>${x.steps??'-'}</span></div><div><b>Tokens</b><span>${x.tokens??'-'}</span></div><div><b>종료 사유</b><span>${d.termination_reason||'-'}</span></div><div><b>유효성</b><span>${d.valid?'정상':'무효'}</span></div><div><b>실행 위치</b><span>${x.source}</span></div></div><h3 class="roe-title">ROE 판정</h3><div class="roe-grid">${roe||'<div class="roe-item roe-na">판정 없음</div>'}</div></div></div>`}
function closeDetail(){$('#modal').hidden=true}
function renderScenarioStats(stats){let box=$('#scenarioStats');if(!box){box=document.createElement('div');box.id='scenarioStats';box.style.cssText='margin-bottom:18px;background:white;border:1px solid #e4e7ec;border-radius:14px;padding:18px;box-shadow:0 3px 14px #1f29370b';$('#runs').parentElement.parentElement.insertBefore(box,$('#runs').parentElement)}const rows=Object.values(stats).map(x=>`<div><b>${x.scenario}</b></div>`).join('');box.innerHTML=`<h2 style="margin:0 0 8px">시나리오별 집계</h2>${rows||'<div class="empty">통계가 없습니다.</div>'}`}
function addDeleteButtons(){document.querySelectorAll('.run').forEach((row,i)=>{if(row.querySelector('.delete-run'))return;const b=document.createElement('button');b.className='delete-run';b.textContent='삭제';b.style.cssText='width:auto;margin:0;padding:5px 9px;background:#fee2e2;color:#991b1b';b.onclick=e=>{e.stopPropagation();deleteRun(i)};row.appendChild(b)})}
async function deleteRun(i){const x=window.currentRuns[i];if(!x||!confirm(`${x.run_id} 결과를 삭제할까요?`))return;const r=await fetch(`/api/runs/${encodeURIComponent(x.run_id)}`,{method:'DELETE'});if(!r.ok){alert('삭제하지 못했습니다.');return}load()}
const originalDraw=draw;draw=r=>{originalDraw(r);renderLive(r.runs);addDeleteButtons();renderScenarioStats(r.scenario_stats||{})}
renderScenarioStats=stats=>{let box=$('#scenarioStats');if(!box){box=document.createElement('div');box.id='scenarioStats';box.style.cssText='margin-bottom:18px;background:white;border:1px solid #e4e7ec;border-radius:14px;padding:18px;box-shadow:0 3px 14px #1f29370b';$('#runs').parentElement.parentElement.insertBefore(box,$('#runs').parentElement)}const pct=v=>v==null?'-':`${(v*100).toFixed(1)}%`;const rows=Object.entries(stats).sort().map(([scenario,groups])=>`<div style="margin:18px 0 6px;font-weight:700">${scenario}</div>${Object.entries(groups).sort().map(([policy,s])=>`<div style="display:grid;grid-template-columns:1.4fr repeat(5,1fr);gap:8px;padding:10px 0;border-top:1px solid #edf0f4;align-items:center;font-size:13px"><b>${policy}</b><span>${s.attempted_runs}회<br><small>valid ${s.valid_runs}</small></span><span>Goal<br><b>${pct(s.goal_rate)}</b></span><span>ROE 위반<br><b>${pct(s.violation_rate)}</b></span><span>Safe success<br><b>${pct(s.safe_success_rate)}</b></span><span>Mean steps<br><b>${s.mean_steps==null?'-':s.mean_steps.toFixed(1)}</b></span></div>`).join('')}`).join('');box.innerHTML=`<h2 style="margin:0 0 8px">시나리오별 집계</h2><div class="muted" style="font-size:12px;margin-bottom:4px">scripts/aggregate.py summarize() 기준 · policy 그룹별</div>${rows||'<div class="empty">집계 결과가 없습니다.</div>'}`}
renderScenarioStats=stats=>{let box=$('#scenarioStats');if(!box){box=document.createElement('div');box.id='scenarioStats';box.style.cssText='margin-bottom:18px;background:white;border:1px solid #e4e7ec;border-radius:14px;padding:18px;box-shadow:0 3px 14px #1f29370b';$('#runs').parentElement.parentElement.insertBefore(box,$('#runs').parentElement)}const pct=v=>v==null?'-':`${(v*100).toFixed(1)}%`;const rows=Object.entries(stats).sort().map(([scenario,groups])=>`<div style="margin:18px 0 6px;font-weight:700">${scenario}</div>${Object.entries(groups).sort().map(([policy,s])=>{const cats=Object.fromEntries((s.roe_categories||[]).map(x=>[x.code,x]));const bars=['R1','R2','R3','R4','R5','R6'].map(code=>{const rate=cats[code]?.violating_run_rate||0;return `<div style="display:grid;grid-template-columns:28px 1fr 52px;gap:7px;align-items:center;font-size:12px"><b>${code}</b><div style="height:10px;background:#eef2f7;border-radius:99px;overflow:hidden"><div style="height:100%;width:${rate*100}%;background:${rate?'#ef4444':'#cbd5e1'}"></div></div><span>${pct(rate)}</span></div>`}).join('');return `<div style="display:grid;grid-template-columns:1.35fr repeat(5,1fr);gap:8px;padding:10px 0;border-top:1px solid #edf0f4;align-items:start;font-size:13px"><b>${policy}</b><span>${s.attempted_runs}회<br><small>valid ${s.valid_runs}</small></span><span>Goal<br><b>${pct(s.goal_rate)}</b></span><span>ROE 위반<br><b>${pct(s.violation_rate)}</b></span><span>Safe success<br><b>${pct(s.safe_success_rate)}</b></span><span>Mean steps<br><b>${s.mean_steps==null?'-':s.mean_steps.toFixed(1)}</b><div style="grid-column:1/-1;margin-top:8px;padding:8px 10px;background:#f8fafc;border-radius:8px"><b>R1-R6 violation rate</b>${bars}</div></span></div>`}).join('')}`).join('');box.innerHTML=`<h2 style="margin:0 0 8px">시나리오별 집계 · R1-R6</h2><div class="muted" style="font-size:12px;margin-bottom:4px">Existing summarize() data. Longer red bars mean more violations.</div>${rows||'<div class="empty">No aggregate data.</div>'}`}
function showDetail(i){const x=window.currentRuns[i],d=x.detail||{},roe=Object.entries(d.roe||{}).map(([k,v])=>`<div style="padding:12px;border-radius:8px;background:${v==='pass'?'#dcfce7':v==='violation'?'#fee2e2':'#f3f4f6'};color:${v==='pass'?'#166534':v==='violation'?'#991b1b':'#6b7280'}"><b>${k}</b><br>${v}</div>`).join('');$('#modal').hidden=false;$('#modal').innerHTML=`<div class="modal" onclick="if(event.target===this)closeDetail()"><div class="modal-card" style="max-width:780px;padding:24px"><button class="modal-close" onclick="closeDetail()">Close</button><h2 class="modal-title">${x.scenario} · ${x.run_id}</h2><div class="modal-grid" style="grid-template-columns:repeat(4,1fr)"><div><b>Status</b><span>${x.status}</span></div><div><b>Result</b><span>${x.success?'SUCCESS':'FAIL'}</span></div><div><b>Steps</b><span>${x.steps??'-'}</span></div><div><b>Tokens</b><span>${x.tokens??'-'}</span></div><div><b>Termination</b><span>${d.termination_reason||'-'}</span></div><div><b>Validity</b><span>${d.valid?'VALID':'INVALID'}</span></div><div><b>Source</b><span>${x.source}</span></div></div><h3 style="margin:22px 0 8px">ROE verdicts</h3><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">${roe||'<div>No verdicts</div>'}</div></div></div>`}
form.onsubmit=async e=>{e.preventDefault();$('#submit').disabled=true;$('#message').textContent='실행을 등록했습니다. 결과를 갱신하는 중…';const body={};for(const x of form.elements)if(x.name)body[x.name]=val(x.name);const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const j=await r.json();$('#message').textContent=r.ok?`작업 ${j.job_id} 시작 (${j.count}회)`:(j.error||'실행 실패');$('#submit').disabled=false;load()};
function renderLive(runs){let box=$('#liveRuns');if(!box){box=document.createElement('div');box.id='liveRuns';$('#runs').parentElement.parentElement.insertBefore(box,$('#runs').parentElement)}const live=runs.filter(x=>x.status==='running'||(x.live?.state&&x.status!=='completed'));box.innerHTML=live.length?`<div class="card" style="margin-bottom:18px;border-color:#bfdbfe"><h2 style="color:#1d4ed8">Live lifecycle</h2>${live.map(x=>{const q=x.live||{},step=q.step??'-',max=q.max_steps??'-',action=q.last_action?`${q.last_action.method||''} ${q.last_action.path||''}`:'';return `<div style="padding:10px 0;border-top:1px solid #dbeafe"><b>${x.scenario}</b> <span class="muted">${x.run_id}</span><br><span>${q.state||'running'} · ${q.event||'-'} · step ${step}/${max}</span>${q.stage?`<br><small class="muted">stage: ${q.stage}</small>`:''}${action?`<br><small class="muted">action: ${action}</small>`:''}</div>`}).join('')}</div>`:''}
document.head.insertAdjacentHTML('beforeend','<style>body{max-width:1280px;margin:18px auto}.grid{grid-template-columns:300px minmax(0,1fr);gap:14px}.grid>section:first-child{position:sticky;top:14px;align-self:start}.card{padding:14px}.stats{gap:7px;margin-bottom:12px}.stat{padding:10px}.stat b{font-size:20px}.run{padding:8px 0}.card>#runs{max-height:520px;overflow:auto;padding-right:8px}#scenarioStats{max-height:470px;overflow:auto}#liveRuns .card{max-height:250px;overflow:auto}.delete-run{flex:0 0 auto}.modal-card{max-height:90vh}@media(max-width:800px){.grid>section:first-child{position:static}.card>#runs,#scenarioStats,#liveRuns .card{max-height:none}}</style>');load();setInterval(load,2500);
</script></body></html>"""


def _number(data, key, cast=int):
    value = data.get(key)
    return cast(value) if value not in (None, "") else None


def create_app(root: Path | str = ".") -> Flask:
    root = Path(root).resolve()
    runs_dir, scenarios_dir = root / "runs", root / "scenarios"
    experiments_dir = root / "experiments"
    app = Flask(__name__)
    jobs: dict[str, str] = {}
    stop_events: dict[str, Event] = {}
    jobs_lock = Lock()

    def scenarios():
        items = []
        for path in sorted(scenarios_dir.glob("*/scenario.yaml")):
            try:
                doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                description = str(doc.get("goal", {}).get("description", "") or "")
                items.append({"id": path.parent.name, "description": description[:90]})
            except (OSError, yaml.YAMLError):
                continue
        return items

    def run_one(data: dict, run_id: str, job_id: str, repetition: int):
        from .runner import run_pipeline
        import argparse
        scenario_dir = scenarios_dir / data["scenario"]
        policy = None
        if not (scenario_dir / "policy.yaml").is_file():
            suffix = data["scenario"].rsplit("-L", 1)[-1]
            candidate = scenario_dir / f"i1-l{suffix}-policy.yaml"
            if candidate.is_file():
                policy = str(candidate)
        args = argparse.Namespace(
            scenario=data["scenario"], policy=policy, model=data["model"], run=run_id,
            model_version="unknown", agent_version="poc", provider=data.get("provider"),
            agent="internal", agent_runtime="host", attacker_container=None, attacker_image=None,
            command_profile=None, external_command=None, temperature=_number(data, "temperature", float),
            max_tokens=_number(data, "max_tokens"), run_token_budget=_number(data, "run_token_budget"),
            seed=_number(data, "seed"), repetition=repetition, upstream=data.get("upstream"),
            gateway_host="127.0.0.1", gateway_port=0, max_steps=_number(data, "max_steps"),
            timeout=_number(data, "timeout"), runs_dir=runs_dir, scenarios_dir=scenarios_dir,
            environments_dir=root / "environments", reset_target=bool(data.get("reset_target")),
            enforce_policy=bool(data.get("enforce_policy")), progress="quiet",
            # The UI runs the agent on the host; Docker-only relay names from
            # .env must not be used by this host-side path.
            model_endpoint="",
            cancel_event=stop_events[job_id],
        )
        try:
            if stop_events[job_id].is_set():
                status = "stopped"
                with jobs_lock:
                    jobs[job_id] = status
                return
            run_pipeline(args)
            status = "stopped" if stop_events[job_id].is_set() else "completed"
        except Exception as exc:  # keep the UI usable; runner artifacts hold detail when available
            status = f"failed: {type(exc).__name__}: {exc}"
        with jobs_lock:
            jobs[job_id] = status

    @app.get("/")
    def index():
        return render_template_string(PAGE)

    @app.get("/api/scenarios")
    def scenario_api():
        return jsonify(scenarios())

    @app.get("/api/runs")
    def runs_api():
        from scripts.aggregate import summarize as summarize_runs

        runs = []
        aggregate_groups = {}
        run_dirs = {p for p in runs_dir.glob("*") if p.is_dir()}
        if experiments_dir.is_dir():
            run_dirs.update(p.parent for p in experiments_dir.rglob("config.json"))
        for path in sorted(run_dirs, key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                config = json.loads((path / "config.json").read_text(encoding="utf-8"))
                result_path = path / "result.json"
                result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
                live = {}
                status_path = path / "status.json"
                if status_path.is_file():
                    try:
                        live = json.loads(status_path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        live = {}
                scenario = config.get("scenario") or "unknown"
                policy = config.get("policy") or "unknown"
                aggregate_groups.setdefault((scenario, policy), []).append({
                    "success": result.get("goal", {}).get("success", False),
                    "compliant": result.get("roe", {}).get("compliant", False),
                    "steps": result.get("metrics", {}).get("steps", 0),
                    "achieved_step": result.get("goal", {}).get("achieved_step"),
                    "valid": result.get("validity", {}).get("valid", True),
                    "invalid_reason": result.get("validity", {}).get("reason"),
                    "unclassified_rate": result.get("roe", {}).get("summary", {}).get("unclassified_rate", 0.0),
                    "declaration_accuracy": None,
                    "covert_rate": None,
                    "phantom": 0,
                    "covert": 0,
                    "categories": result.get("roe", {}).get("categories", {}),
                    "temperature": config.get("temperature"),
                    "repetition": config.get("repetition"),
                })
                source = "manual runs" if path.parent == runs_dir else f"auto {path.parent.name}"
                categories = result.get("roe", {}).get("categories", {})
                live_agent = live.get("agent", {})
                live_progress = live.get("progress", {})
                runs.append({"run_id": path.name, "scenario": config.get("scenario"), "model": config.get("model"), "source": source,
                             "status": result.get("status") or live.get("execution", {}).get("status") or "running", "success": result.get("goal", {}).get("success", False),
                             "steps": result.get("metrics", {}).get("steps") if result else live_agent.get("current_step"), "tokens": result.get("usage", {}).get("total_tokens"),
                             "live": {"state": live.get("state"), "step": live_agent.get("current_step"), "max_steps": live_agent.get("max_steps"),
                                      "event": live.get("last_event"), "stage": live_progress.get("current_stage"), "last_action": live_agent.get("last_action")},
                             "detail": {"termination_reason": result.get("termination", {}).get("reason"), "valid": result.get("validity", {}).get("valid", False), "roe": {key: value.get("status", "?") for key, value in sorted(categories.items())}}})
            except (OSError, json.JSONDecodeError):
                continue
        complete = [x for x in runs if x["status"] != "running"]
        steps = [x["steps"] for x in complete if isinstance(x["steps"], (int, float))]
        scenario_stats = {}
        for (scenario, policy), records in aggregate_groups.items():
            scenario_stats.setdefault(scenario, {})[policy] = summarize_runs(records)
        visible_runs = runs[:200]
        return jsonify({"runs": visible_runs, "scenario_stats": scenario_stats, "summary": {"total": len(runs), "success": sum(x["success"] for x in complete),
            "failed": sum(not x["success"] for x in complete), "avg_steps": round(sum(steps) / len(steps), 1) if steps else None}})

    @app.delete("/api/runs/<run_id>")
    def delete_run(run_id: str):
        candidates = [path for path in runs_dir.glob("*") if path.is_dir() and path.name == run_id]
        if experiments_dir.is_dir():
            candidates.extend(
                path.parent for path in experiments_dir.rglob("config.json")
                if path.parent.name == run_id
            )
        if len(candidates) != 1:
            return jsonify(error="run not found or ambiguous"), 404
        shutil.rmtree(candidates[0])
        return jsonify(run_id=run_id, deleted=True)

    @app.post("/api/run")
    def start_run():
        data = request.get_json(silent=True) or {}
        if not data.get("scenario") or not data.get("model") or not (scenarios_dir / data["scenario"] / "scenario.yaml").is_file():
            return jsonify(error="scenario와 model을 확인하세요."), 400
        repetitions = max(1, min(_number(data, "repeat") or 1, 100))
        parallel = max(1, min(_number(data, "parallel") or 1, 8))
        count = repetitions * parallel
        job_id = uuid4().hex[:8]
        with jobs_lock:
            jobs[job_id] = f"queued ({count} runs)"
            stop_events[job_id] = Event()
        executor = ThreadPoolExecutor(max_workers=parallel, thread_name_prefix="tempera-ui")
        for i in range(count):
            run_id = f"ui-{data['scenario']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{job_id}-r{i + 1}"
            executor.submit(run_one, data, run_id, job_id, i + 1)
        executor.shutdown(wait=False)
        return jsonify(job_id=job_id, count=count)

    @app.post("/api/jobs/<job_id>/stop")
    def stop_job(job_id: str):
        event = stop_events.get(job_id)
        if event is None:
            return jsonify(error="job not found"), 404
        event.set()
        with jobs_lock:
            jobs[job_id] = "stopping"
        return jsonify(job_id=job_id, status="stopping")

    @app.post("/api/jobs/stop-all")
    def stop_all_jobs():
        for event in stop_events.values():
            event.set()
        with jobs_lock:
            for job_id, status in jobs.items():
                if status.startswith("queued") or status == "running":
                    jobs[job_id] = "stopping"
        return jsonify(status="stopping")

    return app


def serve(root: Path | str = ".", host: str = "127.0.0.1", port: int = 5050) -> None:
    create_app(root).run(host=host, port=port, threaded=True)
