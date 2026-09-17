import type { AgentResponse, OfficialSource } from "../types";

export const mockOfficialSources: OfficialSource[] = [
  {
    ground_truth_id: "ANN_01", title: "Thông báo hoàn thiện Onboarding & Ghép đội tự do", channel: "#thong-bao-chung", message_id: "M49744", author: "BTC",
    content: "Thời hạn hoàn thành onboarding và ghép đội tự do trên nền tảng Phoenix đến 21:00 ngày 13/09/2026. Sau thời gian trên hệ thống sẽ tự động ghép đội ngẫu nhiên.", published_at: "2026-09-12 18:02", url: null, verified: true,
  },
  {
    ground_truth_id: "ANN_02", title: "Quy định cú pháp đổi tên hiển thị Discord", channel: "#thong-bao-chung", message_id: "M47011", author: "BTC",
    content: "Mọi người vui lòng đổi tên theo cú pháp: Mã Nhóm - Họ và tên - 5 số cuối mã sinh viên. Việc thống nhất cách đặt tên sẽ giúp BTC và Lab Coach điểm danh thuận tiện.", published_at: "2026-09-12 09:39", url: null, verified: true,
  },
  {
    ground_truth_id: "ANN_03", title: "Thông báo hạn nộp bài tập Lab 01 Codelab", channel: "#thong-bao-lớp-học", message_id: "M57630", author: "BTC",
    content: "Hạn nộp bài tập Lab 01 (Codelab) là 23:59 cùng ngày học trên cổng VLearn. Bài nộp sẽ được chấm sau khi đóng cổng.", published_at: "2026-09-12 12:51", url: null, verified: true,
  },
  {
    ground_truth_id: "ANN_04", title: "Thông báo chuẩn bị và hạn nộp Lab 02 CVAT", channel: "#thong-bao-lớp-học", message_id: "M16114", author: "BTC",
    content: "Bài tập Lab 02 sử dụng công cụ CVAT. Hạn nộp bài tập Lab 02 là 23:59 ngày 16/09/2026 trên hệ thống VLearn.", published_at: "2026-09-13 11:21", url: null, verified: true,
  },
  {
    ground_truth_id: "ANN_05", title: "Quy chế nộp Daily Standup hàng ngày", channel: "#thong-bao-chung", message_id: "M73469", author: "BTC",
    content: "Khung giờ nộp Daily Standup hằng ngày là từ 00:00 đến 10:00 sáng. Nộp muộn vẫn được ghi nhận nhưng không được cộng điểm thưởng XP.", published_at: "2026-09-14 19:35", url: null, verified: true,
  },
  {
    ground_truth_id: "ANN_06", title: "Quy trình tạo Ticket hỗ trợ kỹ thuật và thủ tục", channel: "#ticket-support", message_id: "M49744", author: "BTC",
    content: "Mọi vấn đề phát sinh kỹ thuật, lỗi tài khoản Phoenix hoặc trường hợp đặc biệt, học viên vui lòng gõ /ticket create tại #ticket-support.", published_at: "2026-09-12 18:02", url: null, verified: true,
  },
  {
    ground_truth_id: "ANN_07", title: "Hướng dẫn tra cứu điểm XP và thứ hạng", channel: "#feed", message_id: "M77092", author: "BTC",
    content: "Học viên có thể tra cứu điểm XP tích lũy và Rank của mình bằng lệnh /rank hoặc xem bảng vàng với lệnh /leaderboard users.", published_at: "2026-09-14 22:39", url: null, verified: true,
  },
];

const common = {
  confidence_score: 0.95,
  source_citation: null,
  interactive_elements: { type: "none", options: [] },
  handoff_metadata: { need_ta: false, reason: null },
  processing_metadata: { intent_provider: "mock" },
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
        ground_truth_id: "ANN_04",
        channel: "#thong-bao-lớp-học",
        message_id: "M16114",
        quote: mockOfficialSources[3].content,
        source_type: "official_ground_truth_fixture",
        verified: true,
        published_at: "2026-09-13 11:21",
      },
    };
  }

  if (text.includes("email") && text.includes("discord")) {
    return {
      ...common,
      intent: "query_deadline_conflict",
      status: "ta_handoff",
      confidence_score: 0.99,
      reply_text: "Hệ thống phát hiện hai mốc deadline khác nhau giữa Email và Discord. Mình không tự chọn một mốc để tránh gây thiệt hại cho bạn.",
      handoff_metadata: { need_ta: true, reason: "conflicting_sources" },
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
      interactive_elements: {
        type: "button_ticket",
        options: [{ label: "Mở hướng dẫn /ticket create", action: "show_ticket_help" }],
      },
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
