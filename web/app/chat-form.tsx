"use client";

import { FormEvent, useState } from "react";

type Citation = {
  act_id: string;
  act_label: string;
  article: string;
  page: number;
  pdf_url: string;
};

type AskResponse = {
  status: string;
  message: string;
  citations: Citation[];
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
          placeholder="Ex.: A participação no teletrabalho constitui direito adquirido?"
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
      {result?.status === "answered" ? (
        <section className="answer" aria-live="polite">
          <p>{result.message}</p>
          {result.citations.length > 0 ? (
            <ul className="citations">
              {result.citations.map((citation) => (
                <li key={`${citation.act_id}:${citation.article}:${citation.page}`}>
                  <a href={citation.pdf_url} target="_blank" rel="noreferrer">
                    {citation.act_label}, art. {citation.article}, p.{" "}
                    {citation.page}
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
