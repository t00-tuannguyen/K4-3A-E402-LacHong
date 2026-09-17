import type { DemoScenario } from "../types";

const tones = {
  green: "border-emerald-600/60 bg-emerald-500/10 hover:bg-emerald-500/20",
  yellow: "border-amber-600/60 bg-amber-500/10 hover:bg-amber-500/20",
  red: "border-red-600/60 bg-red-500/10 hover:bg-red-500/20",
  purple: "border-purple-600/60 bg-purple-500/10 hover:bg-purple-500/20",
  orange: "border-orange-600/60 bg-orange-500/10 hover:bg-orange-500/20",
};

export function ScenarioBar({ scenarios, onSelect, disabled }: { scenarios: DemoScenario[]; onSelect: (question: string) => void; disabled: boolean }) {
  return (
    <div className="scenario-bar border-y px-4 py-2">
      <div className="mx-auto flex max-w-4xl gap-2 overflow-x-auto">
        <span className="shrink-0 self-center text-[11px] font-semibold uppercase text-[var(--discord-text-faint)]">Demo CP3</span>
        {scenarios.map((scenario) => (
          <button key={scenario.label} disabled={disabled} onClick={() => onSelect(scenario.question)} className={`shrink-0 rounded border bg-[var(--discord-bg-tertiary)] px-3 py-1.5 text-xs text-[var(--discord-text)] disabled:opacity-40 ${tones[scenario.tone]}`}>{scenario.label}</button>
        ))}
      </div>
    </div>
  );
}
