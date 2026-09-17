import { useEffect, useRef, useState } from "react";
import { DiscordChrome } from "./components/DiscordChrome";
import { Composer } from "./components/Composer";
import { MessageBubble } from "./components/MessageBubble";
import { AgentInspector, type AgentTrace } from "./components/AgentInspector";
import { EvaluationPanel } from "./components/EvaluationPanel";
import { getOfficialSources, sendAgentMessage } from "./services/agentClient";
import type { AgentResponse, ChatMessage, HandoffPacket, OfficialSource } from "./types";

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
  const [sources, setSources] = useState<OfficialSource[]>([]);
  const [sourceError, setSourceError] = useState<string | null>(null);
  const [selectedSourceId, setSelectedSourceId] = useState<string | undefined>();
  const [composerDraft, setComposerDraft] = useState({ text: "", version: 0 });
  const retryText = useRef<string | null>(null);
  const chatHistoryRef = useRef<HTMLElement | null>(null);

  async function loadSources() {
    try {
      setSourceError(null);
      setSources(await getOfficialSources());
    } catch (caught) {
      setSourceError(caught instanceof Error ? caught.message : "Không thể tải nguồn chính thức");
    }
  }

  useEffect(() => { void loadSources(); }, []);

  useEffect(() => {
    const chatHistory = chatHistoryRef.current;
    if (!chatHistory) return;

    chatHistory.scrollTop = chatHistory.scrollHeight;
  }, [activeChannel, error, loading, messages]);

  async function send(text: string) {
    const messageText = text.trim().replace(/^@Trợ lý\s*/i, "");
    const displayText = messageText ? `@Trợ lý ${messageText}` : "@Trợ lý";
    const userMessage: ChatMessage = { id: makeId(), role: "user", text: displayText, createdAt: new Date() };
    const request = { user_id: "D202602628", channel_id: "channel_10", message_text: messageText, timestamp: new Date().toISOString() };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);
    setError(null);
    setTrace({ request, response: null, phase: "running" });
    retryText.current = messageText;
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

  function handoff(message: ChatMessage, response: AgentResponse) {
    const originalQuestion = [...messages].reverse().find((item) => item.role === "user");
    const packet: HandoffPacket = {
      handoff_id: makeId(),
      created_at: new Date().toISOString(),
      user_id: "D202602628",
      channel_id: "channel_10",
      original_message: originalQuestion?.text ?? message.text,
      intent: response.intent,
      status: response.status,
      confidence_score: response.confidence_score,
      reason: response.handoff_metadata.reason,
      source_citation: response.source_citation,
    };
    setTrace((current) => ({ ...current, handoff: packet }));
    setMessages((current) => [...current, {
      id: makeId(),
      role: "assistant",
      text: "Mình đã tag @TA_OnDuty vào thread hỗ trợ để kiểm tra trường hợp này.",
      replyTo: originalQuestion ? { messageId: originalQuestion.id, author: "Học Viên K4", text: originalQuestion.text } : undefined,
      createdAt: new Date(),
    }]);
  }

  function showTicketGuidance() {
    setToast("Mở #ticket-support và dùng lệnh /ticket create.");
    window.setTimeout(() => setToast(null), 3000);
  }

  function jumpToMessage(messageId: string) {
    document.getElementById(`message-${messageId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function putCaseInComposer(question: string) {
    setComposerDraft((current) => ({ text: question, version: current.version + 1 }));
  }

  return (
    <DiscordChrome theme={theme} onToggleTheme={() => setTheme((current) => current === "dark" ? "light" : "dark")} inspectorOpen={inspectorOpen} onToggleInspector={() => setInspectorOpen((current) => !current)} inspector={<AgentInspector trace={trace} />} activeChannel={activeChannel} onChannelSelect={setActiveChannel}>
      <section ref={chatHistoryRef} aria-label="Lịch sử trò chuyện" className="flex-1 overflow-y-auto py-3">
        {activeChannel === "nguon-chinh-thuc" ? <SourceChannelMessages sources={sources} selectedId={selectedSourceId} error={sourceError} onRetry={loadSources} /> : messages.map((message) => <MessageBubble key={message.id} message={message} onOption={send} onHandoff={(response) => handoff(message, response)} onTicket={showTicketGuidance} onSourceOpen={(response) => { setSelectedSourceId(response.source_citation?.ground_truth_id); setActiveChannel("nguon-chinh-thuc"); }} onJumpToMessage={jumpToMessage} />)}
        {loading && <div role="status" className="flex items-center gap-2 px-16 py-3 text-xs text-[var(--discord-text-faint)]"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /> Trợ lý đang kiểm tra nguồn…</div>}
        {error && <div role="alert" className="mx-4 mt-2 flex items-center justify-between rounded border border-red-700 bg-red-950/40 p-3 text-sm text-red-200"><span>{error}</span><button onClick={() => retryText.current && send(retryText.current)} className="rounded bg-red-600 px-3 py-1 text-xs text-white">Thử lại</button></div>}
      </section>
      {activeChannel === "tro-ly-hoi-dap" && <EvaluationPanel onSelectCase={putCaseInComposer} />}
      <Composer onSend={send} disabled={loading || activeChannel === "nguon-chinh-thuc"} prefillText={composerDraft.text} prefillVersion={composerDraft.version} />
      {toast && <div role="status" className="fixed bottom-20 right-5 z-50 rounded bg-[#248046] px-4 py-3 text-sm font-medium text-white shadow-xl">{toast}</div>}
    </DiscordChrome>
  );
}

function SourceChannelMessages({ sources, selectedId, error, onRetry }: { sources: OfficialSource[]; selectedId?: string; error: string | null; onRetry: () => void }) {
  if (error) return <div className="mx-auto max-w-xl rounded border border-red-700 bg-red-950/40 p-4 text-sm text-red-200">{error}<button onClick={onRetry} className="ml-3 rounded bg-red-600 px-3 py-1 text-xs text-white">Thử lại</button></div>;
  return <div className="mx-auto w-full max-w-3xl space-y-3">{sources.map((source) => <article key={source.ground_truth_id} className={`rounded-lg border p-5 ${selectedId === source.ground_truth_id ? "border-[var(--discord-brand)] bg-[var(--discord-bg-elevated)] ring-1 ring-[var(--discord-brand)]/40" : "border-[var(--discord-border)] bg-[var(--discord-bg-elevated)]"}`}><div className="flex gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--discord-brand)] text-xs font-bold text-white">{source.author}</div><div><div className="flex items-center gap-2"><strong className="text-sm text-[var(--discord-text-strong)]">{source.author}</strong><time className="text-[11px] text-[var(--discord-text-faint)]">{source.published_at}</time></div><p className="mt-1 text-xs text-[var(--discord-text-faint)]">{source.channel}</p><p className="mt-2 text-sm leading-6 text-[var(--discord-text)]">{source.content}</p><p className="mt-3 text-xs text-[var(--discord-text-faint)]">{source.title} · {source.message_id}</p></div></div></article>)}{!sources.length && <p className="text-center text-sm text-[var(--discord-text-faint)]">Đang tải nguồn chính thức…</p>}</div>;
}
