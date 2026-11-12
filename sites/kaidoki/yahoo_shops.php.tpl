<?php
// 「いま割引が多いYahoo!ショッピングの店」の欄のデータ(sites/kaidoki/shops.py が yahoo_shops.php.tpl から作る。手で直さない)。
// 店のデータ(店名・件数・店のURL)は、公開のファイルではない。サーバーの非公開フォルダ ~/__PRIVATE__/ (Web の外)に、毎日 06:00 の kaidoki-sale-daily が置く。
// このファイルは、そこから欄の中身だけを出す:
//   GET -> {"u": "YYYY-MM-DD"(取得した日), "genres": [{"s": ジャンルID, "shops": [{"n": 店名, "c": 件数, "lo": 割引率の下, "hi": 割引率の上, "e": 終了日, "r": 店の評価, "rc": 評価の件数, "h": リンク}]}]}
//   データが無い・__MAX_AGE__日より古い・読めないときは genres が空(ページは欄を出さない)。
// 同じサイトのページからの要求だけ。1日の回数の上限あり。
date_default_timezone_set('Asia/Tokyo');
header('X-Robots-Tag: noindex');
header('Cache-Control: no-store');
header('Content-Type: application/json; charset=UTF-8');
function out($code, $data = null) {
    http_response_code($code);
    if ($data !== null) { echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES); }
    exit;
}
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') { out(405); }
$fs = (string)($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '');
if ($fs !== '' && $fs !== 'same-origin') { out(403); }
$ref = (string)($_SERVER['HTTP_REFERER'] ?? '');
if ($ref !== '' && strpos($ref, '__SITE_URL__/') !== 0) { out(403); }
$home = dirname(__DIR__, 3);                                                           // public_html/api/yahoo-shops.php -> the home of the server account
$priv = $home . '/__PRIVATE__';
$work = $priv . '/api-limits';
if (!is_dir($work) && !@mkdir($work, 0700, true)) { out(503); }

$ip = (string)($_SERVER['REMOTE_ADDR'] ?? '');
$who = substr(hash('sha256', $ip . '|' . date('Y-m-d') . '|yshops'), 0, 16);
foreach ((glob($work . '/yshops-*') ?: array()) as $f) { if (strpos($f, '/yshops-' . date('Ymd') . '-') === false) { @unlink($f); } }
$h = @fopen($work . '/yshops-' . date('Ymd') . '-' . $who, 'c+');
if ($h) {
    $over = false;
    if (flock($h, LOCK_EX)) {
        $n = (int)stream_get_contents($h);
        if ($n >= 600) { $over = true; } else { ftruncate($h, 0); rewind($h); fwrite($h, (string)($n + 1)); fflush($h); }
        flock($h, LOCK_UN);
    }
    fclose($h);
    if ($over) { out(429); }
}

$empty = array('u' => '', 'genres' => array());
$raw = @file_get_contents($priv . '/__DB__');
if ($raw === false) { out(200, $empty); }
$db = json_decode($raw, true);
if (!is_array($db) || !isset($db['updated']) || !is_string($db['updated']) || preg_match('/^\d{4}-\d{2}-\d{2}$/', $db['updated']) !== 1) { out(200, $empty); }
$today = date('Y-m-d');
$age = (int)round((strtotime($today) - strtotime($db['updated'])) / 86400);
if ($age < 0 || $age > __MAX_AGE__) { out(200, $empty); }                              // an old day is not shown

$genres = array();
foreach (json_decode('__GENRES__', true) as $slug) {
    $rows = array();
    $src = (isset($db['genres'][$slug]) && is_array($db['genres'][$slug])) ? $db['genres'][$slug] : array();
    foreach ($src as $r) {
        if (!is_array($r) || !isset($r['id'], $r['n'], $r['c'], $r['lo'], $r['hi'], $r['e'], $r['r'], $r['rc'])) { continue; }
        if (!is_string($r['id']) || preg_match('/^[A-Za-z0-9_.-]{1,60}$/', $r['id']) !== 1) { continue; }
        if (!is_string($r['e']) || $r['e'] < $today) { continue; }                      // a shop whose sale has ended is not shown
        // the ValueCommerce MyLink, in the form of redesign/affiliate.py (vc_href): the store's own page as vc_url
        $rows[] = array('n' => (string)$r['n'], 'c' => (int)$r['c'], 'lo' => (int)$r['lo'], 'hi' => (int)$r['hi'], 'e' => $r['e'], 'r' => (float)$r['r'], 'rc' => (int)$r['rc'],
                        'h' => '//ck.jp.ap.valuecommerce.com/servlet/referral?sid=__VC_SID__&pid=__VC_PID__&vc_url=' . rawurlencode('https://store.shopping.yahoo.co.jp/' . $r['id'] . '/'));
        if (count($rows) >= __MAX_SHOPS__) { break; }
    }
    if (count($rows) >= __MIN_SHOPS__) { $genres[] = array('s' => $slug, 'shops' => $rows); }
}
out(200, count($genres) ? array('u' => $db['updated'], 'genres' => $genres) : $empty);
