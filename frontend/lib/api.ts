const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "access_token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

interface ApiOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Set false for endpoints that must not redirect to /login on 401 (the login call). */
  redirectOn401?: boolean;
}

function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg ?? "Invalid value").join("; ");
  }
  return fallback;
}

function rejectUnauthorized(): void {
  clearToken();
  window.location.assign("/login");
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, redirectOn401 = true } = options;
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Please try again.");
  }

  if (response.status === 401 && redirectOn401) rejectUnauthorized();
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(response.status, errorMessage(data.detail, response.statusText));
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export type AssistantEvent =
  | { type: "tool"; name: string }
  | { type: "token"; text: string }
  | { type: "error"; message: string }
  | { type: "done"; status: string };

function parseEvent(block: string): AssistantEvent | null {
  const line = block.split("\n").find((l) => l.startsWith("data: "));
  return line ? (JSON.parse(line.slice(6)) as AssistantEvent) : null;
}

/** Streams the assistant's answer. Calls onEvent for each Server-Sent Event as it arrives. */
export async function askAssistant(
  question: string,
  onEvent: (event: AssistantEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/assistant/ask`, {
      method: "POST",
      headers,
      body: JSON.stringify({ question }),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(0, "Cannot reach the server. Please try again.");
  }
  if (response.status === 401) rejectUnauthorized();
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(response.status, errorMessage(data.detail, response.statusText));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = parseEvent(block);
      if (event) onEvent(event);
    }
  }
}
