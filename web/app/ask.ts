const PLACEHOLDER_CORPUS_CUTOFF = "2025-12-31";
const DEFAULT_ASK_URL = "http://localhost:8000";

export function askBaseUrl(): string {
  return process.env.ASK_API_URL ?? DEFAULT_ASK_URL;
}

export async function loadCorpusCutoff(): Promise<string> {
  try {
    const response = await fetch(`${askBaseUrl()}/health`, { cache: "no-store" });
    if (!response.ok) {
      return PLACEHOLDER_CORPUS_CUTOFF;
    }
    const body = (await response.json()) as { corpus_cutoff?: string };
    return body.corpus_cutoff ?? PLACEHOLDER_CORPUS_CUTOFF;
  } catch {
    return PLACEHOLDER_CORPUS_CUTOFF;
  }
}
