import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_ROOT / "eval" / "run_eval.py"
SPEC = importlib.util.spec_from_file_location("track_b1_run_eval", RUNNER_PATH)
assert SPEC and SPEC.loader
RUN_EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN_EVAL)


class EvalReportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live_run = json.loads(
            (PROJECT_ROOT / "eval" / "run_results.json").read_text(encoding="utf-8")
        )

    def test_summary_exposes_attempted_passed_and_failed_counts(self):
        summary = RUN_EVAL._build_summary(self.live_run["results"])
        self.assertEqual(summary["total"], 30)
        self.assertEqual(summary["passed_cases"], 28)
        self.assertEqual(summary["failed_cases"], 2)

    def test_every_failed_case_has_a_reason_and_root_cause(self):
        failed = [item for item in self.live_run["results"] if not item["overall_pass"]]
        self.assertEqual(len(failed), 2)
        for item in failed:
            analysis = RUN_EVAL._failure_analysis(item)
            self.assertTrue(analysis["failed_checks"])
            self.assertTrue(analysis["reasons"])
            self.assertTrue(analysis["root_cause"])
            self.assertTrue(analysis["next_action"])

    def test_markdown_explicitly_reports_real_counts(self):
        run = dict(self.live_run)
        run["summary"] = RUN_EVAL._build_summary(run["results"])
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "run_results.md"
            RUN_EVAL._write_markdown(run, report_path)
            report = report_path.read_text(encoding="utf-8")

        self.assertIn("Số lượt thử | Số lần đúng | Số lần sai", report)
        self.assertIn("| **30** | **28** | **2** |", report)
        self.assertIn("## Phân tích lý do 2 lần sai", report)
        self.assertIn("### TC_23", report)
        self.assertIn("### TC_26", report)


if __name__ == "__main__":
    unittest.main()
