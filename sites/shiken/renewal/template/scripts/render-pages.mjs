import './fake-date.mjs';
import {readFile} from 'node:fs/promises';
import {parseHTML} from 'linkedom';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
// Run the actual client templates against a DOM. There is no separate SEO copy.
const source=path.resolve(process.argv[2]||'dist');
const {window,document}=parseHTML(await readFile(path.join(source,'index.html'),'utf8'));
const location=new URL('https://shiken-nittei.com/');
const history={replaceState(_s,_t,url){location.href=new URL(url,location).href;},pushState(_s,_t,url){location.href=new URL(url,location).href;}};
Object.assign(globalThis,{window,document,location,history,__SSG__:true,requestAnimationFrame:()=>0,matchMedia:()=>({matches:false})});
window.scrollTo=()=>{};window.localStorage={getItem:()=>null,setItem:()=>{}};
// linkedom deliberately implements select.value as getter-only; browser templates set it.
Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(value){this.querySelectorAll('option').forEach(o=>o.toggleAttribute('selected',o.value===String(value)));}});
const {route}=await import(pathToFileURL(path.join(source,'app.js')));
const {normalizeLinks}=await import(pathToFileURL(path.join(source,'routes.js')));
const {exams,guides}=await import(pathToFileURL(path.join(source,'data.js')));
const out=[];
for(const pathname of ['/',...guides.map(g=>'/guides/'+g.id+'/'),...exams.map(e=>'/exams/'+e.id+'/')]){
 location.href='https://shiken-nittei.com'+pathname;route();normalizeLinks();
 out.push({pathname,html:document.toString(),title:document.title,description:document.querySelector('meta[name=description]').content});
}
process.stdout.write(JSON.stringify(out));
