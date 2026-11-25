// The table and the counts of /koko-tsuikensa-2027/ are made from schedule/registry.json at build time.
// SPEC names, for each prefecture, the rows that are the main exam, the make-up exam and the result.
// A label that no longer exists, or a change in which prefectures announce results on/before the make-up day, stops the build,
// because the sentences of the article name those prefectures.
export const SLUG='koko-tsuikensa-2027';
// [name in the table, exam id, main exam labels, make-up label, result label]
export const SPEC=[
 ['北海道','hokkaido',['一般選抜 学力検査'],'一般選抜 追検査','合格発表'],
 ['岩手県','iwate',['一次募集・杜陵定時制前期 本検査'],'一次募集 追検査','一次募集 合格発表'],
 ['宮城県','miyagi',['第一次募集 本検査'],'第一次募集 追試験','合格発表'],
 ['秋田県','akita',['1次募集 本検査'],'1次募集 追検査','1次募集 合否通知'],
 ['山形県','yamagata',['後期一般 学力検査','後期一般 適性検査'],'後期一般 追検査（学力）','前期・後期 合格発表'],
 ['茨城県','ibaraki',['学力検査'],'追検査（学力）','合格発表'],
 ['栃木県','tochigi',['一般・特色選抜 学力検査'],'追検査（学力）','合格発表'],
 ['群馬県','gunma',['本検査'],'追検査','合格発表'],
 ['千葉県','chiba',['本検査'],'追検査','入学許可候補者発表'],
 ['神奈川県','kanagawa',['共通選抜 学力検査','特色検査・面接等'],'追検査','合格発表'],
 ['新潟県','niigata',['一般選抜 学力検査'],'一般選抜 追検査','一般選抜 合格発表'],
 ['富山県','toyama',['全日制一般 学力検査'],'全日制一般 追検査','全日制一般・推薦 最終合格発表'],
 ['石川県','ishikawa',['全日制一般 学力検査等'],'一般入学 追検査','一般・推薦 合格発表'],
 ['岐阜県','gifu',['第一次選抜 検査','第一次選抜 検査（一部校）'],'第一次選抜 追検査','合格発表'],
 ['静岡県','shizuoka',['一般・特別選抜 学力検査・面接等'],'追検査','合格発表'],
 ['滋賀県','shiga',['一次募集 学力検査'],'一次募集 追検査（学力検査）','一次募集 入学許可予定者発表'],
 ['奈良県','nara',['一次選抜 学力検査等'],'追検査','合格発表'],
 ['鳥取県','tottori',['一般選抜 検査'],'一般選抜 追検査','一般選抜 合格発表'],
 ['島根県','shimane',['一般選抜 学力検査'],'一般選抜 追検査','一般選抜 合格情報掲載'],
 ['岡山県','okayama',['一般入学者選抜 学力検査','一般入学者選抜 面接・実技'],'一般入学者選抜 追検査','一般・特別 合格発表'],
 ['広島県(併設型以外)','hiroshima',['一次選抜（併設型以外）学力検査・自己表現等'],'一次選抜（併設型以外）追検査','一次選抜（併設型以外）合格発表'],
 ['香川県','kagawa',['一般選抜 学力検査','一般選抜 適性検査・面接'],'追検査（学力・面接）','一般選抜 合格者発表'],
 ['愛媛県','ehime',['一般入学者選抜 検査'],'一般入学者選抜 追検査','一般・特色 合格発表'],
 ['佐賀県','saga',['一般選抜 検査'],'一般選抜 追検査','一般選抜 合格発表'],
 ['熊本県','kumamoto',['後期一般 検査'],'後期一般 追検査','前期・後期 合格発表'],
 ['宮崎県','miyazaki',['一般選抜 学力検査'],'一般選抜 追検査','一般・推薦等 合格発表'],
 ['長野県(後期)','nagano',['後期選抜 検査'],'後期選抜 追検査','後期選抜 合格発表'],
 ['山梨県(後期)','yamanashi',['後期募集・定時制 検査'],'後期募集・定時制 追検査','前期・後期 入学許可予定者発表'],
 ['福島県(前期)','fukushima',['前期・連携型選抜 学力検査'],'前期・連携型選抜 追検査','前期・連携型選抜 結果発表'],
 ['徳島県','tokushima',['一般選抜 学力検査'],'一般選抜 追検査・追面接','一般選抜 結果通知'],
 ['福井県','fukui',['一般選抜 学力検査(1日目)','一般選抜 学力検査(2日目)'],'一般選抜 追検査(1日目)','一般選抜 合格者発表'],
 ['長崎県','nagasaki',['一般選抜 学力検査(1日目)','一般選抜 学力検査(2日目)'],'一般選抜 追検査','一般選抜 合格者発表'],
 ['沖縄県','okinawa',['一般選抜 学力検査(1日目)','一般選抜 学力検査(2日目)'],'一般選抜 追検査','特色選抜・一般選抜 合格発表']
];
const W=['日','月','火','水','木','金','土'];
const day=iso=>new Date(iso+'T00:00:00Z');
const md=iso=>{const d=day(iso);return `${d.getUTCMonth()+1}月${d.getUTCDate()}日(${W[d.getUTCDay()]})`;};
const between=(a,b)=>Math.round((day(b)-day(a))/86400000);

export function tsuikensaRows(registry){
 return SPEC.map(([name,id,mainLabels,makeLabel,resultLabel])=>{
  const exam='koko-'+id;
  const dates=label=>{const found=registry.rows.filter(r=>r.exam===exam&&r.label===label).map(r=>r.date).sort();if(!found.length)throw new Error(`tsuikensa: ${exam} has no row "${label}"`);return found;};
  const last=mainLabels.flatMap(dates).sort().at(-1),make=dates(makeLabel)[0],result=dates(resultLabel).at(-1);
  return {name,exam,short:name.replace(/\(.*\)$/,''),last,make,result,gap:between(last,make),after:between(make,result)};
 });
}
const dist=(values,unit)=>[...new Set(values)].sort((a,b)=>a-b).map(v=>`${v}日後が${values.filter(x=>x===v).length}${unit}`).join('、');
export function tsuikensaValues(registry){
 const rows=tsuikensaRows(registry);
 const gaps=rows.map(r=>r.gap),min=Math.min(...gaps),max=Math.max(...gaps);
 const names=list=>list.map(r=>r.short);
 const same=rows.filter(r=>r.after===0),before=rows.filter(r=>r.after<0);
 if(names(same).join()!=='岡山県,熊本県')throw new Error('tsuikensa: the prefectures with the result on the make-up day changed: '+names(same).join());
 if(names(before).join()!=='石川県,奈良県'||before.some(r=>r.after!==-1))throw new Error('tsuikensa: the prefectures with the result before the make-up day changed: '+names(before).join());
 const naraNotice=registry.rows.find(r=>r.exam==='koko-nara'&&r.label==='追検査 合格発表');
 if(!naraNotice)throw new Error('tsuikensa: koko-nara has no row "追検査 合格発表"');
 const ends=v=>rows.filter(r=>r.gap===v);
 const resultCell=r=>r.after>0?`追検査の${r.after}日後`:r.after===0?'追検査と同じ日':`追検査の${-r.after}日前`;
 const table=`<div class="tablewrap"><table class="ed-table"><caption>追検査の日程(令和9年度・${rows.length}道県)</caption><thead><tr><th>道県</th><th>学力検査の最終日</th><th>追検査(初日)</th><th>学力検査の最終日から</th><th>合格発表</th><th>追検査の初日から発表まで</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${r.name}</td><td>${md(r.last)}</td><td>${md(r.make)}</td><td>${r.gap}日</td><td>${md(r.result)}</td><td>${resultCell(r)}</td></tr>`).join('')}</tbody></table></div>`;
 const asOf=day(rows.map(r=>registry.meta[r.exam].checkedAt).sort().at(-1));
 const extreme=v=>{const r=ends(v);return `${r.map(x=>x.short).join('・')}の${v}日後(${r.map(x=>`${md(x.last)}→${md(x.make)}`).join('、')})`;};
 return {
  N:rows.length,N57:gaps.filter(g=>g>=5&&g<=7).length,MIN:min,MAX:max,
  MINPREF:ends(min).map(r=>r.short).join('・'),MAXPREF:ends(max).map(r=>r.short).join('・'),
  MINTEXT:extreme(min),MAXTEXT:extreme(max),
  GAPDIST:dist(gaps,'県'),RESULTDIST:dist(rows.filter(r=>r.after>0).map(r=>r.after),'県'),
  AFTER:rows.filter(r=>r.after>0).length,
  ISHIKAWA_RESULT:md(before[0].result),ISHIKAWA_MAKE:md(before[0].make),
  NARA_RESULT:md(before[1].result),NARA_MAKE:md(before[1].make),NARA_NOTICE:md(naraNotice.date),
  ASOF:`${asOf.getUTCFullYear()}年${asOf.getUTCMonth()+1}月${asOf.getUTCDate()}日`,
  TABLE:table
 };
}
// Replaces {{TK_…}} in every text of the article; a placeholder without a value stops the build.
export function fillTsuikensa(legacy,registry){
 if(!legacy[SLUG])return legacy;
 const values=tsuikensaValues(registry);
 const fill=v=>typeof v==='string'?v.replace(/\{\{TK_([A-Z0-9_]+)\}\}/g,(m,key)=>{if(!(key in values))throw new Error('tsuikensa: unknown placeholder '+m);return String(values[key]);})
  :Array.isArray(v)?v.map(fill):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).map(([k,x])=>[k,fill(x)])):v;
 return {...legacy,[SLUG]:fill(legacy[SLUG])};
}
