import createClient, { type Client } from "openapi-fetch";
import { readAccessToken } from "@/core/auth/token";
import { sessionStore, type MeOut } from "@/core/auth/session-store";
import { ApiError, toApiError } from "./errors";
import type { ApiPaths, OrgPaths } from "./types";

export const API_PREFIX = "/api/v1";
const REFRESH_URL = `${API_PREFIX}/auth/refresh`;
/** Routes that must never carry X-Organization-ID (plan §3.1). */
const PERSONAL_PREFIXES = ["/auth/", "/me", "/organizations", "/meta/", "/health", "/storage/"].map((p) => API_PREFIX + p);

let refreshInFlight: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  if (sessionStore.get().impersonation) return false; // impersonation tokens have no refresh cookie
  try {
    const res = await fetch(REFRESH_URL, {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-With": "inaiflow" },
    });
    if (!res.ok) return false;
    const body = (await res.json()) as { token?: unknown; user?: MeOut };
    const token = readAccessToken(body.token);
    sessionStore.setSession(token.access_token, body.user ?? null);
    return true;
  } catch {
    return false;
  }
}

/** Single-flight refresh: concurrent 401s share one `POST /auth/refresh`. */
export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= doRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

function pathOf(url: string): string {
  return new URL(url, "http://local").pathname;
}

function withHeaders(req: Request, orgId: string | null): Request {
  const headers = new Headers(req.headers);
  const token = sessionStore.get().accessToken;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const path = pathOf(req.url);
  if (orgId && !PERSONAL_PREFIXES.some((p) => path.startsWith(p))) headers.set("X-Organization-ID", orgId);
  return new Request(req, { headers, credentials: "same-origin" });
}

async function errorCodeOf(res: Response): Promise<string | null> {
  try {
    const body: unknown = await res.clone().json();
    return toApiError(res.status, body).code;
  } catch {
    return null;
  }
}

/** fetch wrapper: auth header, org header, one refresh-and-retry on expired tokens. */
function makeFetch(orgId: string | null) {
  return async (input: Request): Promise<Response> => {
    const retryCopy = input.clone();
    const res = await fetch(withHeaders(input, orgId));
    const path = pathOf(input.url);
    if (res.status !== 401 || path.startsWith(`${API_PREFIX}/auth/`)) return res;
    const code = await errorCodeOf(res);
    if (code !== "TOKEN_EXPIRED" && code !== "UNAUTHENTICATED") return res;
    const ok = await refreshSession();
    if (!ok) {
      sessionStore.end("expired");
      return res;
    }
    return fetch(withHeaders(retryCopy, orgId));
  };
}

/** Personal / public API client (no org header). Typed with the raw contract paths. */
export const api: Client<ApiPaths> = createClient<ApiPaths>({ baseUrl: "", fetch: makeFetch(null) });

const orgClients = new Map<string, Client<OrgPaths>>();

/** Org-bound client: injects `X-Organization-ID: orgId` on every tenant call. Cached per org. */
export function createOrgClient(orgId: string): Client<OrgPaths> {
  let c = orgClients.get(orgId);
  if (!c) {
    c = createClient<OrgPaths>({ baseUrl: "", fetch: makeFetch(orgId) });
    orgClients.set(orgId, c);
  }
  return c;
}

export type OrgClient = Client<OrgPaths>;

type ApiResult<T> = { data?: T; error?: unknown; response: Response };

/**
 * Await an openapi-fetch call and return `data`, throwing a typed `ApiError` on failure.
 *   const ledgers = await unwrap(orgApi.GET("/api/v1/accounts/ledgers", { params: { query } }));
 */
export async function unwrap<T>(call: Promise<ApiResult<T>>): Promise<T> {
  let result: ApiResult<T>;
  try {
    result = await call;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, "NETWORK_ERROR", e instanceof Error ? e.message : "Network error");
  }
  if (result.error !== undefined || !result.response.ok) throw toApiError(result.response.status, result.error);
  return result.data as T;
}

/** Header object for idempotent POST/PUT — generate once per user submission and reuse on retry. */
export function idempotencyHeader(key: string = crypto.randomUUID()): { "Idempotency-Key": string } {
  return { "Idempotency-Key": key };
}
