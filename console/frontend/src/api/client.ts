const BASE=import.meta.env.VITE_API_URL??'http://localhost:8000';
const json=async(r:Response)=>{const body=await r.json().catch(()=>({}));if(!r.ok){const message=typeof body?.detail==='string'?body.detail:`Request failed (${r.status})`;throw new Error(message)}return body};
export const api={
 getScenarios:()=>fetch(`${BASE}/api/meta/scenarios`).then(json),
 getEnvStatus:()=>fetch(`${BASE}/api/env/status`).then(json),
 startEnvironment:()=>fetch(`${BASE}/api/env/start`,{method:'POST'}).then(json),
 getRuns:(scenario?:string)=>fetch(`${BASE}/api/runs${scenario?`?scenario=${encodeURIComponent(scenario)}`:''}`).then(json),
 startBatch:(body:unknown)=>fetch(`${BASE}/api/runs/batch`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(json),
 getBatch:(id:string)=>fetch(`${BASE}/api/runs/batch/${id}`).then(json),
 getActiveBatches:()=>fetch(`${BASE}/api/runs/batch`).then(json),
 getDetail:(id:string)=>fetch(`${BASE}/api/runs/${id}`).then(json),
 getActions:(id:string)=>fetch(`${BASE}/api/runs/${id}/actions`).then(json),
 getArtifacts:(id:string)=>fetch(`${BASE}/api/runs/${id}/artifacts`).then(json),
 getOverlay:(id:string)=>fetch(`${BASE}/api/runs/${id}/overlay`).then(json),
 getTerminal:(id:string)=>fetch(`${BASE}/api/runs/${id}/terminal`).then(json),
 deleteRun:(id:string)=>fetch(`${BASE}/api/runs/${encodeURIComponent(id)}`,{method:'DELETE'}).then(r=>{if(!r.ok)throw new Error('delete failed');return r.json()}),
 stopBatch:(id:string)=>fetch(`${BASE}/api/runs/batch/${id}/stop`,{method:'POST'}),
 stopRun:(id:string)=>fetch(`${BASE}/api/runs/${id}/stop`,{method:'POST'}),
 stream:(id:string,on:(x:any)=>void)=>{const source=new EventSource(`${BASE}/api/runs/${id}/stream`);source.onmessage=e=>on(JSON.parse(e.data));return source},
};
