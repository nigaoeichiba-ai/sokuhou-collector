"""The test runner must recognise a project's tests even when its module cannot be imported, so one project's missing library never blocks another project."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_tests  # noqa: E402


class ModuleOfTest(unittest.TestCase):
    def test_normal_and_failed_import_ids_give_the_module_name(self):
        self.assertEqual(run_tests.module_of("tests.test_minna_build.MinnaBuildTest.test_catalogue"), "test_minna_build")
        self.assertEqual(run_tests.module_of("tests.test_minna_factory"), "test_minna_factory")  # unittest.loader._FailedTest
        self.assertEqual(run_tests.module_of("unittest.loader._FailedTest.tests.test_minna_factory"), "test_minna_factory")
        self.assertEqual(run_tests.module_of("something.else"), "something.else")

    def test_a_project_that_fails_to_import_is_left_out_of_another_projects_run(self):
        import fnmatch
        pats = [p for name, ps in run_tests.OWNED.items() if name != "saichin" for p in ps]
        self.assertTrue(any(fnmatch.fnmatch(run_tests.module_of("tests.test_minna_factory"), p) for p in pats))
        self.assertFalse(any(fnmatch.fnmatch(run_tests.module_of("tests.test_saichin_build.X.test_a"), p) for p in pats))


if __name__ == "__main__":
    unittest.main()
