"""trend: 関連リンクの文は、リンク先の記事の h1 から毎回作る(sites/trend/hooks.py の sync_related_titles)。手書きの写しが古いまま残ると落ちる(負例)。"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _hooks():
    spec = importlib.util.spec_from_file_location("trend_hooks_rel", ROOT / "sites" / "trend" / "hooks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RelatedTitles(unittest.TestCase):
    def test_a_stale_copy_of_a_headline_is_replaced(self):
        hooks = _hooks()
        art = {"path": "/a/", "h1": "セールは終了しました", "category": "暮らし"}
        linking = {"path": "/b/", "related": [{"path": "/a/", "text": "今日18日が一般販売"}, {"path": "/other/", "text": "一覧"}]}
        hooks.sync_related_titles([art, linking], [art])
        self.assertEqual([r["text"] for r in linking["related"]], ["セールは終了しました", "一覧"])

    def test_prepare_calls_it(self):
        src = (ROOT / "sites" / "trend" / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("    sync_related_titles(pages, arts)", src)


if __name__ == "__main__":
    unittest.main()
