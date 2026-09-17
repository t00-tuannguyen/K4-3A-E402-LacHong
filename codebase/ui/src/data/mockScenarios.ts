import type { AgentResponse, DemoScenario } from "../types";

export const scenarios: DemoScenario[] = [
  { label: "Có nguồn", question: "Hạn nộp Lab 2 CVAT là khi nào?", tone: "green" },
  { label: "Mơ hồ", question: "Hạn nộp bài là mấy giờ?", tone: "yellow" },
  { label: "Chưa công bố", question: "Hạn nộp Lab 4 là ngày nào?", tone: "red" },
  { label: "Ngoài quyền", question: "Check xem t đã nộp bài codelab chưa", tone: "purple" },
  { label: "Mâu thuẫn", question: "Email báo 23:59 nhưng Discord báo 18:00, nộp theo giờ nào?", tone: "orange" },
];

const common = {
  confidence_score: 0.95,
  source_citation: null,
  interactive_elements: null,
  handoff_metadata: { need_ta: false, reason: null },
} satisfies Partial<AgentResponse>;

export function mockResponseFor(message: string): AgentResponse {
  const text = message.toLowerCase();

  if ((text.includes("lab 2") || text.includes("cvat")) && text.includes("hạn")) {
    return {
      ...common,
      intent: "query_deadline",
      status: "answered",
      reply_text: "Hạn nộp Lab 02 (CVAT) là 23:59 ngày 16/09/2026 trên hệ thống VLearn.",
      source_citation: {
        title: "Thông báo chính thức — Lab 02 CVAT",
        channel: "#thong-bao-chung",
        message_id: "M49744",
      },
    };
  }

  if (text.includes("email") && text.includes("discord")) {
    return {
      ...common,
      intent: "query_deadline_conflict",
      status: "source_conflict",
      confidence_score: 0.99,
      reply_text: "Hệ thống phát hiện hai mốc deadline khác nhau giữa Email và Discord. Mình không tự chọn một mốc để tránh gây thiệt hại cho bạn.",
      handoff_metadata: { need_ta: true, reason: "conflicting_official_sources" },
      interactive_elements: {
        type: "button_handoff",
        options: [{ label: "Gắn cờ ưu tiên cho TA", action: "trigger_ta_handoff" }],
      },
    };
  }

  if (text.includes("lab 4")) {
    return {
      ...common,
      intent: "query_deadline_unannounced",
      status: "ta_handoff",
      confidence_score: 0.1,
      reply_text: "BTC chưa công bố thời hạn chính thức cho Lab 4. Để tránh thông tin sai lệch, mình không đưa ra suy đoán.",
      interactive_elements: {
        type: "button_handoff",
        options: [{ label: "Chuyển cho TA hỗ trợ", action: "trigger_ta_handoff" }],
      },
      handoff_metadata: { need_ta: true, reason: "no_official_ground_truth" },
    };
  }

  if (text.includes("đã nộp") || text.includes("gia hạn") || text.includes("điểm danh")) {
    return {
      ...common,
      intent: "personal_record_or_privileged_action",
      status: "rejected",
      confidence_score: 0.98,
      reply_text: "Trợ lý không có quyền truy cập dữ liệu cá nhân hoặc cấp quyền gia hạn. Hãy kiểm tra trên VLearn hoặc dùng /ticket create tại #ticket-support.",
    };
  }

  return {
    ...common,
    intent: "query_deadline_ambiguous",
    status: "clarification_needed",
    confidence_score: 0.55,
    reply_text: "Bạn đang cần tra cứu hạn nộp của nội dung nào?",
    interactive_elements: {
      type: "chips",
      options: [
        { label: "Lab 01 Codelab", value: "Hạn nộp Lab 01 Codelab" },
        { label: "Lab 02 CVAT", value: "Hạn nộp Lab 02 CVAT" },
        { label: "Ghép đội tự do", value: "Hạn ghép đội tự do" },
      ],
    },
  };
}
