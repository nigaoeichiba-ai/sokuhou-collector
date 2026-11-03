"""Builds this site (the scaffold of sokuhou/newsite.py).  python sites/shiken/build.py --release --out release"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sokuhou import newsite  # noqa: E402

if __name__ == "__main__":
    # "N days left" and the lists in date order count from today: the content is made again from the dates (gen/facts.py, data/) on every build
    from sites.shiken import gen  # noqa: E402
    gen.write()
    newsite.main_build(Path(__file__).resolve().parent)
