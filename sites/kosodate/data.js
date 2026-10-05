/* Every item below was checked against the cited primary source on `verifiedAt`.
   Wording stays within what the source states; anything not verified is NOT listed. */
window.KOSODATE_ITEMS = [
  {
    id: 'birth-report',
    title: '出生届を出す',
    category: '手続き',
    rule: { type: 'days', start: 0, end: 13 },
    when: '出生の日から14日以内(出生日を1日目と数えます)',
    body: '子の出生地・本籍地または届出人の所在地の市区町村役場に提出します。国外で出生した場合は3か月以内です。',
    basis: '戸籍法第43条・第49条',
    source: { label: '法務省「出生届」', url: 'https://www.moj.go.jp/ONLINE/FAMILYREGISTER/5-1.html' },
    verifiedAt: '2026-10-05'
  },
  {
    id: 'child-allowance',
    title: '児童手当の認定請求をする',
    category: '手続き',
    rule: { type: 'days', start: 1, end: 15 },
    when: '出生日の翌日から数えて15日以内',
    body: '期限を過ぎると、原則として遅れた月分の手当を受けられなくなります。請求先はお住まいの市区町村です(公務員の方は勤務先)。',
    basis: 'こども家庭庁「児童手当Q&A」',
    source: { label: 'こども家庭庁 児童手当Q&A', url: 'https://www.cfa.go.jp/policies/kokoseido/jidouteate/faq/ippan' },
    verifiedAt: '2026-10-05'
  },
  {
    id: 'rota',
    title: 'ロタウイルスワクチンの初回接種',
    category: '予防接種',
    rule: { type: 'weeks', start: 8, end: 14 },
    when: '生後8〜14週(標準的な初回接種の時期)',
    body: '接種のスケジュールは、かかりつけ医と相談して決めてください。',
    basis: '厚生労働省「生後2か月から推奨される予防接種」',
    source: { label: '厚生労働省', url: 'https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/kenkou/kekkaku-kansenshou/yobou-sesshu/vaccine/months-2.html' },
    verifiedAt: '2026-10-05'
  },
  {
    id: 'vaccines-2m',
    title: '生後2か月から: 5種混合・小児用肺炎球菌・B型肝炎の接種開始',
    category: '予防接種',
    rule: { type: 'months', start: 2, end: null },
    when: '生後2か月から初回の接種を始めます',
    body: '5種混合と小児用肺炎球菌は、一定の間隔をあけて追加の接種があります。間隔と回数はかかりつけ医や市区町村の案内で確認してください。',
    basis: '厚生労働省「生後2か月から推奨される予防接種」',
    source: { label: '厚生労働省', url: 'https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/kenkou/kekkaku-kansenshou/yobou-sesshu/vaccine/months-2.html' },
    verifiedAt: '2026-10-05'
  },
  {
    id: 'vaccines-1y',
    title: '1歳ごろ: MR・水痘の接種開始、5種混合・肺炎球菌の追加接種',
    category: '予防接種',
    rule: { type: 'months', start: 12, end: null },
    when: '1歳になったら',
    body: 'MR(麻しん・風しん)は1歳と小学校入学前の2回接種です。水痘は1歳から。5種混合と小児用肺炎球菌は1歳ごろに追加の接種を行います。',
    basis: '厚生労働省「1歳頃から推奨される予防接種」',
    source: { label: '厚生労働省', url: 'https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/kenkou/kekkaku-kansenshou/yobou-sesshu/vaccine/years-1.html' },
    verifiedAt: '2026-10-05'
  },
  {
    id: 'school-health-check',
    title: '就学時健康診断',
    category: '入学準備',
    rule: { type: 'school', start: { y: -1, m: 11, d: 1 }, end: { y: -1, m: 12, d: 1 } },
    when: '入学の前の年の11月初め〜12月初めごろまで',
    body: '法令上は、学齢簿が作成された後、翌学年の初めから4か月前までの間に行うこととされています(手続に支障がなければ3か月前まで)。実際の日程は市区町村が決め、通知します。',
    basis: '学校保健安全法施行令第1条、学校教育法施行令第2条',
    source: { label: 'e-Gov 学校保健安全法施行令', url: 'https://laws.e-gov.go.jp/law/333CO0000000174' },
    verifiedAt: '2026-10-05'
  },
  {
    id: 'entry-notice',
    title: '小学校の入学期日などの通知が届く',
    category: '入学準備',
    rule: { type: 'school', start: null, showFrom: { y: -1, m: 11, d: 1 }, end: { y: 0, m: 2, d: 1 } },
    when: '入学する年の2月初めまでに',
    body: '市町村の教育委員会は、翌学年の初めから2か月前までに、保護者へ入学期日を通知することになっています。学校が複数ある場合は、通学する学校も指定されます。',
    basis: '学校教育法施行令第5条',
    source: { label: 'e-Gov 学校教育法施行令', url: 'https://laws.e-gov.go.jp/law/328CO0000000340' },
    verifiedAt: '2026-10-05'
  }
];
