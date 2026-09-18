import { askBaseUrl } from "../../ask";

type RouteContext = {
  params: Promise<{ filename: string }>;
};

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const { filename } = await context.params;
  if (
    filename.includes("/") ||
    filename.includes("\\") ||
    !filename.endsWith(".pdf")
  ) {
    return new Response("Not found", { status: 404 });
  }

  const response = await fetch(`${askBaseUrl()}/snapshot/${filename}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    return new Response("Not found", { status: 404 });
  }

  return new Response(response.body, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="${filename}"`,
    },
  });
}
