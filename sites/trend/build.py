"""Builds this site (the scaffold of sokuhou/newsite.py).  python sites/trend/build.py --release --out release
The product shelves (sites/trend/shelves.json) ship api/shelf.php and assets/shelf.js through sokuhou/mallstore.py."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sokuhou import newsite  # noqa: E402

if __name__ == "__main__":
    newsite.main_build(Path(__file__).resolve().parent)
