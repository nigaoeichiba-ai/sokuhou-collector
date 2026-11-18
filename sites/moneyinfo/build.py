"""Builds this site for the deploy: python sites/moneyinfo/build.py --release --out release

The pages come from generate.py (and case_articles / case_finances / category_pages / faithful_pages); release_build.py turns them into the publishable folder
(canonical, og, JSON-LD, sitemap, robots, the site's own contact form).  Without --release the REVIEW build is made (noindex, robots Disallow)."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import release_build  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--out", default="release")
    a = ap.parse_args()
    release_build.build(Path(a.out).resolve(), None, review=not a.release, own_contact=a.release)
