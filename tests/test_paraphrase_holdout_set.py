import json
from collections import Counter
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "eval"


class ParaphraseHoldoutSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = json.loads((EVAL_DIR / "golden_set.json").read_text(encoding="utf-8"))
        cls.paraphrases = json.loads((EVAL_DIR / "paraphrase_set.json").read_text(encoding="utf-8"))
        cls.holdout = json.loads((EVAL_DIR / "paraphrase_holdout_set.json").read_text(encoding="utf-8"))
        cls.golden_by_id = {case["case_id"]: case for case in cls.golden}

    def test_has_twenty_unique_cases_balanced_across_wording_types(self):
        self.assertEqual(len(self.holdout), 20)
        self.assertEqual(len({case["case_id"] for case in self.holdout}), 20)
        self.assertEqual(
            Counter(case["paraphrase_type"] for case in self.holdout),
            {"slang": 4, "verbose": 4, "implied": 4, "typo": 4, "boundary": 4},
        )

    def test_is_wording_independent_and_preserves_reference_contract(self):
        prior_queries = {
            case["user_query"].casefold().strip()
            for case in self.golden + self.paraphrases
        }
        for case in self.holdout:
            with self.subTest(case_id=case["case_id"]):
                reference = self.golden_by_id[case["reference_case"]]
                self.assertNotIn(case["user_query"].casefold().strip(), prior_queries)
                self.assertEqual(case["expected_intent"], reference["expected_intent"])
                self.assertEqual(case["expected_action"], reference["expected_action"])
                self.assertEqual(
                    case.get("expected_ground_truth_id"),
                    reference.get("expected_ground_truth_id"),
                )


if __name__ == "__main__":
    unittest.main()
