import {scheduleSnapshot} from './schedule-records.js';
import {scheduleRows,CHECKED_AT} from './official-schedule.js';
export const types={deadline:{label:'申込締切',class:'peach'},exam:{label:'試験日',class:'mint'},result:{label:'結果発表等',class:'lavender'}};
export const exams=scheduleSnapshot.exams;
export const events=scheduleRows.map(row=>{const exam=exams.find(e=>e.id===row.exam);return {...row,time:row.time||'',note:row.note||'',checkedAt:row.checkedAt||CHECKED_AT,name:exam.name,short:exam.short,aliases:exam.aliases,edition:exam.edition};});
export const guides=[
 {id:'decided',title:'受ける試験が決まっている',desc:'受けたい試験の名前を入れると、申込の締切と試験日をまとめて確認できます。TOEIC・英検・簿記・FP・宅建など、掲載している試験の日程を一覧で探せます。',sub:'日程・申込方法を確認',art:'planner',intro:'受けたい試験の名前を入れてみてください。申込の締切と試験日を、まとめて確認できます。'},
 {id:'discover',title:'資格をこれから選びたい',desc:'受ける試験がまだ決まっていない方向けに、分野や受けられそうな時期から資格・試験を探せます。気になる試験の日程と申込期限もあわせて確認できます。',sub:'目的や時期から探す',art:'books',intro:'何を受けるか、まだ決まっていなくても大丈夫です。気になる分野や、受けられそうな時期から見てみませんか。'},
 {id:'compare',title:'複数の試験を受けたい',desc:'複数の資格・試験を受けたい方向けに、申込締切と試験日を並べて比べられます。保存した試験から選んで、月ごとの予定として並べられます。日程の重なりや、準備に使える時間も確認できます。',sub:'日程を並べて比較',art:'calendars',intro:'受けたい試験を並べてみましょう。申込の締切や試験日が重なっていないか、ここで確かめられます。'},
 {id:'family',title:'お子さんの入試を調べたい',desc:'ご家族が受験する方向けに、出願から入学手続きまでの日程と、準備しておきたいことを整理しました。大学入試・高校入試の出願日や、当日の準備の目安も確認できます。',sub:'出願から入学手続きまで',art:'family',intro:'お子さんと一緒に、これからの予定を確認してみませんか。出願や入学手続きの期限も、学校ごとの案内で確かめておきましょう。'},
 {id:'prepared',title:'申込は済んでいる',desc:'申し込みが済んだ方向けに、受験票・持ち物・当日の流れを試験ごとのチェックリストで確認できます。試験までにやることと、試験のあとの手続きも整理しました。',sub:'当日の準備・合格発表を確認',art:'bag',intro:'申込、おつかれさまでした。受験票や持ち物、会場への行き方など、当日までに気になることを少しずつ確認しておきましょう。'}
];
