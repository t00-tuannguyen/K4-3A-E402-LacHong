import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import type { AgentRequest, AgentResponse, HandoffPacket } from "../types";

export type AgentTrace = {
  request: AgentRequest | null;
  response: AgentResponse | null;
  phase: "idle" | "running" | "done" | "error";
  error?: string;
  handoff?: HandoffPacket;
};

export function AgentInspector({ trace }: { trace: AgentTrace }) {
  const steps = [
    ["Nhận diện intent", Boolean(trace.response?.intent)],
    ["Kiểm tra entity", trace.phase === "done"],
    ["Đối chiếu nguồn", trace.phase === "done"],
    ["Chọn hành vi", Boolean(trace.response?.status)],
  ] as const;

  return (
    <div className="agent-inspector h-full overflow-y-auto p-4">
      <div className="mb-5">
        <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--discord-text-faint)]">Agent runtime</p>
        <div className="mt-2 flex items-center justify-between text-xs"><span>Mode</span><code className="rounded bg-black/20 px-2 py-1 text-[#00a8fc]">Core AI API</code></div>
      </div>

      <div className="mb-5 space-y-2">
        {steps.map(([label, complete], index) => (
          <div key={label} className="flex items-center gap-2 text-xs">
            {trace.phase === "running" && index === 0 ? <Loader2 size={14} className="animate-spin text-[var(--discord-brand)]" /> : complete ? <CheckCircle2 size={14} className="text-[var(--discord-green)]" /> : <Circle size={14} className="text-[var(--discord-text-subtle)]" />}
            <span>{label}</span>
          </div>
        ))}
      </div>

      {!trace.request && <p className="rounded border border-dashed border-[var(--discord-text-subtle)] p-3 text-xs text-[var(--discord-text-faint)]">Gửi một câu hỏi để xem request, các bước xử lý và response của agent.</p>}
      {trace.request && <JsonBlock title="Request" value={trace.request} />}
      {trace.response && <JsonBlock title="Response" value={trace.response} />}
      {trace.handoff && <JsonBlock title="TA handoff packet" value={trace.handoff} />}
      {trace.error && <div className="mt-3 rounded bg-red-950/40 p-3 text-xs text-red-300">{trace.error}</div>}
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return <section className="mb-4"><h3 className="mb-1 text-[10px] font-bold uppercase text-[var(--discord-text-faint)]">{title}</h3><pre className="max-h-64 overflow-auto rounded p-3 text-[10px] leading-4">{JSON.stringify(value, null, 2)}</pre></section>;
}
