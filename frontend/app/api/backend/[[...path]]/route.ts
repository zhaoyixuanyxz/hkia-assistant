import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

function upstreamBase(): string {
  const raw =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.INTERNAL_API_ORIGIN ||
    "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}

async function proxy(req: NextRequest, segments: string[] | undefined) {
  const sub = segments?.length ? `/${segments.join("/")}` : "";
  const target = `${upstreamBase()}${sub}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    const buf = await req.arrayBuffer();
    if (buf.byteLength > 0) {
      init.body = buf;
    }
  }

  const res = await fetch(target, init);
  const outHeaders = new Headers(res.headers);
  return new Response(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: outHeaders,
  });
}

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function HEAD(
  req: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function PUT(
  req: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function PATCH(
  req: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function DELETE(
  req: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
