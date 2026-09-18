import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "codebase" / "data"
AUDIT_BUCKETS = {
    "source_attested",
    "source_derived",
    "normalization_alias",
    "evaluation_motivated_unverified",
}


class RetrievalTermsAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = json.loads((DATA_DIR / "official_announcements.json").read_text(encoding="utf-8"))
        cls.audit = json.loads((DATA_DIR / "retrieval_terms_audit.json").read_text(encoding="utf-8"))
        cls.audit_by_source = {item["source_id"]: item for item in cls.audit["sources"]}

    def test_every_current_metadata_term_has_exactly_one_audit_classification(self):
        self.assertEqual({source["id"] for source in self.sources}, set(self.audit_by_source))
        for source in self.sources:
            audit_source = self.audit_by_source[source["id"]]
            for field_name in ("retrieval_terms", "subject_terms"):
                with self.subTest(source=source["id"], field=field_name):
                    buckets = audit_source["fields"][field_name]
                    self.assertEqual(set(buckets), AUDIT_BUCKETS)
                    audited_terms = [term for terms in buckets.values() for term in terms]
                    self.assertEqual(len(audited_terms), len(set(audited_terms)))
                    self.assertEqual(set(audited_terms), set(source[field_name]))

    def test_unverified_terms_are_explicitly_marked_for_owner_review(self):
        for item in self.audit["sources"]:
            unverified = [
                term
                for field in item["fields"].values()
                for term in field["evaluation_motivated_unverified"]
            ]
            if unverified:
                with self.subTest(source=item["source_id"]):
                    self.assertEqual(item["review_status"], "needs_owner_confirmation")


if __name__ == "__main__":
    unittest.main()
