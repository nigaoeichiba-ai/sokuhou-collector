// Makes the static site (HTML of every page, assets, sitemap, robots, .htaccess) from the browser templates in dist/, the schedule (schedule/registry.json)
// and the old articles (legacy/).  The same templates the visitor's browser runs are run here against a DOM, so the HTML a crawler gets is the page.
//
//   node scripts/build-site.mjs --out <folder>         the folder is made empty first
//   SHIKEN_TODAY=2026-11-13 node scripts/build-site.mjs --out <folder>   (tests: pretend it is that day, Japan time)
//
// Nothing here uploads anything; sites/shiken/build.py (the build of the deploy workflow) calls this, adds the contact receiver and the visit counter, and the workflow checks the result.
import './fake-date.mjs';
import {readFile,writeFile,cp,mkdir,readdir,rm,mkdtemp,chmod} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {parseHTML} from 'linkedom';
import {loadRegistry,digest,generated,today as jstToday} from './schedule-core.mjs';
import {redirects,loadLegacy,legacyMain,siteWideMain,siteWide,config,SITE_NAME} from './legacy-pages.mjs';
import {apacheConfig} from './apache-config.mjs';

const run=promisify(execFile);
const root=new URL('../',import.meta.url),rootDir=fileURLToPath(root);
export const origin='https://shiken-nittei.com';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function listFiles(dir,prefix=''){const files=[];for(const entry of await readdir(dir,{withFileTypes:true})){const rel=prefix+entry.name;if(entry.isDirectory())files.push(...await listFiles(path.join(dir,entry.name),rel+'/'));else files.push(rel);}return files.sort();}
async function sourceRevision(){const files={};for(const f of await listFiles(path.join(rootDir,'dist')))files['dist/'+f]=sha(await readFile(path.join(rootDir,'dist',f)));for(const f of await listFiles(path.join(rootDir,'legacy')))files['legacy/'+f]=sha(await readFile(path.join(rootDir,'legacy',f)));for(const f of ['scripts/build-site.mjs','scripts/render-pages.mjs','scripts/legacy-pages.mjs','scripts/apache-config.mjs','package-lock.json'])files[f]=sha(await readFile(path.join(rootDir,f)));return digest(files);}

export async function buildSite(out){
 const registry=await loadRegistry(),today=jstToday();
 const id='v'+sha(digest(registry)+await sourceRevision()).slice(0,12),prefix='/_versions/'+id;
 const source=await mkdtemp(path.join(os.tmpdir(),'shiken-src-'));
 try{
 await cp(path.join(rootDir,'dist'),source,{recursive:true});
 // the browser files are ES modules: this folder is outside the template, so it needs its own marker (Node reads .js as CommonJS otherwise; Deno does not care)
 await writeFile(path.join(source,'package.json'),'{"type":"module"}');
 const g=generated(registry);await writeFile(path.join(source,'schedule-records.js'),g.records);await writeFile(path.join(source,'expanded-catalog.js'),g.catalog);
 for(const name of await listFiles(source)){if(!/\.(js|html|css)$/.test(name))continue;const f=path.join(source,name);let text=await readFile(f,'utf8');text=text.replaceAll('/assets/',prefix+'/assets/');if(name==='index.html')text=text.replace(/(href|src)="\/(?!assets|_versions)([^"/]+\.(?:css|js))"/g,`$1="${prefix}/$2"`);await writeFile(f,text);}
 const result=await run(process.execPath,[path.join(rootDir,'scripts/render-pages.mjs'),source],{cwd:rootDir,maxBuffer:200*1024*1024,env:process.env});
 const pages=JSON.parse(result.stdout);
 const {document:shell}=parseHTML(pages[0].html);
 const legacy=await loadLegacy(root);
 // ---- pages that are not made by the browser templates: the old articles and the site-wide pages -----------------------------
 const crumbsOf={};
 const wrap=(main,{pathname,title,description,noindex,h1})=>{
  const doc=parseHTML(shell.toString()).document;
  doc.querySelector('main').innerHTML=main.html;
  doc.querySelector('script[src]').setAttribute('src',prefix+'/legacy.js');
  doc.querySelector('.skip-link').setAttribute('href','#legacy-title');doc.querySelector('.skip-link').textContent='本文へ進む';
  crumbsOf[pathname]=main.crumbs;
  pages.push({pathname,html:doc.toString(),title:title+'｜'+SITE_NAME,description,noindex});
 };
 for(const [slug,data] of Object.entries(legacy)){
  const main=legacyMain({slug,data,registry,today,prefix,legacy});
  wrap(main,{pathname:`/${slug}/`,title:data.title,description:data.description,noindex:config[slug].noindex});
 }
 for(const key of ['about','contact','privacy','thanks']){const p=siteWide[key];wrap(siteWideMain(key,prefix),{pathname:key==='thanks'?'/contact/thanks.html':`/${key}/`,title:p.title,description:p.description,noindex:p.noindex});}
 // ---- every page: title, description, robots, canonical, social tags, structured data ----------------------------------------
 const sitemap=[];const checked=Object.fromEntries(registry.exams.map(e=>[e.id,registry.meta[e.id].checkedAt]));
 const titles=new Set();
 for(const p of pages){
  const {document}=parseHTML(p.html);
  const title=p.title.includes(SITE_NAME)?p.title:p.title+'｜'+SITE_NAME;
  document.title=title;
  document.querySelector('meta[name=description]').setAttribute('content',p.description);
  document.querySelector('meta[name=robots]').setAttribute('content',p.noindex?'noindex,follow':'index,follow');
  const canonical=origin+p.pathname;
  const crumbs=crumbsOf[p.pathname]||autoCrumbs(p.pathname,registry,document);
  const ld=[{'@context':'https://schema.org','@type':'WebPage',url:canonical,name:title,description:p.description,inLanguage:'ja',isPartOf:{'@type':'WebSite',name:SITE_NAME,url:origin+'/'}}];
  if(crumbs&&crumbs.length>1)ld.push({'@context':'https://schema.org','@type':'BreadcrumbList',itemListElement:crumbs.map((c,i)=>({'@type':'ListItem',position:i+1,name:c.name,item:origin+c.url}))});
  document.head.insertAdjacentHTML('beforeend',`<link rel="canonical" href="${canonical}"><meta property="og:type" content="website"><meta property="og:site_name" content="${SITE_NAME}"><meta property="og:locale" content="ja_JP"><meta property="og:url" content="${canonical}"><meta property="og:title" content="${escape(title)}"><meta property="og:description" content="${escape(p.description)}"><meta property="og:image" content="${origin+prefix}/assets/hero-wide-v2.webp"><meta name="twitter:card" content="summary_large_image">${ld.map(x=>`<script type="application/ld+json">${JSON.stringify(x).replaceAll('<','\\u003c')}</script>`).join('')}`);
  if(p.pathname==='/')document.querySelector('#catalog-section, #catalog-cards')?.insertAdjacentHTML('afterend','<p class="small-note"><a href="/schedule/">掲載しているすべての試験・実施回を見る ›</a></p>');
  const shells={};for(const sid of ['home-page','guide-page','exam-page']){const element=document.getElementById(sid);if(element?.hasAttribute('hidden')&&element.innerHTML){shells[sid]=element.innerHTML;element.innerHTML='';}}
  if(Object.keys(shells).length){const script=document.createElement('script');script.type='application/json';script.id='page-shells';script.textContent=JSON.stringify(shells).replaceAll('<','\\u003c');document.body.appendChild(script);}
  const file=path.join(out,p.pathname.endsWith('.html')?p.pathname.slice(1):path.join(p.pathname.slice(1),'index.html'));
  await mkdir(path.dirname(file),{recursive:true});await writeFile(file,document.toString());
  if(!p.noindex){const exam=p.pathname.startsWith('/exams/')?p.pathname.split('/')[2]:null;sitemap.push([canonical,exam&&checked[exam]?checked[exam]:today]);}
  titles.add(title);
 }
 // ---- assets: one folder per version of the browser files (cached for a year) -------------------------------------------------
 await writeFile(path.join(source,'legacy.js'),`document.querySelector('.menu-toggle')?.addEventListener('click',()=>{const b=document.querySelector('.menu-toggle');const open=b.getAttribute('aria-expanded')!=='true';b.setAttribute('aria-expanded',String(open));document.querySelector('#main-nav').classList.toggle('menu-open',open);});`);
 await cp(source,path.join(out,'_versions',id),{recursive:true,filter:src=>!src.endsWith('index.html')});
 // the temporary folder was made private (mode 700) and cp copies the mode: on the server the web server could not read the folder (403 on every css/js/image, 2026-11-13).  Every folder of the site is public.
 for(const f of ['_versions/'+id,...(await listFiles(path.join(out,'_versions',id))).flatMap(n=>n.split('/').slice(0,-1).map((_,i,a)=>'_versions/'+id+'/'+a.slice(0,i+1).join('/')))])await chmod(path.join(out,f),0o755);
 await writeFile(path.join(out,'robots.txt'),`User-agent: *\nAllow: /\nSitemap: ${origin}/sitemap.xml\n`);
 await writeFile(path.join(out,'.htaccess'),apacheConfig());
 sitemap.sort((a,b)=>(a[0]==origin+'/'?-1:b[0]==origin+'/'?1:a[0].localeCompare(b[0])));
 await writeFile(path.join(out,'sitemap.xml'),`<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${sitemap.map(([loc,mod])=>`<url><loc>${loc}</loc><lastmod>${mod}</lastmod></url>`).join('\n')}\n</urlset>\n`);
 const nf=parseHTML(shell.toString()).document;
 nf.querySelector('main').innerHTML=`<article class="exam-detail legacy-page" data-theme="cream"><header class="ed-hero"><div><h1 id="legacy-title">お探しのページが見つかりませんでした</h1><p class="ed-intro">アドレスが変わったか、入力に誤りがあるようです。試験の名前から、もう一度探してみてください。</p><p><a class="text-link" href="/">トップページへ ›</a>　<a class="text-link" href="/schedule/">掲載している試験の一覧へ ›</a></p></div></header></article>`;
 nf.querySelector('script[src]').setAttribute('src',prefix+'/legacy.js');nf.querySelector('.skip-link').setAttribute('href','#legacy-title');nf.querySelector('.skip-link').textContent='本文へ進む';
 nf.title='ページが見つかりません｜'+SITE_NAME;nf.querySelector('meta[name=description]').setAttribute('content','お探しのページが見つかりませんでした。');nf.querySelector('meta[name=robots]').setAttribute('content','noindex,follow');
 await writeFile(path.join(out,'404.html'),nf.toString());
 return {id,pages:pages.length,today,files:(await listFiles(out)).length};
 }finally{await rm(source,{recursive:true,force:true});}
}
// breadcrumbs for the pages the browser templates make (the visible breadcrumb of the page has the same trail)
function autoCrumbs(pathname,registry){
 if(pathname==='/')return null;
 if(pathname.startsWith('/guides/'))return [{name:'トップ',url:'/'},{name:'状況から探す',url:'/#situations'},{name:guideName(pathname),url:pathname}];
 if(pathname.startsWith('/exams/')){const e=registry.exams.find(x=>x.id===pathname.split('/')[2]);return e?[{name:'トップ',url:'/'},{name:'試験を探す',url:'/guides/decided/'},{name:e.name+'（'+e.edition+'）',url:pathname}]:null;}
 return null;
}
const guideName=p=>({'/guides/decided/':'受ける試験が決まっている方','/guides/discover/':'これから選ぶ方','/guides/compare/':'複数の試験を受ける方','/guides/family/':'お子さんの入試を調べる方','/guides/prepared/':'申し込み済みの方'}[p]||'ご案内');

if(process.argv[1]&&fileURLToPath(import.meta.url)===path.resolve(process.argv[1])){
 const i=process.argv.indexOf('--out');if(i<0||!process.argv[i+1]){console.error('usage: node scripts/build-site.mjs --out <folder>');process.exit(2);}
 const out=path.resolve(process.argv[i+1]);
 await mkdir(out,{recursive:true});for(const f of await readdir(out))await rm(path.join(out,f),{recursive:true,force:true,maxRetries:10,retryDelay:100});
 try{console.log(JSON.stringify(await buildSite(out)));}catch(e){console.error(e.stack);process.exit(1);}
}
