export type Observation={service:string;observed_at:string;health:string;ready:boolean|null;telemetry_status:string;request_rate:number|null;error_rate:number|null;latency_p95:number|null};
export type Service={id:string;name:string;observation:Observation|null};
export type Incident={id:string;service_id:string;rule:string;status:string;severity:string;created_at:string};
export type Evidence={id:string;kind:string;source:string;data:Record<string,unknown>;created_at:string};
export type Event={id:string;created_at:string;details:Record<string,unknown>};
export type Findings={summary:string;probable_cause:string;confidence:string;confidence_meaning:string;supporting_evidence_ids:string[];contradicting_evidence_ids:string[];alternatives:string[];next_steps:string[];limitations:string[];expected_recovery:string;abort_conditions:string};
export type Investigation={provider:string;findings:Findings};
export type Action={id:string;incident_id:string;target:string;action:string;parameters:Record<string,unknown>;fingerprint:string;status:string;expires_at:string;result:Record<string,unknown>|null};
export type Audit={id:string;actor:string;event:string;subject:string;created_at:string};
export const pretty=(s:string)=>s.replaceAll('_',' ');
export const date=(s:string)=>new Date(s.endsWith('Z')||/[+-]\d\d:\d\d$/.test(s)?s:s+'Z').toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
export const pct=(n:number|null|undefined)=>n==null?'—':`${(n*100).toFixed(1)}%`;
export const ms=(n:number|null|undefined)=>n==null?'—':`${Math.round(n*1000)} ms`;
export async function api<T>(path:string,token?:string,body?:unknown):Promise<T>{
 const response=await fetch('/api/v1'+path,{method:body===undefined?'GET':'POST',headers:{...(body===undefined?{}:{'Content-Type':'application/json'}),...(token?{Authorization:`Bearer ${token}`}:{})},body:body===undefined?undefined:JSON.stringify(body)});
 if(!response.ok){const data=await response.json().catch(()=>({detail:'Request failed'}));throw new Error(typeof data.detail==='string'?data.detail:`Request failed (${response.status})`)}
 return response.json();
}
