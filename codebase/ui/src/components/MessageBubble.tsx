import { AlertTriangle, Bot, ExternalLink, Headphones, ShieldAlert } from "lucide-react";
import type { AgentResponse, ChatMessage } from "../types";

export function MessageBubble({ message, onOption, onHandoff, onSourceOpen }: { message: ChatMessage; onOption: (value: string) => void; onHandoff: () => void; onSourceOpen: (response: AgentResponse) => void }) {
  const assistant = message.role === "assistant";
  return (
    <article className="discord-message group flex gap-3 px-4 py-3">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${assistant ? "bg-[var(--discord-brand)]" : "bg-[var(--discord-green)]"}`}>
        {assistant ? <Bot size={21} /> : "HV"}
      </div>
      <div className="min-w-0 max-w-3xl flex-1">
        <div className="flex items-center gap-2"><strong className={assistant ? "text-[#c9cdfb]" : "text-[var(--discord-text-strong)]"}>{assistant ? "Trợ lý K4" : "Học Viên K4"}</strong>{assistant && <span className="rounded bg-[var(--discord-brand)] px-1.5 text-[10px] font-bold text-white">BOT</span>}<time className="text-[11px] text-[var(--discord-text-faint)]">{message.createdAt.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</time></div>
        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[var(--discord-text)]">{assistant ? message.text : <HighlightedMention text={message.text} />}</p>
        {message.response && <ResponseDetails response={message.response} onOption={onOption} onHandoff={onHandoff} onSourceOpen={onSourceOpen} />}
      </div>
    </article>
  );
}

function HighlightedMention({ text }: { text: string }) {
  const match = text.match(/^(@Trợ lý)(?:\s+|$)(.*)$/iu);
  if (!match) return text;
  return <><span className="rounded bg-[var(--discord-brand)]/25 px-1 py-0.5 text-[#c9cdfb]">{match[1]}</span>{match[2] ? ` ${match[2]}` : ""}</>;
}

function ResponseDetails({ response, onOption, onHandoff, onSourceOpen }: { response: AgentResponse; onOption: (value: string) => void; onHandoff: () => void; onSourceOpen: (response: AgentResponse) => void }) {
  const conflict = response.status === "source_conflict";
  const rejected = response.status === "rejected";
  const needsHandoff = response.status === "ta_handoff" || conflict;
  return (
    <div className={`agent-card mt-3 rounded border-l-4 p-3 ${conflict ? "border-orange-500" : rejected ? "border-purple-500" : needsHandoff ? "border-red-500" : response.status === "clarification_needed" ? "border-amber-500" : "border-[var(--discord-brand)]"}`}>
      <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase text-[var(--discord-text-muted)]">
        {conflict ? <AlertTriangle size={15} /> : rejected ? <ShieldAlert size={15} /> : needsHandoff ? <Headphones size={15} /> : null}
        {response.status.split("_").join(" ")}
        <span className="ml-auto font-normal normal-case text-[var(--discord-text-subtle)]">confidence {Math.round(response.confidence_score * 100)}%</span>
      </div>
      {response.source_citation && (
        <div className="rounded bg-[var(--discord-bg-tertiary)] p-3 text-xs text-[var(--discord-text-muted)]">
          <button type="button" onClick={() => onSourceOpen(response)} className="block text-left text-[#c9cdfb] hover:underline"><strong>{response.source_citation.title}</strong></button>
          <span>{response.source_citation.channel} · {response.source_citation.message_id}</span>
          {response.source_citation.url && <a href={response.source_citation.url} target="_blank" rel="noreferrer" className="ml-2 inline-flex text-[#00a8fc]"><ExternalLink size={13} /></a>}
        </div>
      )}
      {response.interactive_elements?.type === "chips" && (
        <div className="mt-3 flex max-w-full flex-wrap gap-1.5">
            {response.interactive_elements.options.map((option, index) => <button key={option.label} aria-label={option.label} onClick={() => onOption(option.value ?? option.label)} className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-[#3f4147] bg-[#2b2d31] px-2.5 py-1 text-sm font-normal text-[var(--discord-text)] shadow-sm transition-colors hover:bg-[#35373c]"><span className="text-lg font-bold leading-none text-white [text-shadow:1px_1px_0_#1e1f22,-1px_-1px_0_#1e1f22]">{index + 1}</span>{option.label}</button>)}
        </div>
      )}
      {needsHandoff && <button onClick={onHandoff} className={`mt-3 rounded px-3 py-1.5 text-xs font-semibold text-white ${conflict ? "bg-orange-600 hover:bg-orange-500" : "bg-red-600 hover:bg-red-500"}`}>{conflict ? "Gắn cờ ưu tiên cho TA" : "Chuyển cho TA hỗ trợ"}</button>}
    </div>
  );
}
