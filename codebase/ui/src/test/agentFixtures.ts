import type { AgentResponse, OfficialSource } from "../types";

export const officialSources: OfficialSource[] = [{
  ground_truth_id: "ANN_04",
  title: "Thông báo chuẩn bị và hạn nộp Lab 02 CVAT",
  channel: "#thong-bao-lop-hoc",
  message_id: "M16114",
  author: "BTC",
  content: "Bài tập Lab 02 sử dụng công cụ CVAT. Hạn nộp bài tập Lab 02 là 23:59 ngày 16/09/2026 trên hệ thống VLearn.",
  published_at: "2026-09-13 11:21",
  url: null,
  verified: true,
}];

const base: Pick<AgentResponse, "confidence_score" | "processing_metadata"> = {
  confidence_score: 0.95,
  processing_metadata: { intent_provider: "test_fixture" },
};

export function responseFor(message: string): AgentResponse {
  if (message.includes("Lab 4")) {
    return {
      ...base,
      intent: "query_deadline_unannounced",
      status: "ta_handoff",
      reply_text: "Kho thông báo chính thức chưa có thời hạn cho bài Lab này.",
      source_citation: null,
      interactive_elements: { type: "button_handoff", options: [{ label: "Chuyển cho TA hỗ trợ", action: "trigger_ta_handoff" }] },
      handoff_metadata: { need_ta: true, reason: "no_official_ground_truth" },
    };
  }
  if (message.includes("Hạn nộp bài")) {
    return {
      ...base,
      intent: "query_deadline_ambiguous",
      status: "clarification_needed",
      reply_text: "Bạn đang hỏi hạn nộp của nội dung nào?",
      source_citation: null,
      interactive_elements: { type: "chips", options: [{ label: "Lab 02 CVAT", value: "Hạn nộp Lab 02 CVAT là khi nào?" }] },
      handoff_metadata: { need_ta: false, reason: null },
    };
  }
  if (message.includes("Check xem")) {
    return {
      ...base,
      intent: "check_personal_submission_status",
      status: "rejected",
      reply_text: "Mình không có quyền xem trạng thái bài nộp cá nhân.",
      source_citation: null,
      interactive_elements: { type: "button_ticket", options: [{ label: "Mở hướng dẫn /ticket create", action: "show_ticket_help" }] },
      handoff_metadata: { need_ta: true, reason: "outside_authority" },
    };
  }
  const source = officialSources[0];
  return {
    ...base,
    intent: "query_deadline_lab2",
    status: "answered",
    reply_text: "Hạn nộp Lab 02 CVAT là 23:59 ngày 16/09/2026 trên VLearn.",
    source_citation: {
      ground_truth_id: source.ground_truth_id,
      channel: source.channel,
      message_id: source.message_id,
      quote: source.content,
      url: source.url,
      source_type: "official_ground_truth_fixture",
      verified: true,
      published_at: source.published_at,
    },
    interactive_elements: { type: "none", options: [] },
    handoff_metadata: { need_ta: false, reason: null },
  };
}
