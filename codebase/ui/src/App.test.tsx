import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("Discord assistant UI", () => {
  it("sends a message and renders a grounded citation", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Tin nhắn"), "Hạn nộp Lab 2 CVAT là khi nào?");
    await user.click(screen.getByLabelText("Gửi"));
    expect(screen.getByRole("status")).toHaveTextContent("đang kiểm tra nguồn");
    expect(await screen.findByText("Thông báo chính thức — Lab 02 CVAT")).toBeInTheDocument();
  });

  it("navigates to the mock source channel when a citation is clicked", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Có nguồn" }));
    await user.click(await screen.findByRole("button", { name: "Thông báo chính thức — Lab 02 CVAT" }));
    expect(screen.getAllByText("nguon-chinh-thuc").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Thông báo chính thức — Lab 02 CVAT · M49744")).toBeInTheDocument();
    expect(screen.getByText(/23:59 ngày 16\/09\/2026/)).toBeInTheDocument();
  });

  it("renders clarification chips", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Mơ hồ" }));
    expect(await screen.findByRole("button", { name: "Lab 02 CVAT" })).toBeInTheDocument();
  });

  it("shows handoff confirmation", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Chưa công bố" }));
    await user.click(await screen.findByRole("button", { name: "Chuyển cho TA hỗ trợ" }));
    expect(screen.getByRole("status")).toHaveTextContent("@TA_OnDuty");
  });

  it("keeps scenarios directly above the composer and shows an editable assistant mention", () => {
    render(<App />);
    const scenario = screen.getByRole("button", { name: "Có nguồn" });
    const input = screen.getByLabelText("Tin nhắn");
    expect(screen.getByRole("button", { name: "Xóa mention @Trợ lý" })).toBeInTheDocument();
    expect(scenario.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
