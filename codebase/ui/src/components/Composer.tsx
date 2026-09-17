import { Gift, PlusCircle, Send, Smile } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

export function Composer({ onSend, disabled, prefillText, prefillVersion }: { onSend: (text: string) => void; disabled: boolean; prefillText?: string; prefillVersion?: number }) {
  const mention = "@Trợ lý ";
  const [mentionEnabled, setMentionEnabled] = useState(true);
  const [text, setText] = useState("");
  useEffect(() => {
    if (!prefillVersion) return;
    setText(prefillText ?? "");
    setMentionEnabled(true);
  }, [prefillText, prefillVersion]);
  const hasMessage = text.trim().length > 0;
  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = `${mentionEnabled ? mention : ""}${text}`.trim();
    if (!hasMessage || disabled) return;
    onSend(trimmed);
    setText("");
    setMentionEnabled(true);
  }
  return (
    <form onSubmit={submit} className="discord-composer mx-4 mb-4 flex items-center gap-3 rounded-lg px-4 py-3 shadow-sm">
      <PlusCircle size={20} className="text-[var(--discord-text-muted)]" />
      {mentionEnabled && <button type="button" aria-label="Xóa mention @Trợ lý" onClick={() => setMentionEnabled(false)} className="inline-flex shrink-0 items-center gap-1 rounded bg-[#5865f2]/20 px-1.5 py-0.5 text-sm font-semibold text-[#c9cdfb] hover:bg-[#5865f2]/35">@Trợ lý <span aria-hidden="true" className="text-xs opacity-70">×</span></button>}
      <input aria-label="Tin nhắn" value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === "Backspace" && !text && mentionEnabled) { event.preventDefault(); setMentionEnabled(false); } }} disabled={disabled} placeholder={mentionEnabled ? "hỏi về deadline, quy chế..." : "Nhập tin nhắn..."} className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--discord-text-subtle)]" />
      <Gift size={19} className="hidden text-[var(--discord-text-muted)] sm:block" /><Smile size={19} className="hidden text-[var(--discord-text-muted)] sm:block" />
      <button aria-label="Gửi" disabled={disabled || !hasMessage} className="text-[var(--discord-text-muted)] disabled:opacity-30"><Send size={19} /></button>
    </form>
  );
}
