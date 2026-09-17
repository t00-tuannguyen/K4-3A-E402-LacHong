import { useRef, useState } from "react";
import { DiscordChrome } from "./components/DiscordChrome";
import { Composer } from "./components/Composer";
import { MessageBubble } from "./components/MessageBubble";
import { ScenarioBar } from "./components/ScenarioBar";
import { AgentInspector, type AgentTrace } from "./components/AgentInspector";
import { scenarios } from "./data/mockScenarios";
import { sendAgentMessage } from "./services/agentClient";
import type { AgentResponse, ChatMessage } from "./types";

const officialSources = [
  { title: "Thông báo chính thức — Lab 02 CVAT", channel: "#thong-bao-chung", message_id: "M49744", text: "Hạn nộp bài tập Lab 02 (CVAT) là 23:59 ngày 16/09/2026 trên hệ thống VLearn.", date: "13/09/2026" },
  { title: "Thông báo chính thức — Lab 01 Codelab", channel: "#thong-bao-chung", message_id: "M49731", text: "Lab 01 Codelab mở trên VLearn. Hạn nộp được tính theo mốc hiển thị trong thông báo ghim.", date: "12/09/2026" },
  { title: "Thông báo — Ghép đội tự do", channel: "#thong-bao-chung", message_id: "M49688", text: "Học viên có thể ghép đội tự do theo hướng dẫn trong kênh hỗ trợ học tập.", date: "11/09/2026" },
];

const welcome: ChatMessage = {
  id: "welcome",
  role: "assistant",
  text: "Chào bạn! Mình hỗ trợ tra cứu deadline, quy định nộp lab và thủ tục onboarding từ nguồn chính thức.",
  createdAt: new Date(),
};

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([welcome]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [trace, setTrace] = useState<AgentTrace>({ request: null, response: null, phase: "idle" });
  const [activeChannel, setActiveChannel] = useState<"tro-ly-hoi-dap" | "nguon-chinh-thuc">("tro-ly-hoi-dap");
  const [sourceMessage, setSourceMessage] = useState<AgentResponse | null>(null);
  const retryText = useRef<string | null>(null);

  async function send(text: string) {
    const normalizedText = text.trim().replace(/^@Trợ lý\s*/i, "") ? `@Trợ lý ${text.trim().replace(/^@Trợ lý\s*/i, "")}` : "@Trợ lý";
    const userMessage: ChatMessage = { id: makeId(), role: "user", text: normalizedText, createdAt: new Date() };
    const request = { user_id: "D202602628", channel_id: "channel_10", message_text: normalizedText, timestamp: new Date().toISOString() };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);
    setError(null);
    setTrace({ request, response: null, phase: "running" });
    retryText.current = normalizedText;
    try {
      const response = await sendAgentMessage(request);
      setMessages((current) => [...current, { id: makeId(), role: "assistant", text: response.reply_text, response, createdAt: new Date() }]);
      setTrace({ request, response, phase: "done" });
      retryText.current = null;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể kết nối backend");
      setTrace({ request, response: null, phase: "error", error: caught instanceof Error ? caught.message : "Không thể kết nối backend" });
    } finally {
      setLoading(false);
    }
  }

  function handoff() {
    setToast("Đã tạo yêu cầu hỗ trợ và tag @TA_OnDuty trong bản demo.");
    window.setTimeout(() => setToast(null), 3000);
  }

  return (
    <DiscordChrome theme={theme} onToggleTheme={() => setTheme((current) => current === "dark" ? "light" : "dark")} inspectorOpen={inspectorOpen} onToggleInspector={() => setInspectorOpen((current) => !current)} inspector={<AgentInspector trace={trace} />} activeChannel={activeChannel} onChannelSelect={setActiveChannel}>
      <section aria-label="Lịch sử trò chuyện" className="flex-1 overflow-y-auto py-3">
        {activeChannel === "nguon-chinh-thuc" ? <SourceChannelMessages selectedId={sourceMessage?.source_citation?.message_id} /> : messages.map((message) => <MessageBubble key={message.id} message={message} onOption={send} onHandoff={handoff} onSourceOpen={(response) => { setSourceMessage(response); setActiveChannel("nguon-chinh-thuc"); }} />)}
        {loading && <div role="status" className="flex items-center gap-2 px-16 py-3 text-xs text-[var(--discord-text-faint)]"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /> Trợ lý đang kiểm tra nguồn…</div>}
        {error && <div role="alert" className="mx-4 mt-2 flex items-center justify-between rounded border border-red-700 bg-red-950/40 p-3 text-sm text-red-200"><span>{error}</span><button onClick={() => retryText.current && send(retryText.current)} className="rounded bg-red-600 px-3 py-1 text-xs text-white">Thử lại</button></div>}
      </section>
      {activeChannel === "tro-ly-hoi-dap" && <ScenarioBar scenarios={scenarios} onSelect={send} disabled={loading} />}
      <Composer onSend={send} disabled={loading || activeChannel === "nguon-chinh-thuc"} />
      {toast && <div role="status" className="fixed bottom-20 right-5 z-50 rounded bg-[#248046] px-4 py-3 text-sm font-medium text-white shadow-xl">{toast}</div>}
    </DiscordChrome>
  );
}

function SourceChannelMessages({ selectedId }: { selectedId?: string }) {
  return <div className="mx-auto w-full max-w-3xl space-y-3">{officialSources.map((source) => <article key={source.message_id} className={`rounded-lg border p-5 ${selectedId === source.message_id ? "border-[var(--discord-brand)] bg-[var(--discord-bg-elevated)] ring-1 ring-[var(--discord-brand)]/40" : "border-[var(--discord-border)] bg-[var(--discord-bg-elevated)]"}`}><div className="flex gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--discord-brand)] text-xs font-bold text-white">BTC</div><div><div className="flex items-center gap-2"><strong className="text-sm text-[var(--discord-text-strong)]">Ban tổ chức</strong><time className="text-[11px] text-[var(--discord-text-faint)]">{source.date}</time></div><p className="mt-1 text-xs text-[var(--discord-text-faint)]">{source.channel}</p><p className="mt-2 text-sm leading-6 text-[var(--discord-text)]">{source.text}</p><p className="mt-3 text-xs text-[var(--discord-text-faint)]">{source.title} · {source.message_id}</p></div></div></article>)}</div>;
}
