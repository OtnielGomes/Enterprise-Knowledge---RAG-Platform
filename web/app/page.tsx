import { ChatForm } from "./chat-form";
import { loadCorpusCutoff } from "./ask";

export const dynamic = "force-dynamic";

function formatCutoff(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`);
  return date.toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default async function HomePage() {
  const corpusCutoff = await loadCorpusCutoff();

  return (
    <main className="page">
      <p className="kicker">Unifesp · Programa de Gestão e Desempenho</p>
      <h1>PGD Teletrabalho</h1>
      <p className="lede">
        Pergunte sobre as regras vigentes de teletrabalho. Sem artigo recuperado
        que sustente a resposta, o assistente recusa.
      </p>
      <dl className="cutoff">
        <dt>Corte do corpus</dt>
        <dd>
          {formatCutoff(corpusCutoff)}
          <p>Respostas valem nesta data, não no diário oficial de hoje.</p>
        </dd>
      </dl>
      <ChatForm />
    </main>
  );
}
