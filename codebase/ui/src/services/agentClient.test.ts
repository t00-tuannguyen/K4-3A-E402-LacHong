import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mockResponseFor, mockOfficialSources } from "../data/mockScenarios";
import { getEvaluationCases, getOfficialSources, sendAgentMessage } from "./agentClient";

beforeEach(() => {
  vi.stubEnv("VITE_API_MODE", "mock");
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("mock agent scenarios", () => {
  it.each([
    ["Hạn nộp Lab 2 CVAT là khi nào?", "answered"],
    ["Hạn nộp bài là mấy giờ?", "clarification_needed"],
    ["Hạn nộp Lab 4 là ngày nào?", "ta_handoff"],
    ["Check xem t đã nộp bài codelab chưa", "rejected"],
    ["Email báo 23:59 nhưng Discord báo 18:00", "ta_handoff"],
  ])("maps %s to %s", (question, status) => {
    expect(mockResponseFor(question).status).toBe(status);
  });

  it("only returns a citation for a grounded answer", () => {
    const grounded = mockResponseFor("Hạn nộp Lab 2 CVAT là khi nào?");
    expect(grounded.source_citation).not.toBeNull();
    expect(grounded.source_citation?.quote).toBe(mockOfficialSources[3].content);
    expect(mockResponseFor("Hạn nộp bài là mấy giờ?").source_citation).toBeNull();
  });

  it("marks conflict for TA handoff", () => {
    const result = mockResponseFor("Email báo 23:59 nhưng Discord báo 18:00");
    expect(result.handoff_metadata.need_ta).toBe(true);
    expect(result.interactive_elements?.type).toBe("button_handoff");
  });

  it("returns the local official-source archive in mock mode", async () => {
    await expect(getOfficialSources()).resolves.toEqual(mockOfficialSources);
  });

  it("loads the official-source archive from the Core AI endpoint in API mode", async () => {
    vi.stubEnv("VITE_API_MODE", "api");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sources: [mockOfficialSources[0]] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getOfficialSources()).resolves.toEqual([mockOfficialSources[0]]);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/sources");
  });

  it("posts an agent request to the Core AI endpoint in API mode", async () => {
    vi.stubEnv("VITE_API_MODE", "api");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
    const expected = mockResponseFor("Hạn nộp Lab 2 CVAT là khi nào?");
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => expected });
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendAgentMessage({
      user_id: "D202602628",
      channel_id: "channel_10",
      message_text: "Hạn nộp Lab 2 CVAT là khi nào?",
      timestamp: "2026-09-17T03:00:00Z",
    })).resolves.toEqual(expected);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/assist", expect.objectContaining({ method: "POST" }));
  });

  it("loads the Golden Set from the Core AI endpoint in API mode", async () => {
    vi.stubEnv("VITE_API_MODE", "api");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
    const evaluationCase = {
      case_id: "TC_01", category: "layer_1_no_ground_truth", layer: "Nguồn sự thật", user_query: "Lab 4 khi nào?",
      expected_intent: "query_deadline_unannounced", expected_action: "ta_handoff", expected_ground_truth_id: null,
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ cases: [evaluationCase] }) });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getEvaluationCases()).resolves.toEqual([evaluationCase]);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/evaluation/cases");
  });

  it("reports an invalid source archive contract clearly", async () => {
    vi.stubEnv("VITE_API_MODE", "api");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sources: [{ title: "Thiếu định danh" }] }),
    }));

    await expect(getOfficialSources()).rejects.toThrow("Danh sách nguồn không đúng contract");
  });
});
