import json
from pathlib import Path
import unittest

from codebase.core_ai.normalization import fold_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "eval"
DATA_DIR = PROJECT_ROOT / "codebase" / "data"
COVERAGE_GAP_CASES = {"TC_23", "TC_26"}


def source_text(source: dict) -> str:
    fields = source.get("field_availability", {})
    responses = [
        str(value.get("response", ""))
        for value in fields.values()
        if isinstance(value, dict)
    ]
    return " ".join([
        str(source.get("title", "")),
        str(source.get("content", "")),
        *map(str, source.get("key_entities", {}).values()),
        *responses,
    ])


class ContentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {
            case["case_id"]: case
            for path in (EVAL_DIR / "dev_set.json", EVAL_DIR / "eval_set.json")
            for case in json.loads(path.read_text(encoding="utf-8"))
        }
        cls.contracts = json.loads((EVAL_DIR / "content_contracts.json").read_text(encoding="utf-8"))["cases"]
        cls.sources = {
            source["id"]: source
            for source in json.loads((DATA_DIR / "official_announcements.json").read_text(encoding="utf-8"))
        }

    def test_every_grounded_answer_without_a_declared_data_gap_has_one_contract(self):
        expected_ids = {
            case_id
            for case_id, case in self.cases.items()
            if case["expected_action"] == "answered"
            and case.get("expected_ground_truth_id")
            and case_id not in COVERAGE_GAP_CASES
        }
        self.assertEqual(set(self.contracts), expected_ids)

    def test_each_required_fact_is_supported_by_its_declared_official_source(self):
        for case_id, contract in self.contracts.items():
            with self.subTest(case_id=case_id):
                case = self.cases[case_id]
                self.assertEqual(contract["source_id"], case["expected_ground_truth_id"])
                official_text = fold_text(source_text(self.sources[contract["source_id"]]))
                for alternatives in contract["source_fact_groups"]:
                    self.assertTrue(
                        any(fold_text(term) in official_text for term in alternatives),
                        msg=f"Unsupported content assertion: {alternatives}",
                    )


if __name__ == "__main__":
    unittest.main()
