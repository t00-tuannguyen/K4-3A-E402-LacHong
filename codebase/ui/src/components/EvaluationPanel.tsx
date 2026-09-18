import { useEffect, useMemo, useState } from "react";
import { ChevronDown, FlaskConical, RotateCcw } from "lucide-react";
import { getEvaluationCases, sendAgentMessage } from "../services/agentClient";
import { effectiveAction, evaluateResponse } from "../evaluation";
import type { EvaluationCase, EvaluationResult } from "../types";

const CATEGORY_LABELS: Record<string, string> = {
  happy_path: "Có nguồn / trả lời được",
  layer_1_no_ground_truth: "Chưa có thông báo chính thức",
  layer_2_ambiguity: "Cần làm rõ câu hỏi",
  layer_3_out_of_scope: "Ngoài quyền hỗ trợ",
  layer_4_domain_conflict: "Mâu thuẫn nguồn",
  adversarial_edge_case: "Bẫy an toàn / prompt injection",
};

function categoryLabel(category: string) {
  return CATEGORY_LABELS[category] ?? category;
}

export function EvaluationPanel({ onSelectCase }: { onSelectCase: (question: string) => void }) {
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [category, setCategory] = useState("happy_path");
  const [selectedId, setSelectedId] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [results, setResults] = useState<Record<string, EvaluationResult>>({});
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ done: 0, total: 0 });

  useEffect(() => {
    void getEvaluationCases()
      .then((loaded) => {
        setCases(loaded);
        setSelectedId(loaded[0]?.case_id ?? "");
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Không thể tải Dev Set"))
      .finally(() => setLoading(false));
  }, []);

  const categories = useMemo(() => [...new Set(cases.map((testCase) => testCase.category))], [cases]);
  const visibleCases = useMemo(() => cases.filter((testCase) => testCase.category === category), [cases, category]);
  const selectedCase = visibleCases.find((testCase) => testCase.case_id === selectedId) ?? visibleCases[0];
  const resultList = Object.values(results);
  const passed = resultList.filter((result) => result.passed).length;

  function changeCategory(nextCategory: string) {
    setCategory(nextCategory);
    const nextCases = cases.filter((testCase) => testCase.category === nextCategory);
    setSelectedId(nextCases[0]?.case_id ?? "");
  }

  async function runCases(targets: EvaluationCase[]) {
    if (!targets.length || running) return;
    setRunning(true);
    setError(null);
    setProgress({ done: 0, total: targets.length });
    for (const [index, testCase] of targets.entries()) {
      try {
        const response = await sendAgentMessage({
          user_id: "golden-set-ui",
          channel_id: "hoi-dap-lab",
          message_text: testCase.user_query,
          timestamp: new Date().toISOString(),
        });
        const result = evaluateResponse(testCase, response);
        setResults((current) => ({ ...current, [testCase.case_id]: result }));
      } catch (caught) {
        setError(`${testCase.case_id}: ${caught instanceof Error ? caught.message : "Không thể chạy case"}`);
        break;
      }
      setProgress({ done: index + 1, total: targets.length });
    }
    setRunning(false);
  }

  function selectCaseForChat() {
    if (!selectedCase) return;
    onSelectCase(selectedCase.user_query);
    setExpanded(false);
  }

  return <section aria-label="Development set evaluation" className="border-t border-[var(--discord-border)] bg-[var(--discord-bg-secondary)] px-4 py-2">
    <button type="button" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)} className="flex w-full items-center gap-2 text-left text-xs text-[var(--discord-text-muted)]">
      <FlaskConical size={15} className="text-[var(--discord-brand)]" />
      <span className="font-medium text-[var(--discord-text)]">Evaluation</span>
      <span>· {cases.length || 15} test cases</span>
      {resultList.length > 0 && <span className="rounded bg-[var(--discord-bg-tertiary)] px-1.5 py-0.5 text-[10px]">{passed}/{resultList.length} pass</span>}
      <ChevronDown size={15} className={`ml-auto transition-transform ${expanded ? "rotate-180" : ""}`} />
    </button>

    {expanded && <div className="mt-3 max-h-72 space-y-3 overflow-y-auto pb-1">
      <p className="text-[11px] text-[var(--discord-text-faint)]">Chạy qua backend và so với Dev Set; đây là công cụ review trong quá trình phát triển.</p>
      {loading && <p className="text-xs text-[var(--discord-text-faint)]">Đang tải Dev Set…</p>}
      {error && <p role="alert" className="rounded border border-red-700 bg-red-950/30 p-2 text-[11px] text-red-200">{error}</p>}
      {!loading && cases.length > 0 && <>
        <div className="flex flex-wrap gap-1.5" aria-label="Nhóm Dev Set">
          {categories.map((item) => <button key={item} type="button" onClick={() => changeCategory(item)} disabled={running} className={`rounded-md px-2 py-1 text-[11px] disabled:opacity-50 ${category === item ? "bg-[var(--discord-brand)] text-white" : "bg-[var(--discord-bg-active)] text-[var(--discord-text-muted)] hover:text-[var(--discord-text)]"}`}>{categoryLabel(item)} · {cases.filter((testCase) => testCase.category === item).length}</button>)}
        </div>
        <label className="block text-[11px] text-[var(--discord-text-faint)]">Test case
          <select aria-label="Test case" value={selectedCase?.case_id ?? ""} onChange={(event) => setSelectedId(event.target.value)} disabled={running} className="mt-1 w-full rounded bg-[var(--discord-bg-tertiary)] p-2 text-xs text-[var(--discord-text)]">
            {visibleCases.map((testCase) => <option key={testCase.case_id} value={testCase.case_id}>{testCase.case_id} · {testCase.user_query}</option>)}
          </select>
        </label>
        <div className="flex gap-2">
          <button type="button" onClick={selectCaseForChat} disabled={running} className="flex flex-1 items-center justify-center rounded bg-[var(--discord-brand)] px-2 py-2 text-xs font-medium text-white disabled:opacity-50">Đưa vào chat</button>
          <button type="button" onClick={() => { setResults({}); void runCases(cases); }} disabled={running} className="flex flex-1 items-center justify-center gap-1 rounded bg-[var(--discord-bg-active)] px-2 py-2 text-xs text-[var(--discord-text)] disabled:opacity-50"><RotateCcw size={13} /> Chạy Dev Set (15)</button>
        </div>
        {running && <p role="status" className="text-[11px] text-[var(--discord-text-faint)]">Đang chạy {progress.done}/{progress.total} case…</p>}
        {selectedCase && results[selectedCase.case_id] && <ResultCard result={results[selectedCase.case_id]} />}
      </>}
    </div>}
  </section>;
}

function ResultCard({ result }: { result: EvaluationResult }) {
  const actualAction = effectiveAction(result.response);
  const expected = result.testCase;
  return <div className={`rounded border p-3 text-[11px] ${result.passed ? "border-emerald-800 bg-emerald-950/20" : "border-red-800 bg-red-950/20"}`}>
    <p className={`font-bold ${result.passed ? "text-emerald-300" : "text-red-300"}`}>{result.passed ? "PASS" : "FAIL"} · {expected.case_id}</p>
    <p className="mt-2 text-[var(--discord-text-muted)]">Intent: {result.response.intent} / {expected.expected_intent ?? "-"}</p>
    <p className="text-[var(--discord-text-muted)]">Action: {actualAction} / {expected.expected_action ?? "-"}</p>
    <p className="text-[var(--discord-text-muted)]">Nguồn: {result.response.source_citation?.ground_truth_id ?? "-"} / {expected.expected_ground_truth_id ?? "-"}</p>
  </div>;
}
