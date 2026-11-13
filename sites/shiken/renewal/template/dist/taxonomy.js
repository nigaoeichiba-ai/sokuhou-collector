// The source imports used English field codes. Keep one explicit mapping everywhere.
export const fieldLabels={language:'語学',it:'IT',business:'ビジネス',medical:'医療',school:'大学入試'};
export const knownFields=new Set(['語学','会計','医療','金融','不動産','大学入試','高校入試','法律・不動産','法律・労務','医療・福祉','経営・会計','公務員','IT','ビジネス']);
export const fieldLabel=field=>fieldLabels[field]||field;
export function categoryFor(exam){const field=fieldLabel(exam.field);if(!knownFields.has(field))throw Error('未定義の分野です: '+field);return field==='大学入試'?'university':field==='高校入試'?'school':'qualification';}
