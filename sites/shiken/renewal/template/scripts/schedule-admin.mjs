import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import path from 'node:path';
async function automationState(){try{const a=JSON.parse(await readFile(new URL('schedule/automation.json',root),'utf8'));if(!/^[a-zA-Z0-9_-]+$/.test(a.id))return null;try{const t=await readFile(path.join(homedir(),'.codex','automations',a.id,'automation.toml'),'utf8');return {...a,status:t.match(/^status = "([^"]+)"/m)?.[1]||a.status,live:true};}catch{return {...a,live:false};}}catch{return null;}}

import {root,loadRegistry,digest,draft,candidate,changes,apply,acknowledge,loadMonitor,queue,checkSources} from './schedule-core.mjs';
import {prepareRelease,activateStaging,releaseStatus,rollbackStaging,deploymentPlan} from './release-core.mjs';
const origin='http://localhost:4179';
const server=http.createServer(async(req,res)=>{
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' http://localhost:4178; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'");
 const send=(code,data)=>{res.writeHead(code,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(data));};
 try{if(!['localhost:4179','127.0.0.1:4179'].includes(req.headers.host))return send(403,{error:'ローカルで開いてください'});const url=new URL(req.url,origin);
 if(req.method==='GET'&&url.pathname==='/api/state'){const r=await loadRegistry();return send(200,{registry:r,revision:digest(r),queue:queue(r,await loadMonitor()),monitor:await loadMonitor(),automation:await automationState()});}
 if(req.method==='GET'&&url.pathname==='/api/draft'){const r=await loadRegistry();return send(200,draft(r,url.searchParams.get('id'),await loadMonitor()));}
 if(req.method==='GET'&&url.pathname==='/api/release')return send(200,await releaseStatus());
 if(req.method==='POST'){
 if(![origin,'http://127.0.0.1:4179'].includes(req.headers.origin)||!req.headers['content-type']?.startsWith('application/json'))return send(403,{error:'管理画面から操作してください'});
 let body='',size=0;for await(const chunk of req){size+=chunk.length;if(size>3_000_000)throw Error('更新データが大きすぎます');body+=chunk;}const input=JSON.parse(body);
 if(url.pathname==='/api/check'){const r=await loadRegistry(),ids=input.ids||[];if(!Array.isArray(ids)||ids.length>r.exams.length||ids.some(id=>!r.meta[id]))throw Error('確認対象が不正です');return send(200,await checkSources(ids));}
 if(url.pathname==='/api/release/prepare')return send(200,await prepareRelease());
 if(url.pathname==='/api/release/stage')return send(200,await activateStaging(input.id));
 if(url.pathname==='/api/release/rollback')return send(200,await rollbackStaging());
 if(url.pathname==='/api/release/plan')return send(200,await deploymentPlan(input.id));
 if(url.pathname==='/api/diff'){const r=await loadRegistry();return send(200,{changes:changes(r,candidate(r,input)),beforeRevision:digest(r)});}
 if(url.pathname==='/api/apply'){const result=await apply(input);await acknowledge(input);return send(200,result);}
 return send(404,{error:'この操作はありません'});
 }
 if(req.method!=='GET')return send(405,{error:'この操作はありません'});
 if(url.pathname==='/illustration.png'){res.writeHead(200,{'Content-Type':'image/png'});res.end(await readFile(new URL('dist/assets/guide-decided.png',root)));return;}
 const paths={'/':'admin/index.html','/admin.js':'admin/admin.js','/admin.css':'admin/admin.css'};if(!paths[url.pathname])return send(404,{error:'見つかりません'});const file=paths[url.pathname];res.writeHead(200,{'Content-Type':file.endsWith('.js')?'text/javascript; charset=utf-8':file.endsWith('.css')?'text/css; charset=utf-8':'text/html; charset=utf-8'});res.end(await readFile(new URL(file,root)));
 }catch(e){send(400,{error:e.message});}
});server.listen(4179,'127.0.0.1',()=>console.log('日程管理: '+origin));
