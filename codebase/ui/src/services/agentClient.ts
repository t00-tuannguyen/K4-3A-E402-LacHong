import { mockResponseFor } from "../data/mockScenarios";
import type { AgentRequest, AgentResponse, AgentStatus } from "../types";

const statuses: AgentStatus[] = ["answered", "clarification_needed", "ta_handoff", "rejected", "source_conflict"];

function isAgentResponse(value: unknown): value is AgentResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Record<string, unknown>;
  return (
    typeof response.intent === "string" &&
    typeof response.reply_text === "string" &&
    typeof response.confidence_score === "number" &&
    statuses.includes(response.status as AgentStatus) &&
    typeof response.handoff_metadata === "object"
  );
}

export async function sendAgentMessage(request: AgentRequest): Promise<AgentResponse> {
  const mode = import.meta.env.VITE_API_MODE ?? "mock";
  if (mode === "mock") {
    await new Promise((resolve) => window.setTimeout(resolve, 450));
    return mockResponseFor(request.message_text);
  }

  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${baseUrl}/api/v1/agent/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) throw new Error(`Backend trả HTTP ${response.status}`);
  const payload: unknown = await response.json();
  if (!isAgentResponse(payload)) throw new Error("Response không đúng AgentResponse contract");
  return payload;
}
