import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

async function ask(user: ReturnType<typeof userEvent.setup>, text: string) {
  await user.type(screen.getByLabelText("Tin nhắn"), text);
  await user.click(screen.getByLabelText("Gửi"));
}

beforeEach(() => {
  vi.stubEnv("VITE_API_MODE", "mock");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("Discord assistant UI", () => {
  it("sends a message and renders a grounded citation", async () => {
    const user = userEvent.setup();
    render(<App />);
    await ask(user, "Hạn nộp Lab 2 CVAT là khi nào?");
    expect(screen.getByRole("status")).toHaveTextContent("đang kiểm tra nguồn");
    expect(await screen.findByRole("button", { name: "Nguồn chính thức · ANN_04" })).toBeInTheDocument();
  });

  it("keeps the assistant mention in chat but removes it from the agent request", async () => {
    const user = userEvent.setup();
    render(<App />);
    await ask(user, "Hạn nộp Lab 2 CVAT là khi nào?");
    await screen.findByRole("button", { name: "Nguồn chính thức · ANN_04" });
    await user.click(screen.getByLabelText("Ẩn hiện agent inspector"));

    expect(screen.getByText((_, element) => element?.tagName === "P" && element.textContent === "@Trợ lý Hạn nộp Lab 2 CVAT là khi nào?")).toBeInTheDocument();
    expect(screen.getByText(/"message_text": "Hạn nộp Lab 2 CVAT là khi nào\?"/)).toBeInTheDocument();
    expect(screen.queryByText(/"message_text": "@Trợ lý/)).not.toBeInTheDocument();
  });

  it("navigates to the mock source channel when a citation is clicked", async () => {
    const user = userEvent.setup();
    render(<App />);
    await ask(user, "Hạn nộp Lab 2 CVAT là khi nào?");
    await user.click(await screen.findByRole("button", { name: "Nguồn chính thức · ANN_04" }));
    expect(screen.getAllByText("nguon-chinh-thuc").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Thông báo chuẩn bị và hạn nộp Lab 02 CVAT · M16114")).toBeInTheDocument();
    expect(screen.getByText(/23:59 ngày 16\/09\/2026/)).toBeInTheDocument();
  });

  it("renders clarification chips", async () => {
    const user = userEvent.setup();
    render(<App />);
    await ask(user, "Hạn nộp bài là mấy giờ?");
    expect(await screen.findByRole("button", { name: "Lab 02 CVAT" })).toBeInTheDocument();
  });

  it("shows handoff confirmation", async () => {
    const user = userEvent.setup();
    render(<App />);
    await ask(user, "Hạn nộp Lab 4 là ngày nào?");
    await user.click(await screen.findByRole("button", { name: "Chuyển cho TA hỗ trợ" }));
    expect(screen.getByText((_, element) => element?.tagName === "P" && element.textContent === "Mình đã tag @TA_OnDuty vào thread hỗ trợ để kiểm tra trường hợp này.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nhảy đến tin nhắn gốc: @Trợ lý Hạn nộp Lab 4 là ngày nào/ })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows ticket guidance for an out-of-scope request", async () => {
    const user = userEvent.setup();
    render(<App />);
    await ask(user, "Check xem t đã nộp bài codelab chưa");
    await user.click(await screen.findByRole("button", { name: "Mở hướng dẫn /ticket create" }));
    expect(screen.getByRole("status")).toHaveTextContent("#ticket-support");
  });

  it("keeps evaluation directly above the composer and shows an editable assistant mention", () => {
    render(<App />);
    const evaluation = screen.getByRole("button", { name: /Evaluation/ });
    const input = screen.getByLabelText("Tin nhắn");
    expect(screen.getByRole("button", { name: "Xóa mention @Trợ lý" })).toBeInTheDocument();
    expect(evaluation.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("scrolls the chat history to the newest message", async () => {
    const user = userEvent.setup();
    render(<App />);
    const history = screen.getByLabelText("Lịch sử trò chuyện");
    Object.defineProperty(history, "scrollHeight", { configurable: true, value: 600 });

    await ask(user, "Hạn nộp Lab 2 CVAT là khi nào?");

    expect(history.scrollTop).toBe(600);
  });

  it("toggles the agent inspector and light theme", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByLabelText("Ẩn hiện agent inspector"));
    expect(screen.getByRole("complementary", { name: "Agent inspector" })).toBeInTheDocument();
    await user.click(screen.getByLabelText("Đổi theme"));
    expect(document.querySelector("[data-theme='light']")).toBeInTheDocument();
  });
});
