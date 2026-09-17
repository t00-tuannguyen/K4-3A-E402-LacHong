import type { AgentResponse, EvaluationCase, EvaluationResult } from "./types";

export function effectiveAction(response: AgentResponse): string {
  if (response.status === "rejected") return "out_of_scope";
  if (response.status === "ta_handoff" && response.handoff_metadata.reason === "conflicting_sources") return "domain_conflict";
  return response.status;
}

export function evaluateResponse(testCase: EvaluationCase, response: AgentResponse): EvaluationResult {
  const checks = {
    intent: response.intent === testCase.expected_intent,
    action: effectiveAction(response) === testCase.expected_action,
    source: testCase.expected_ground_truth_id === null || response.source_citation?.ground_truth_id === testCase.expected_ground_truth_id,
  };
  return { testCase, response, checks, passed: Object.values(checks).every(Boolean) };
}
