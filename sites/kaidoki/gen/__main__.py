import sys

from . import stale, write

if "--stale" in sys.argv:
    rows = stale()
    print("\n".join(rows) if rows else "確認日から、過ぎた日付も未発表のものもありません")
else:
    print(write(), "pages")
