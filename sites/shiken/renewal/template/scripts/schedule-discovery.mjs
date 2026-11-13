// Read-only discovery: candidates are evidence for review, never published dates.
const decode=s=>s.replace(/&amp;/gi,'&').replace(/&quot;/gi,'"').replace(/&#(?:x([0-9a-f]+)|(\d+));/gi,(_,h,d)=>{const n=parseInt(h||d,h?16:10);return n>=0&&n<=0x10ffff?String.fromCodePoint(n):'';}).replace(/&nbsp;/gi,' ');
export function discoverLinks(html,base,allowedHosts){
 const links=new Map();for(const match of html.matchAll(/<a\b[^>]*\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))[^>]*>([\s\S]*?)<\/a\s*>/gi)){
 const href=decode(match[1]||match[2]||match[3]||''),label=decode(match[4].replace(/<[^>]*>/g,' ')).replace(/\s+/g,' ').trim().slice(0,240);
 if(!href||href.startsWith('#'))continue;try{const u=new URL(href,base);u.hash='';if(u.protocol!=='https:'||u.username||u.password||u.port||!allowedHosts.has(u.hostname))continue;if(!/試験|検定|日程|要項|申込|申し込|出願|募集|選抜|実施|令和|20\d{2}|\.pdf(?:$|\?)/i.test(label+' '+u.pathname))continue;for(const key of [...u.searchParams.keys()])if(/^utm_|^fbclid$/i.test(key))u.searchParams.delete(key);if(u.href===base)continue;links.set(u.href,{url:u.href,label:label||u.pathname.split('/').pop()});}catch{}}
 return [...links.values()].slice(0,300);
}
export function observe(old,{url,hash,at,bytes,contentType,links}){
 const baseline=old.hash,changed=!!(old.changed||baseline&&baseline!==hash||old.url&&old.url!==url);
 const known=new Set((old.links||[]).map(x=>x.url));const additions=old.links?links.filter(x=>!known.has(x.url)):[];
 const candidates=new Map((old.linkCandidates||[]).map(x=>[x.url,x]));for(const link of additions)candidates.set(link.url,{...link,firstSeenAt:at,sourceHash:hash});
 return {...old,url,hash,firstHash:old.firstHash||hash,checkedAt:at,changed,error:null,firstObservation:!baseline,bytes,contentType,links,linkCandidates:[...candidates.values()]};
}
export function unreviewedLinks(monitor,profileId,sourceId){return (monitor.sources[sourceId]?.linkCandidates||[]).filter(x=>!monitor.linkReviews?.[profileId]?.[sourceId]?.[x.url]);}
