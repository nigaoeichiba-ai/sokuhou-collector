"""One-off: draws the share picture (assets/og.png, 1200x630) with headless Chrome from the wordmark and the catch phrase.  python sites/atomou/make_og.py
A placeholder in the same way as the wordmark: when the owner's real logo exists, run this again with it."""
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CATCH = "忘れたくない日を、お知らせします。"   # the same words as build.CATCH


def main() -> None:
    svg = (HERE / "assets" / "wordmark.svg").read_text(encoding="utf-8").replace("<svg ", '<svg style="width:900px;height:auto;display:block" ', 1)
    html = f"""<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;width:1200px;height:630px;background:#F7F7F5;font-family:"Yu Gothic UI","Meiryo","Noto Sans JP",sans-serif;color:#1F2937}}
.w{{box-sizing:border-box;width:1200px;height:630px;padding:70px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:44px;border:14px solid #1A56B8}}
.c{{font-size:46px;font-weight:700;letter-spacing:.04em}}
.d{{font-size:30px;color:#5B6470;letter-spacing:.08em}}
</style><div class="w">{svg}<div class="c">{CATCH}</div><div class="d">atomou.com</div></div>"""
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "og.html"
        page.write_text(html, encoding="utf-8")
        out = HERE / "assets" / "og.png"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", f"--user-data-dir={Path(td) / 'p'}", "--window-size=1200,630",
                        f"--screenshot={out}", page.as_uri()], check=True, capture_output=True, timeout=120)
    print("wrote", out)


if __name__ == "__main__":
    main()
