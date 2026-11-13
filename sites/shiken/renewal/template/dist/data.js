import {scheduleSnapshot} from './schedule-records.js';
import {scheduleRows,CHECKED_AT} from './official-schedule.js';
export const types={deadline:{label:'申込締切',class:'peach'},exam:{label:'試験日',class:'mint'},result:{label:'結果発表等',class:'lavender'}};
export const exams=scheduleSnapshot.exams;
export const events=scheduleRows.map(row=>{const exam=exams.find(e=>e.id===row.exam);return {...row,time:row.time||'',note:row.note||'',checkedAt:row.checkedAt||CHECKED_AT,name:exam.name,short:exam.short,aliases:exam.aliases,edition:exam.edition};});
export const guides=[
 {id:'decided',title:'受ける試験が決まっている',sub:'日程・申込方法を確認',art:'planner',intro:'受けたい試験の名前を入れてみてください。申込の締切と試験日を、まとめて確認できます。'},
 {id:'discover',title:'資格をこれから選びたい',sub:'目的や時期から探す',art:'books',intro:'何を受けるか、まだ決まっていなくても大丈夫です。気になる分野や、受けられそうな時期から見てみませんか。'},
 {id:'compare',title:'複数の試験を受けたい',sub:'日程を並べて比較',art:'calendars',intro:'受けたい試験を並べてみましょう。申込の締切や試験日が重なっていないか、ここで確かめられます。'},
 {id:'family',title:'お子さんの入試を調べたい',sub:'出願から入学手続きまで',art:'family',intro:'お子さんと一緒に、これからの予定を確認してみませんか。出願や入学手続きの期限も、学校ごとの案内で確かめておきましょう。'},
 {id:'prepared',title:'申込は済んでいる',sub:'当日の準備・合格発表を確認',art:'bag',intro:'申込、おつかれさまでした。受験票や持ち物、会場への行き方など、当日までに気になることを少しずつ確認しておきましょう。'}
];
