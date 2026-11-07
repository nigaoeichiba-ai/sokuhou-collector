<?php
// The product shelves of the pages (made by sokuhou/mallstore.py from mallshelf.php.tpl; do not edit by hand).
// The shops' data (picture, product page, price) is NOT a public file: it lives in the private folder ~/__PRIVATE__/ (outside the web root), put there once a day by the
// mall-refresh workflow.  This script gives out only what a page needs, a few products of ONE shelf at a time (Rakuten Web Service terms, Article 10 (1) (9)):
//   ?s=<shelf id>   -> {"u": "YYYY-MM-DD" (the day the data was taken), "items": [{"i": picture, "h": the affiliate link, "p": price}, ...]}   (items: [] when the shelf has nothing)
// Same-site requests only, and a daily limit per sender.
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
if ($fs !== '' && $fs !== 'same-origin') { out(403); }                                 // a browser that says the request comes from elsewhere
$ref = (string)($_SERVER['HTTP_REFERER'] ?? '');
if ($ref !== '' && strpos($ref, '__SITE_URL__/') !== 0) { out(403); }                  // the pages of this site only
$home = dirname(__DIR__, 3);                                                           // public_html/api/shelf.php -> the home of the server account
$priv = $home . '/__PRIVATE__';
$work = $priv . '/api-limits';
if (!is_dir($work) && !@mkdir($work, 0700, true)) { out(503); }

// A daily limit per sender (a salted daily hash of the address in a counter file; the address itself is never stored).
$ip = (string)($_SERVER['REMOTE_ADDR'] ?? '');
$who = substr(hash('sha256', $ip . '|' . date('Y-m-d') . '|shelf'), 0, 16);
foreach ((glob($work . '/rate-*') ?: array()) as $f) { if (strpos($f, '/rate-' . date('Ymd') . '-') === false) { @unlink($f); } }
$h = @fopen($work . '/rate-' . date('Ymd') . '-' . $who, 'c+');
if ($h) {
    $over = false;
    if (flock($h, LOCK_EX)) {
        $n = (int)stream_get_contents($h);
        if ($n >= __LIMIT__) { $over = true; } else { ftruncate($h, 0); rewind($h); fwrite($h, (string)($n + 1)); fflush($h); }
        flock($h, LOCK_UN);
    }
    fclose($h);
    if ($over) { out(429); }
}

$s = $_GET['s'] ?? '';
if (!is_string($s) || preg_match('/^[a-z0-9_-]{1,40}$/', $s) !== 1) { out(400); }
$raw = @file_get_contents($priv . '/__DB__');
if ($raw === false) { out(200, array('u' => '', 'items' => array())); }              // no data yet: the page shows nothing
$db = json_decode($raw, true);
if (!is_array($db)) { out(503); }
$rows = (isset($db['shelves'][$s]) && is_array($db['shelves'][$s])) ? $db['shelves'][$s] : array();
$items = array();
foreach (array_slice($rows, 0, 6) as $r) {
    if (!isset($r['i'], $r['u'], $r['p'])) { continue; }
    $items[] = array('i' => $r['i'], 'h' => 'https://hb.afl.rakuten.co.jp/hgc/__AFF__/?pc=' . rawurlencode($r['u']), 'p' => (int)$r['p']);
}
out(200, array('u' => (string)($db['updated'] ?? ''), 'items' => $items));
