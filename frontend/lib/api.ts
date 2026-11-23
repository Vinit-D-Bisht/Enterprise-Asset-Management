export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly errors?: Array<{ loc: Array<string | number>; msg: string; type: string }>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

function signalExpiredSession() {
  accessToken = null;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("eamms:session-expired"));
  }
}

async function renewAccessToken(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      signalExpiredSession();
      return false;
    }
    const payload = (await response.json()) as { access_token: string };
    accessToken = payload.access_token;
    return true;
  } catch {
    signalExpiredSession();
    return false;
  }
}

async function request<T>(path: string, options: RequestInit = {}, allowRefresh = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && allowRefresh && !path.startsWith("/auth/")) {
    if (await renewAccessToken()) return request<T>(path, options, false);
    throw new ApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let errors: ApiError["errors"];
    try {
      const payload = (await response.json()) as { detail?: string; errors?: ApiError["errors"] };
      message = typeof payload.detail === "string" ? payload.detail : message;
      errors = payload.errors;
    } catch {
      // Keep the status based message when a server or proxy returns non-JSON.
    }
    throw new ApiError(message, response.status, errors);
  }
  if (response.status === 204) return undefined as T;
  if (response.headers.get("content-type")?.includes("application/json")) return (await response.json()) as T;
  return (await response.blob()) as T;
}

export const api = {
  get<T>(path: string) {
    return request<T>(path);
  },
  post<T>(path: string, body?: unknown) {
    return request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
  },
  patch<T>(path: string, body: unknown) {
    return request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
  },
  async login(email: string, password: string) {
    const result = await request<{ access_token: string }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    );
    accessToken = result.access_token;
  },
  async refreshSession() {
    return renewAccessToken();
  },
  async logout() {
    try {
      await request<void>("/auth/logout", { method: "POST" }, false);
    } finally {
      signalExpiredSession();
    }
  },
};
