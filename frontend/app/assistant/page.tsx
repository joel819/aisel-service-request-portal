"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { api, askAssistant, type AssistantEvent } from "@/lib/api";

const MAX_LENGTH = 1000;
const SUGGESTIONS = [
  "Show me urgent requests from this week",
  "Summarise request #1",
  "How many requests are still open for client Acme?",
];
const TOOL_LABELS: Record<string, string> = {
  search_requests: "search",
  get_request: "lookup",
  count_requests: "count",
};

interface Turn {
  id: number;
  question: string;
  answer: string;
  tools: string[];
  error: string | null;
  finished: boolean;
}

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);
  const nextId = useRef(1);
  const streaming = turns.some((turn) => !turn.finished);

  useEffect(() => {
    api<{ role: string }>("/api/auth/me")
      .then((me) => setRole(me.role))
      .catch(() => setRole(null));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest" });
  }, [turns]);

  function update(id: number, change: (turn: Turn) => Turn) {
    setTurns((all) => all.map((turn) => (turn.id === id ? change(turn) : turn)));
  }

  function handleEvent(id: number, event: AssistantEvent) {
    if (event.type === "token") {
      update(id, (turn) => ({ ...turn, answer: turn.answer + event.text }));
    } else if (event.type === "tool") {
      update(id, (turn) => ({ ...turn, tools: [...turn.tools, event.name] }));
    } else if (event.type === "error") {
      update(id, (turn) => ({ ...turn, error: event.message }));
    }
  }

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed) {
      setFormError("Type a question first.");
      return;
    }
    if (trimmed.length > MAX_LENGTH) {
      setFormError(`Questions can be up to ${MAX_LENGTH} characters.`);
      return;
    }
    setFormError(null);
    setQuestion("");
    const id = nextId.current++;
    setTurns((all) => [...all, { id, question: trimmed, answer: "", tools: [], error: null, finished: false }]);
    controller.current = new AbortController();
    try {
      await askAssistant(trimmed, (event) => handleEvent(id, event), controller.current.signal);
    } catch (e) {
      const stopped = e instanceof DOMException && e.name === "AbortError";
      if (!stopped) update(id, (turn) => ({ ...turn, error: e instanceof Error ? e.message : "Something went wrong" }));
    } finally {
      update(id, (turn) => ({ ...turn, finished: true }));
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  return (
    <div>
      <h1 className="font-serif text-3xl font-bold">
        Ask the <span className="shadow-[inset_0_-0.4em_0_0_#36d6a0]">assistant</span>
      </h1>
      <p className="mb-5 mt-1 text-sm text-ink/65">
        Ask about service requests in plain English. It only reads what you are allowed to see and cannot change anything.
      </p>

      <div className="grid gap-5 lg:grid-cols-[1fr_300px]">
        <section className="card flex flex-col p-4" aria-label="Conversation">
          <div className="flex-1 space-y-4" aria-live="polite">
            <div className="max-w-[85%] rounded-2xl border-2 border-ink bg-white p-3 text-sm shadow-hard-sm">
              Hi! I can search your requests, summarise one by its number, or count them. What would you like to know?
            </div>
            {turns.map((turn) => (
              <div key={turn.id} className="space-y-3">
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl border-2 border-ink bg-lilac px-4 py-2 text-sm font-bold shadow-hard-sm">
                    {turn.question}
                  </div>
                </div>
                <div className="max-w-[85%] rounded-2xl border-2 border-ink bg-white p-3 text-sm shadow-hard-sm">
                  {turn.tools.length > 0 && (
                    <div className="mb-2 flex flex-wrap gap-1.5">
                      {turn.tools.map((tool, index) => (
                        <span key={index} className="chip bg-mint">
                          tool · {TOOL_LABELS[tool] ?? tool}
                        </span>
                      ))}
                    </div>
                  )}
                  {turn.answer ? (
                    <p className="whitespace-pre-wrap">{turn.answer}</p>
                  ) : (
                    !turn.error && <p className="text-ink/65">{turn.finished ? "No answer." : "Thinking..."}</p>
                  )}
                  {turn.error && <p className="mt-2 rounded-lg border-2 border-ink bg-blush px-2 py-1 font-bold">{turn.error}</p>}
                </div>
              </div>
            ))}
            <div ref={bottom} />
          </div>

          <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-2 border-t-2 border-ink pt-4">
            <label htmlFor="question" className="sr-only">
              Your question
            </label>
            <textarea
              id="question"
              className="input min-h-16"
              placeholder="For example: show urgent requests from this week"
              maxLength={MAX_LENGTH}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            {formError && <p className="text-sm font-bold text-[#b3261e]">{formError}</p>}
            <div className="flex items-center gap-2">
              <button type="submit" className="btn-primary" disabled={streaming}>
                {streaming ? "Answering..." : "Ask"}
              </button>
              {streaming && (
                <button type="button" className="btn-secondary" onClick={() => controller.current?.abort()}>
                  Stop
                </button>
              )}
              <span className="ml-auto text-xs text-ink/55">
                {question.length}/{MAX_LENGTH}
              </span>
            </div>
          </form>
        </section>

        <aside className="space-y-5">
          <section className="card bg-sky p-4">
            <h2 className="label-caps mb-3">Try</h2>
            <div className="space-y-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={streaming}
                  className="w-full rounded-xl border-2 border-ink bg-white px-3 py-2 text-left text-sm font-bold shadow-hard-sm transition hover:-translate-y-px active:translate-x-px active:translate-y-px active:shadow-none disabled:opacity-50"
                  onClick={() => void ask(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </section>

          <section className="card p-4">
            <h2 className="label-caps mb-3">Who sees what</h2>
            {role && (
              <span className={`chip ${role === "admin" ? "bg-sun" : "bg-lilac"}`}>
                {role === "admin" ? "admin · all requests" : "user · your own requests"}
              </span>
            )}
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-xs text-ink/80">
              <li>Read-only: three tools, no way to create, edit or delete.</li>
              <li>Runs as you, with the same access rule as the rest of the app.</li>
              <li>Links and images are removed from every answer.</li>
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
