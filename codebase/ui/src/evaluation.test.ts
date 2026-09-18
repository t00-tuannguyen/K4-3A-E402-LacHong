import { describe, expect, it } from "vitest";
import { evaluateResponse } from "./evaluation";
import type { AgentResponse, EvaluationCase } from "./types";

const conflictCase: EvaluationCase = {
  case_id: "TC_09",
  category: "layer_4_domain_conflict",
  layer: "④ Mâu thuẫn nguồn",
  user_query: "Email báo 23:59 nhưng Discord báo 18:00",
  expected_intent: "resolve_deadline_conflict",
  expected_action: "domain_conflict",
  expected_ground_truth_id: null,
};

const conflictResponse: AgentResponse = {
  intent: "resolve_deadline_conflict",
  status: "ta_handoff",
  confidence_score: 0.9,
  reply_text: "Hai nguồn chính thức đang không khớp; cần TA xác minh.",
  source_citation: null,
  interactive_elements: { type: "button_handoff", options: [] },
  handoff_metadata: { need_ta: true, reason: "conflicting_sources" },
  processing_metadata: { intent_provider: "test_fixture" },
};

describe("Golden Set quick checks", () => {
  it("maps a conflicting-source handoff to the Golden Set domain_conflict action", () => {
    const result = evaluateResponse(conflictCase, conflictResponse);

    expect(result.checks.action).toBe(true);
    expect(result.passed).toBe(true);
  });

  it("fails a result when its expected source does not match", () => {
    const result = evaluateResponse(
      { ...conflictCase, expected_ground_truth_id: "ANN_01" },
      conflictResponse,
    );

    expect(result.checks.source).toBe(false);
    expect(result.passed).toBe(false);
  });
});
