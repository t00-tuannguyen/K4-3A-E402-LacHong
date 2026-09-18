import { afterEach, describe, expect, it, vi } from "vitest";
import { officialSources, responseFor } from "../test/agentFixtures";
import { getEvaluationCases, getOfficialSources, sendAgentMessage } from "./agentClient";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("Core AI HTTP client", () => {
  it("posts an agent request to the Core AI endpoint", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
    const expected = responseFor("Hạn nộp Lab 2 CVAT là khi nào?");
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => expected });
    vi.stubGlobal("fetch", fetchMock);
    const request = {
      user_id: "D202602628",
      channel_id: "channel_10",
      message_text: "Hạn nộp Lab 2 CVAT là khi nào?",
      timestamp: "2026-09-17T03:00:00Z",
    };

    await expect(sendAgentMessage(request)).resolves.toEqual(expected);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/assist",
      expect.objectContaining({ method: "POST", body: JSON.stringify(request) }),
    );
  });

  it("loads the official-source archive from the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ sources: officialSources }) });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getOfficialSources()).resolves.toEqual(officialSources);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/sources");
  });

  it("loads the Golden Set from the backend", async () => {
    const evaluationCase = {
      case_id: "TC_01",
      category: "layer_1_no_ground_truth",
      layer: "Nguồn sự thật",
      user_query: "Lab 4 khi nào?",
      expected_intent: "query_deadline_unannounced",
      expected_action: "ta_handoff",
      expected_ground_truth_id: null,
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ cases: [evaluationCase] }) });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getEvaluationCases()).resolves.toEqual([evaluationCase]);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/evaluation/cases");
  });

  it("rejects an invalid assistant response contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "answered" }) }));

    await expect(sendAgentMessage({
      user_id: "test",
      channel_id: "test",
      message_text: "test",
      timestamp: "2026-09-17T03:00:00Z",
    })).rejects.toThrow("Response không đúng AgentResponse contract");
  });

  it("rejects an invalid source archive contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sources: [{ title: "Thiếu định danh" }] }),
    }));

    await expect(getOfficialSources()).rejects.toThrow("Danh sách nguồn không đúng contract");
  });

  it("reports backend HTTP errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 }));

    await expect(getOfficialSources()).rejects.toThrow("HTTP 503");
  });
});
