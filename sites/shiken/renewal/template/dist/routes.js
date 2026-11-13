export const examPath=id=>'/exams/'+encodeURIComponent(id)+'/';
export const guidePath=id=>'/guides/'+encodeURIComponent(id)+'/';
export function fromHash(hash){return hash.replace(/^#\/exam\/([^?]+)/,(_,id)=>examPath(id)).replace(/^#\/guide\/([^?]+)/,(_,id)=>guidePath(id)).replace(/^#\/$/,'/');}
export function routeHash(pathname,search='',hash=''){const m=pathname.match(/^\/(exams|guides)\/([^/]+)\/?$/);return m?'#/'+(m[1]==='exams'?'exam':'guide')+'/'+m[2]+search:hash;}
export function normalizeLinks(root=document){root.querySelectorAll('a[href]').forEach(a=>{const href=a.getAttribute('href');if(href.startsWith('#/'))a.setAttribute('href',fromHash(href));else if(/^#(calendar-section|situations|saved-section)$/.test(href))a.setAttribute('href','/'+href);});}
