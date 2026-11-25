import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { getAccessToken, setAccessToken } from "@/core/auth/token-store";
import { ApiError, toApiError } from "./errors";
import type { components } from "./schema";

export type Schemas = components["schemas"];
export const API_PREFIX = "/api/v1";
const REFRESH_PATH = `${API_PREFIX}/admin/auth/refresh`;
const NO_RETRY = ["/admin/auth/login", "/admin/auth/mfa/verify", "/admin/auth/refresh", "/admin/auth/logout"];

type RefreshResult = Schemas["AdminLoginSuccessOut"] | null;
let refreshInFlight: Promise<RefreshResult> | null = null;
let onAuthLost: (() => void) | null = null;

export function setOnAuthLost(fn: (() => void) | null) {
  onAuthLost = fn;
}

/** Single-flight refresh: concurrent callers share one POST /admin/auth/refresh. */
export function refreshSession(): Promise<RefreshResult> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(REFRESH_PATH, {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-Requested-With": "inaiflow" },
        });
        if (!res.ok) {
          setAccessToken(null);
          return null;
        }
        const body = (await res.json()) as Schemas["AdminLoginSuccessOut"];
        setAccessToken(body.token.access_token);
        return body;
      } catch {
        setAccessToken(null);
        return null;
      } finally {
        setTimeout(() => (refreshInFlight = null), 0);
      }
    })();
  }
  return refreshInFlight;
}

function withAuth(req: Request): Request {
  const token = getAccessToken();
  const headers = new Headers(req.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  headers.set("X-Requested-With", "inaiflow");
  return new Request(req, { headers, credentials: "same-origin" });
}

async function authFetch(input: Request): Promise<Response> {
  const retry = input.clone();
  const res = await fetch(withAuth(input));
  const skip = NO_RETRY.some((p) => input.url.includes(p));
  if (res.status !== 401 || skip) return res;
  const refreshed = await refreshSession();
  if (!refreshed) {
    onAuthLost?.();
    return res;
  }
  return fetch(withAuth(retry));
}

export const api = createClient<paths>({ baseUrl: "", fetch: authFetch });

/** Unwraps an openapi-fetch result: returns data or throws ApiError. */
export async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let r: { data?: T; error?: unknown; response: Response };
  try {
    r = await p;
  } catch (e) {
    throw new ApiError(0, "NETWORK_ERROR", e instanceof Error ? e.message : "Network error");
  }
  if (!r.response.ok) throw toApiError(r.response.status, r.error);
  return r.data as T;
}
