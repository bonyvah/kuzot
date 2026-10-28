// Fetch wrapper that attaches the access token and transparently renews it.
//
// The access token lives only in memory. The refresh token is an httpOnly
// cookie scoped to /api/v1/auth: scripts never see it, the browser sends it.
// The backend rotates it on every use, so concurrent refreshes (other
// requests, other tabs) are serialized.

const API_URL = import.meta.env.VITE_API_URL ?? "/api/v1";
// Not a secret: only remembers that a session cookie exists, so a signed-out
// visitor skips the refresh call and other tabs can notice a sign-out.
const SESSION_HINT_KEY = "kuzot.session";
const REFRESH_LOCK = "kuzot.refresh";

interface AccessToken {
  access_token: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
let onSessionExpired: () => void = () => {};

export const session = {
  /** Whether this browser probably holds a refresh cookie. */
  hinted: () => safeStorage(() => localStorage.getItem(SESSION_HINT_KEY)) === "1",
  start(token: AccessToken) {
    accessToken = token.access_token;
    safeStorage(() => localStorage.setItem(SESSION_HINT_KEY, "1"));
  },
  end() {
    accessToken = null;
    safeStorage(() => localStorage.removeItem(SESSION_HINT_KEY));
  },
  hintKey: SESSION_HINT_KEY,
};

/** Called when a request is unauthorized and the session can't be renewed. */
export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

/** Trade the refresh cookie for a new access token. Resolves false when the session is gone. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= withRefreshLock(doRefresh).finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function doRefresh(): Promise<boolean> {
  const res = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "same-origin" });
  if (!res.ok) {
    if (res.status === 401) session.end();
    return false;
  }
  session.start((await res.json()) as AccessToken);
  return true;
}

function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  return navigator.locks ? navigator.locks.request(REFRESH_LOCK, fn) : fn();
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Send the access token and retry once after a refresh on 401. */
  auth?: boolean;
}

export async function api<T>(path: string, { method = "GET", body, auth = true }: RequestOptions = {}): Promise<T> {
  const send = () => {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`;
    return fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  };

  let res = await send();
  if (res.status === 401 && auth) {
    if (await refreshSession()) {
      res = await send();
    }
    if (res.status === 401) {
      session.end();
      onSessionExpired();
    }
  }

  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** FastAPI returns `detail` as a string, or as a list of validation errors (422). */
async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    // Non-JSON body (e.g. a proxy error page).
  }
  return `Request failed (${res.status})`;
}

function safeStorage<T>(fn: () => T): T | null {
  try {
    return fn();
  } catch {
    return null;
  }
}
