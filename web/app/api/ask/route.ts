import { askBaseUrl } from "../../ask";

export async function POST(request: Request): Promise<Response> {
  const payload = await request.json();
  const response = await fetch(`${askBaseUrl()}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await response.text();
  return new Response(body, {
    status: response.status,
    headers: { "Content-Type": "application/json" },
  });
}
