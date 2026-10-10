/**
 * Typed client for the MineMind AI API.
 *
 * Every failure is converted into an ApiError with a user-safe message. Raw
 * response bodies, stack traces and network internals are never shown.
 */

export type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor(
    message: string,
    options: { status: number; code: string; details?: unknown; requestId?: string | null },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? null;
    this.requestId = options.requestId ?? null;
  }
}

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export function buildUrl(path: string, params?: QueryParams): string {
  const search = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        search.set(key, String(value));
      }
    }
  }
  const query = search.toString();
  return `${API_BASE}${path}${query ? `?${query}` : ""}`;
}

function fallbackMessage(status: number): string {
  if (status === 404) return "The requested item was not found.";
  if (status === 413) return "The file is too large to upload.";
  if (status === 415) return "This file type is not supported.";
  if (status === 422) return "The request could not be processed.";
  if (status >= 500) return "The server could not complete the request. Try again shortly.";
  return "The request failed.";
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    const envelope = (body as { error?: Record<string, unknown> } | null)?.error ?? {};
    const message =
      typeof envelope.message === "string" && envelope.message.length > 0
        ? envelope.message
        : fallbackMessage(response.status);
    return new ApiError(message, {
      status: response.status,
      code: typeof envelope.code === "string" ? envelope.code : "http_error",
      details: envelope.details,
      requestId: typeof envelope.request_id === "string" ? envelope.request_id : null,
    });
  } catch {
    return new ApiError(fallbackMessage(response.status), {
      status: response.status,
      code: "http_error",
    });
  }
}

async function request<T>(url: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" }, ...init });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(
      "The MineMind API could not be reached. Check that the backend is running and try again.",
      { status: 0, code: "network_error" },
    );
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("The server returned an unexpected response.", {
      status: response.status,
      code: "invalid_response",
    });
  }
}

export function apiGet<T>(path: string, params?: QueryParams, signal?: AbortSignal): Promise<T> {
  return request<T>(buildUrl(path, params), { method: "GET", signal });
}

export function apiUpload<T>(path: string, form: FormData, signal?: AbortSignal): Promise<T> {
  return request<T>(buildUrl(path), { method: "POST", body: form, signal });
}

export function apiDelete(path: string, signal?: AbortSignal): Promise<void> {
  return request<void>(buildUrl(path), { method: "DELETE", signal });
}

/** Download a file from the API (for example, a generated report). */
export async function apiDownload(path: string, params?: QueryParams): Promise<{ blob: Blob; filename: string }> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), { method: "GET" });
  } catch {
    throw new ApiError("The MineMind API could not be reached.", { status: 0, code: "network_error" });
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return { blob: await response.blob(), filename: match?.[1] ?? "download" };
}

/** POST a JSON body and download the response (for example, a generated report). */
export async function apiPostDownload(
  path: string,
  body: unknown,
): Promise<{ blob: Blob; filename: string }> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/html,application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("The MineMind API could not be reached.", { status: 0, code: "network_error" });
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return { blob: await response.blob(), filename: match?.[1] ?? "download" };
}
