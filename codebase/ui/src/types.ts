export type AgentStatus =
  | "answered"
  | "clarification_needed"
  | "ta_handoff"
  | "rejected";

export type InteractiveType = "none" | "chips" | "button_handoff" | "button_ticket";

export type AgentRequest = {
  user_id: string;
  channel_id: string;
  message_text: string;
  timestamp: string;
};

export type InteractiveOption = {
  label: string;
  value?: string;
  action?: string;
};

export type AgentResponse = {
  intent: string;
  status: AgentStatus;
  confidence_score: number;
  reply_text: string;
  source_citation: {
    ground_truth_id: string;
    channel: string;
    message_id: string;
    quote: string;
    url?: string | null;
    source_type: string;
    verified: boolean;
    published_at: string | null;
  } | null;
  interactive_elements: {
    type: InteractiveType;
    options: InteractiveOption[];
  };
  handoff_metadata: {
    need_ta: boolean;
    reason: string | null;
  };
  processing_metadata: {
    intent_provider: string;
  };
};

export type OfficialSource = {
  ground_truth_id: string;
  title: string;
  channel: string;
  message_id: string;
  author: string;
  content: string;
  published_at: string;
  url: string | null;
  verified: boolean;
};

export type HandoffPacket = {
  handoff_id: string;
  created_at: string;
  user_id: string;
  channel_id: string;
  original_message: string;
  intent: string;
  status: AgentStatus;
  confidence_score: number;
  reason: string | null;
  source_citation: AgentResponse["source_citation"];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: AgentResponse;
  createdAt: Date;
};

export type DemoScenario = {
  label: string;
  question: string;
  tone: "green" | "yellow" | "red" | "purple" | "orange";
};
