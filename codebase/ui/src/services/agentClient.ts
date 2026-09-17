import { mockOfficialSources, mockResponseFor } from "../data/mockScenarios";
import type { AgentRequest, AgentResponse, AgentStatus, InteractiveType, OfficialSource } from "../types";

const statuses: AgentStatus[] = ["answered", "clarification_needed", "ta_handoff", "rejected"];
const interactiveTypes: InteractiveType[] = ["none", "chips", "button_handoff", "button_ticket"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

function isCitation(value: unknown): boolean {
  if (value === null) return true;
  if (!isRecord(value)) return false;
  return typeof value.ground_truth_id === "string" &&
    typeof value.channel === "string" &&
    typeof value.message_id === "string" &&
    typeof value.quote === "string" &&
    typeof value.source_type === "string" &&
    typeof value.verified === "boolean" &&
    (value.published_at === null || typeof value.published_at === "string") &&
    (value.url === undefined || value.url === null || typeof value.url === "string");
}

function isInteractiveElements(value: unknown): boolean {
  if (!isRecord(value) || !interactiveTypes.includes(value.type as InteractiveType) || !Array.isArray(value.options)) return false;
  return value.options.every((option) => isRecord(option) && typeof option.label === "string" &&
    (option.value === undefined || typeof option.value === "string") &&
    (option.action === undefined || typeof option.action === "string"));
}

function isAgentResponse(value: unknown): value is AgentResponse {
  if (!isRecord(value)) return false;
  const response = value;
  return (
    typeof response.intent === "string" &&
    typeof response.reply_text === "string" &&
    typeof response.confidence_score === "number" &&
    statuses.includes(response.status as AgentStatus) &&
    isCitation(response.source_citation) &&
    isInteractiveElements(response.interactive_elements) &&
    isRecord(response.handoff_metadata) &&
    typeof response.handoff_metadata.need_ta === "boolean" &&
    (response.handoff_metadata.reason === null || typeof response.handoff_metadata.reason === "string") &&
    isRecord(response.processing_metadata) &&
    typeof response.processing_metadata.intent_provider === "string"
  );
}

function isOfficialSource(value: unknown): value is OfficialSource {
  if (!isRecord(value)) return false;
  return ["ground_truth_id", "title", "channel", "message_id", "author", "content", "published_at"].every((key) => typeof value[key] === "string") &&
    typeof value.verified === "boolean" &&
    (value.url === null || typeof value.url === "string");
}

function apiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
}

export async function sendAgentMessage(request: AgentRequest): Promise<AgentResponse> {
  const mode = import.meta.env.VITE_API_MODE ?? "mock";
  if (mode === "mock") {
    await new Promise((resolve) => window.setTimeout(resolve, 450));
    return mockResponseFor(request.message_text);
  }

  const response = await fetch(`${apiBaseUrl()}/api/assist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) throw new Error(`Backend trả HTTP ${response.status}`);
  const payload: unknown = await response.json();
  if (!isAgentResponse(payload)) throw new Error("Response không đúng AgentResponse contract");
  return payload;
}

export async function getOfficialSources(): Promise<OfficialSource[]> {
  const mode = import.meta.env.VITE_API_MODE ?? "mock";
  if (mode === "mock") return mockOfficialSources;

  const response = await fetch(`${apiBaseUrl()}/api/sources`);
  if (!response.ok) throw new Error(`Không thể tải nguồn chính thức (HTTP ${response.status})`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object") {
    throw new Error("Danh sách nguồn không đúng contract");
  }
  const archive = (payload as Record<string, unknown>).sources;
  if (!Array.isArray(archive) || !archive.every(isOfficialSource)) {
    throw new Error("Danh sách nguồn không đúng contract");
  }
  return archive;
}
