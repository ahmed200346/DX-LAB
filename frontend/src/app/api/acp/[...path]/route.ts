import { NextRequest, NextResponse } from "next/server";

/**
 * Reverse proxy to the ACP hub so the Next app can call the hub same-origin:
 *   GET  /api/acp/agents     →  GET  {ACP}/agents
 *   POST /api/acp/runs      →  POST {ACP}/runs
 *
 * Set NEXT_PUBLIC_ACP_URL (and optionally ACP_SERVER_URL for server-only override).
 */

function hubBase(): string {
  const raw =
    process.env.ACP_SERVER_URL?.trim() ||
    process.env.NEXT_PUBLIC_ACP_URL?.trim() ||
    "http://127.0.0.1:8010";
  return raw.replace(/\/$/, "");
}

function buildTarget(request: NextRequest, pathSegments: string[]): string {
  const path = pathSegments.map(encodeURIComponent).join("/");
  const u = new URL(request.url);
  const suffix = path ? `/${path}` : "";
  return `${hubBase()}${suffix}${u.search}`;
}

async function proxy(
  request: NextRequest,
  method: string,
  pathSegments: string[]
): Promise<NextResponse> {
  const targetUrl = buildTarget(request, pathSegments);
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const accept = request.headers.get("accept");
  if (accept) headers.set("accept", accept);

  const init: RequestInit = {
    method,
    headers,
    signal: AbortSignal.timeout(120_000),
  };

  if (method !== "GET" && method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    const upstream = await fetch(targetUrl, init);
    const outHeaders = new Headers();
    const ct = upstream.headers.get("content-type");
    if (ct) outHeaders.set("content-type", ct);
    const body = await upstream.arrayBuffer();
    return new NextResponse(body, { status: upstream.status, headers: outHeaders });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json(
      {
        error: "ACP proxy failed",
        detail: message,
        target: targetUrl,
        hint: "Start the hub: cd backend && python -m acp_hub.main",
      },
      { status: 502 }
    );
  }
}

type Ctx = { params: Promise<{ path?: string[] }> };

export async function GET(request: NextRequest, ctx: Ctx) {
  const { path = [] } = await ctx.params;
  return proxy(request, "GET", path);
}

export async function POST(request: NextRequest, ctx: Ctx) {
  const { path = [] } = await ctx.params;
  return proxy(request, "POST", path);
}

export async function HEAD(request: NextRequest, ctx: Ctx) {
  const { path = [] } = await ctx.params;
  return proxy(request, "HEAD", path);
}
