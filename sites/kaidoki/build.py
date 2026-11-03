"""Builds this site (the scaffold of sokuhou/newsite.py) for today's date.  python sites/kaidoki/build.py --release --out release"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sokuhou import newsite  # noqa: E402

if __name__ == "__main__":
    if not os.environ.get("KAIDOKI_NO_GEN"):
        from sites.kaidoki import gen  # noqa: E402
        gen.write()
    newsite.main_build(Path(__file__).resolve().parent)
