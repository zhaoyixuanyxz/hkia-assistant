import { getToken } from "./auth";
import { PUBLIC_API_PREFIX } from "./api-base";

const API_BASE =
  typeof window === "undefined"
    ? (process.env.BACKEND_INTERNAL_URL ||
        process.env.NEXT_PUBLIC_API_BASE_URL ||
        "http://127.0.0.1:8000"
      ).replace(/\/$/, "")
    : PUBLIC_API_PREFIX;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: string
  ) {
    super(message);
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(`HTTP ${res.status}`, res.status, text);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function apiFetchWithTimeout<T = unknown>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 120_000
): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await apiFetch<T>(path, { ...init, signal: ctrl.signal });
  } finally {
    clearTimeout(t);
  }
}
