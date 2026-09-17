import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from codebase.core_ai.assistant import RAW_SOURCES
from codebase.core_ai.server import app


class CoreAiServerTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("codebase.core_ai.server.answer")
    def test_assist_delegates_to_core_contract(self, answer):
        expected = {
            "intent": "query_deadline",
            "status": "answered",
            "confidence_score": 0.95,
            "reply_text": "Grounded response",
            "source_citation": None,
            "interactive_elements": {"type": "none", "options": []},
            "handoff_metadata": {"need_ta": False, "reason": None},
            "processing_metadata": {"intent_provider": "local_rules"},
        }
        answer.return_value = expected

        response = self.client.post(
            "/api/assist",
            json={
                "user_id": "D202602628",
                "channel_id": "channel_10",
                "message_text": "Hạn nộp Lab 2 là khi nào?",
                "timestamp": "2026-09-17T03:00:00Z",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        answer.assert_called_once_with({
            "user_id": "D202602628",
            "channel_id": "channel_10",
            "message_text": "Hạn nộp Lab 2 là khi nào?",
            "timestamp": "2026-09-17T03:00:00Z",
        })

    def test_sources_exposes_the_official_source_archive(self):
        response = self.client.get("/api/sources")

        self.assertEqual(response.status_code, 200)
        sources = response.json()["sources"]
        self.assertEqual(len(sources), len(RAW_SOURCES))
        self.assertEqual(sources[3]["ground_truth_id"], "ANN_04")
        self.assertEqual(sources[3]["message_id"], "M16114")
        self.assertTrue(sources[3]["verified"])

    def test_evaluation_cases_exposes_the_complete_golden_set(self):
        response = self.client.get("/api/evaluation/cases")

        self.assertEqual(response.status_code, 200)
        cases = response.json()["cases"]
        self.assertEqual(len(cases), 30)
        self.assertEqual(cases[0]["case_id"], "TC_01")
        self.assertEqual(cases[0]["expected_action"], "ta_handoff")
        self.assertNotIn("evaluation_criteria", cases[0])


if __name__ == "__main__":
    unittest.main()
