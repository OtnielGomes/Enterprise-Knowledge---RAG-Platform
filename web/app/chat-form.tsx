"use client";

import { FormEvent, useState } from "react";

type AskResponse = {
  status: string;
  message: string;
  citations: unknown[];
  corpus_cutoff: string;
};

export function ChatForm() {
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);

  const blankQuestion = "Escreva uma pergunta sobre teletrabalho no PGD.";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) {
      setError(blankQuestion);
      return;
    }

    setPending(true);
    setError(null);

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (response.status === 422) {
        setError(blankQuestion);
        return;
      }
      if (!response.ok) {
        throw new Error("Ask request failed");
      }
      setResult((await response.json()) as AskResponse);
    } catch {
      setError("Não foi possível consultar o assistente. Tente de novo.");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit}>
        <label htmlFor="question">Sua pergunta</label>
        <textarea
          id="question"
          name="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ex.: O teletrabalho é um direito do servidor?"
          required
        />
        <button type="submit" disabled={pending}>
          {pending ? "Consultando…" : "Perguntar"}
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {result?.status === "insufficient_evidence" ? (
        <section className="refusal" aria-live="polite">
          <p>{result.message}</p>
        </section>
      ) : null}
    </>
  );
}
