#!/usr/bin/env python3
"""公開ゲート: 文章のルールの正(ng_rules.json)を、URL から取って保存する。

使い方: python3 fetch_rules.py <URL> <保存先>
URL は Secrets(SHIKEN_RULES_URL)から渡す。ワークフローのファイルには書かない。

取得・JSONの形・version・ハード一覧のどれか1つでも失敗したら、終了コード1で止まる。
控え(リポジトリ内のコピー)には切り替えない。成功したら version を標準出力に書く。
"""
import json
import sys
import urllib.request


def main() -> int:
    if len(sys.argv) != 3 or not sys.argv[1]:
        print("使い方: fetch_rules.py <URL> <保存先> (URL が空です)")
        return 1
    url, out = sys.argv[1], sys.argv[2]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "shiken-text-gate"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
        data = json.loads(body.decode("utf-8"))
        hard = data["hard"]
        version = str(data["version"]).strip()
        if not isinstance(hard, list) or not hard or not version:
            raise ValueError("hard が空、または version がありません")
        for item in hard:
            if not item.get("label") or not item.get("pattern"):
                raise ValueError("hard の項目に label / pattern がありません")
    except Exception as exc:  # 取得・形式のどれでも、止める側に倒す
        print(f"ルールを取得できませんでした: {type(exc).__name__}: {exc}")
        return 1
    with open(out, "wb") as fh:
        fh.write(body)
    print(f"version={version} hard={len(hard)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
