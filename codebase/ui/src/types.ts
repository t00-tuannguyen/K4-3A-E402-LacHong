export type AgentStatus =
  | "answered"
  | "clarification_needed"
  | "ta_handoff"
  | "rejected"
  | "source_conflict";

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
    title: string;
    channel: string;
    message_id: string;
    url?: string;
  } | null;
  interactive_elements: {
    type: "chips" | "button_handoff";
    options: InteractiveOption[];
  } | null;
  handoff_metadata: {
    need_ta: boolean;
    reason: string | null;
  };
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
