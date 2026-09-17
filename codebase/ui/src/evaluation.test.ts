import { describe, expect, it } from "vitest";
import { evaluateResponse } from "./evaluation";
import { mockResponseFor } from "./data/mockScenarios";
import type { EvaluationCase } from "./types";

const conflictCase: EvaluationCase = {
  case_id: "TC_09",
  category: "layer_4_domain_conflict",
  layer: "④ Mâu thuẫn nguồn",
  user_query: "Email báo 23:59 nhưng Discord báo 18:00",
  expected_intent: "query_deadline_conflict",
  expected_action: "domain_conflict",
  expected_ground_truth_id: null,
};

describe("Golden Set quick checks", () => {
  it("maps a conflicting-source handoff to the Golden Set domain_conflict action", () => {
    const response = mockResponseFor(conflictCase.user_query);
    const result = evaluateResponse(conflictCase, response);

    expect(result.checks.action).toBe(true);
    expect(result.passed).toBe(true);
  });

  it("fails a result when its expected source does not match", () => {
    const response = mockResponseFor(conflictCase.user_query);
    const result = evaluateResponse({ ...conflictCase, expected_ground_truth_id: "ANN_01" }, response);

    expect(result.checks.source).toBe(false);
    expect(result.passed).toBe(false);
  });
});
