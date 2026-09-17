import { describe, expect, it } from "vitest";
import { mockResponseFor } from "../data/mockScenarios";

describe("mock agent scenarios", () => {
  it.each([
    ["Hạn nộp Lab 2 CVAT là khi nào?", "answered"],
    ["Hạn nộp bài là mấy giờ?", "clarification_needed"],
    ["Hạn nộp Lab 4 là ngày nào?", "ta_handoff"],
    ["Check xem t đã nộp bài codelab chưa", "rejected"],
    ["Email báo 23:59 nhưng Discord báo 18:00", "source_conflict"],
  ])("maps %s to %s", (question, status) => {
    expect(mockResponseFor(question).status).toBe(status);
  });

  it("only returns a citation for a grounded answer", () => {
    expect(mockResponseFor("Hạn nộp Lab 2 CVAT là khi nào?").source_citation).not.toBeNull();
    expect(mockResponseFor("Hạn nộp bài là mấy giờ?").source_citation).toBeNull();
  });

  it("marks conflict for TA handoff", () => {
    const result = mockResponseFor("Email báo 23:59 nhưng Discord báo 18:00");
    expect(result.handoff_metadata.need_ta).toBe(true);
    expect(result.interactive_elements?.type).toBe("button_handoff");
  });
});
