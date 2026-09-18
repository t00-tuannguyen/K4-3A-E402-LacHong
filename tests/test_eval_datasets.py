import importlib.util
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "eval"
RUNNER_PATH = EVAL_DIR / "run_eval.py"
SPEC = importlib.util.spec_from_file_location("track_b1_dataset_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUN_EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN_EVAL)

ALL_CATEGORIES = {
    "layer_1_no_ground_truth",
    "layer_2_ambiguity",
    "layer_3_out_of_scope",
    "layer_4_domain_conflict",
    "happy_path",
    "adversarial_edge_case",
}


class EvalDatasetSplitTests(unittest.TestCase):
    def setUp(self):
        self.dev = json.loads((EVAL_DIR / "dev_set.json").read_text(encoding="utf-8"))
        self.sealed = json.loads((EVAL_DIR / "eval_set.json").read_text(encoding="utf-8"))
        self.golden_backup = json.loads((EVAL_DIR / "golden_set.json").read_text(encoding="utf-8"))

    def test_sets_are_disjoint_complete_and_balanced(self):
        self.assertEqual(len(self.dev), 15)
        self.assertEqual(len(self.sealed), 15)
        dev_ids = {case["case_id"] for case in self.dev}
        sealed_ids = {case["case_id"] for case in self.sealed}
        self.assertEqual(len(dev_ids), 15)
        self.assertEqual(len(sealed_ids), 15)
        self.assertFalse(dev_ids & sealed_ids)
        self.assertEqual(len(dev_ids | sealed_ids), 30)
        self.assertEqual(sum(case["source_type"] == "real_chatlog" for case in self.dev), 8)
        self.assertEqual(sum(case["source_type"] == "real_chatlog" for case in self.sealed), 8)

    def test_frozen_golden_backup_matches_the_two_split_sets(self):
        golden_by_id = {case["case_id"]: case for case in self.golden_backup}
        split_by_id = {case["case_id"]: case for case in self.dev + self.sealed}
        self.assertEqual(len(self.golden_backup), 30)
        self.assertEqual(golden_by_id, split_by_id)

    def test_each_set_covers_all_six_categories(self):
        self.assertEqual({case["category"] for case in self.dev}, ALL_CATEGORIES)
        self.assertEqual({case["category"] for case in self.sealed}, ALL_CATEGORIES)

    def test_repeated_intents_are_split_between_sets(self):
        dev_intents = {case["expected_intent"] for case in self.dev}
        sealed_intents = {case["expected_intent"] for case in self.sealed}
        self.assertEqual(dev_intents & sealed_intents, {
            "query_deadline_lab2",
            "query_deadline_team_formation",
        })
        self.assertEqual(sum(case["expected_intent"] == "query_deadline_lab2" for case in self.dev), 1)
        self.assertEqual(sum(case["expected_intent"] == "query_deadline_lab2" for case in self.sealed), 1)
        self.assertEqual(sum(case["expected_intent"] == "query_deadline_team_formation" for case in self.dev), 1)
        self.assertEqual(sum(case["expected_intent"] == "query_deadline_team_formation" for case in self.sealed), 1)

    def test_runner_defaults_to_sealed_dataset_and_supports_all_modes(self):
        self.assertEqual(len(RUN_EVAL._load_dataset("dev")), 15)
        self.assertEqual(len(RUN_EVAL._load_dataset("eval")), 15)
        self.assertEqual(len(RUN_EVAL._load_dataset("all")), 30)
        self.assertEqual(len(RUN_EVAL._load_dataset("paraphrase")), 30)
        self.assertEqual(len(RUN_EVAL._load_dataset("paraphrase_holdout")), 20)
        self.assertEqual(RUN_EVAL.run.__kwdefaults__["dataset"], "eval")


if __name__ == "__main__":
    unittest.main()
