import {readFile,writeFile} from 'node:fs/promises';
import {loadRegistry,build,draft,candidate,changes,apply,acknowledge,loadMonitor,queue,checkSources,rollback,dailyCheck} from './schedule-core.mjs';
const [command,arg,out]=process.argv.slice(2);
try{const r=await loadRegistry();switch(command){
case 'build':await build(r);console.log('トップ・詳細・一覧の共通データを生成しました');break;
case 'rollback':console.log(await rollback(arg));break;
case 'daily':console.log(JSON.stringify(await dailyCheck(),null,2));break;
case 'status':console.log(JSON.stringify(queue(r,await loadMonitor()),null,2));break;
case 'draft':if(!arg||!out)throw Error('draft 試験ID 出力ファイル');await writeFile(out,JSON.stringify(draft(r,arg,await loadMonitor()),null,2));console.log('下書きを保存しました: '+out);break;
case 'diff':{const p=JSON.parse(await readFile(arg,'utf8'));console.log(JSON.stringify(changes(r,candidate(r,p)),null,2));break;}
case 'apply':{const p=JSON.parse(await readFile(arg,'utf8'));console.log(await apply(p));await acknowledge(p);break;}
case 'check':{const ids=arg==='--pending'?queue(r,await loadMonitor()).filter(x=>x.reasons.length||x.due).map(x=>x.id):arg?[arg]:[];if(!ids.length)throw Error('check 試験ID または check --pending');console.log(await checkSources(ids));break;}
default:console.log('node scripts/schedule-manager.mjs status | build | draft ID FILE | diff FILE | apply FILE | check ID | check --pending');}
}catch(e){console.error(e.message);process.exitCode=1;}
