import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EvaluationPanel } from "./EvaluationPanel";

const categories = [
  "happy_path", "layer_1_no_ground_truth", "layer_2_ambiguity",
  "layer_3_out_of_scope", "layer_4_domain_conflict", "adversarial_edge_case",
];

beforeEach(() => {
  vi.stubEnv("VITE_API_MODE", "api");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ cases: categories.map((category, index) => ({
      case_id: `TC_0${index + 1}`, category, layer: "Test", user_query: `Câu hỏi ${index + 1}`,
      expected_intent: "unknown", expected_action: "ta_handoff", expected_ground_truth_id: null,
    })) }),
  }));
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("EvaluationPanel", () => {
  it("keeps the panel collapsed and renders readable Golden Set categories when opened", async () => {
    const user = userEvent.setup();
    const onSelectCase = vi.fn();
    render(<EvaluationPanel onSelectCase={onSelectCase} />);

    const toggle = screen.getByRole("button", { name: /Evaluation/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);

    expect(await screen.findByRole("button", { name: /Có nguồn \/ trả lời được/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Chưa có thông báo chính thức/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cần làm rõ câu hỏi/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ngoài quyền hỗ trợ/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Mâu thuẫn nguồn/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Bẫy an toàn \/ prompt injection/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Đưa vào chat" }));
    expect(onSelectCase).toHaveBeenCalledWith("Câu hỏi 1");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
