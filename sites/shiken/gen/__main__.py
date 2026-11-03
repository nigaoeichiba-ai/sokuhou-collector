import sys

from . import stale, write

if "--stale" in sys.argv:
    s = stale()
    print(chr(10).join(s) if s else "no date has passed since the facts were checked")
else:
    print(write(), "pages")
