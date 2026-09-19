# v1 quality is the Golden Set in CI, not traces or LLM-judge metrics

Ask is right only when the annotator-owned Golden Set passes through Ask. GitHub Actions on `pull_request` and `push` to `main` run `pytest` in `api/` (empty `OPENAI_API_KEY`, extractive draft) and `npm run typecheck` in `web/`. Langfuse, RAGAS, and OpenTelemetry are out of v1: they do not unblock the Servidor, they are not the quality score, and an LLM judge can agree with a fabricated Citation (ADR-0003). No CD, no OpenAI secret in CI, no local CI-mirror script.

**Status:** accepted

**Considered Options:** Langfuse traces as quality; RAGAS (or other LLM-as-judge) as a second gate; OpenTelemetry in the same slice; CI that calls a chat model — all rejected so a trace or a judge cannot contradict the Golden Set.
