"use client";

import { FormEvent, useRef, useState } from "react";

import { ErrorState } from "@/components/States";
import { askAssistant, type AssistantEvent } from "@/lib/api";

const MAX_LENGTH = 1000;
const SUGGESTIONS = [
  "Show me urgent requests from this week",
  "Summarise request #1",
  "How many requests are still open for client Acme?",
];

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [working, setWorking] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [asked, setAsked] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  function handleEvent(event: AssistantEvent) {
    if (event.type === "token") {
      setWorking(null);
      setAnswer((previous) => previous + event.text);
    } else if (event.type === "tool") {
      setWorking("Looking through your requests...");
    } else if (event.type === "error") {
      setError(event.message);
    }
  }

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed) {
      setError("Type a question first.");
      return;
    }
    if (trimmed.length > MAX_LENGTH) {
      setError(`Questions can be up to ${MAX_LENGTH} characters.`);
      return;
    }
    controller.current?.abort();
    controller.current = new AbortController();
    setError(null);
    setAnswer("");
    setAsked(trimmed);
    setWorking("Thinking...");
    setStreaming(true);
    try {
      await askAssistant(trimmed, handleEvent, controller.current.signal);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        setError(e instanceof Error ? e.message : "Something went wrong");
      }
    } finally {
      setWorking(null);
      setStreaming(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  function stop() {
    controller.current?.abort();
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold">Ask the assistant</h1>
      <p className="mb-4 text-sm text-slate-500">
        Ask about service requests in plain English. It only reads requests you are allowed to see and
        cannot change anything.
      </p>

      <form onSubmit={handleSubmit} className="card space-y-3 p-4">
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <textarea
          id="question"
          className="input min-h-24"
          placeholder="For example: show urgent requests from this week"
          maxLength={MAX_LENGTH}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="flex flex-wrap items-center gap-2">
          <button type="submit" className="btn-primary" disabled={streaming}>
            {streaming ? "Answering..." : "Ask"}
          </button>
          {streaming && (
            <button type="button" className="btn-secondary" onClick={stop}>
              Stop
            </button>
          )}
          <span className="ml-auto text-xs text-slate-400">
            {question.length}/{MAX_LENGTH}
          </span>
        </div>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            disabled={streaming}
            className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-600 hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50"
            onClick={() => {
              setQuestion(suggestion);
              void ask(suggestion);
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4">
          <ErrorState message={error} />
        </div>
      )}

      {asked && (
        <div className="card mt-4 p-4" aria-live="polite">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">You asked</p>
          <p className="mb-3 text-sm text-slate-700">{asked}</p>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Answer</p>
          {answer ? (
            <p className="whitespace-pre-wrap text-sm text-slate-900">{answer}</p>
          ) : (
            !error && <p className="text-sm text-slate-500">{working ?? "No answer."}</p>
          )}
          {answer && working && <p className="mt-2 text-xs text-slate-500">{working}</p>}
        </div>
      )}
    </div>
  );
}
