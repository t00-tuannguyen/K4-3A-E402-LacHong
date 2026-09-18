import json
from collections import Counter
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "eval"


class ParaphraseSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = json.loads((EVAL_DIR / "golden_set.json").read_text(encoding="utf-8"))
        cls.paraphrases = json.loads((EVAL_DIR / "paraphrase_set.json").read_text(encoding="utf-8"))
        cls.golden_by_id = {case["case_id"]: case for case in cls.golden}

    def test_has_thirty_unique_cases_and_six_per_paraphrase_type(self):
        self.assertEqual(len(self.paraphrases), 30)
        self.assertEqual(len({case["case_id"] for case in self.paraphrases}), 30)
        self.assertEqual(
            Counter(case["paraphrase_type"] for case in self.paraphrases),
            {"slang": 6, "verbose": 6, "implied": 6, "typo": 6, "boundary": 6},
        )

    def test_every_case_preserves_its_reference_contract_without_copying_wording(self):
        golden_queries = {case["user_query"].casefold().strip() for case in self.golden}
        for case in self.paraphrases:
            with self.subTest(case_id=case["case_id"]):
                reference = self.golden_by_id[case["reference_case"]]
                self.assertNotIn(case["user_query"].casefold().strip(), golden_queries)
                self.assertEqual(case["expected_intent"], reference["expected_intent"])
                self.assertEqual(case["expected_action"], reference["expected_action"])
                self.assertEqual(
                    case.get("expected_ground_truth_id"),
                    reference.get("expected_ground_truth_id"),
                )


if __name__ == "__main__":
    unittest.main()
