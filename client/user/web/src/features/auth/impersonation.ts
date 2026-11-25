/**
 * Parse the impersonation launch fragment: `#token=<jwt>&org_id=<uuid>` (also accepts `org`, `slug`).
 * The org id falls back to the JWT payload (`org_id` or `imp.org_id`) — decoded only to route, never trusted
 * for authorization (the server verifies the token).
 */
export interface ImpersonationLaunch {
  token: string;
  orgId: string | null;
  slug: string | null;
}

function b64urlJson(part: string): unknown {
  try {
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "=");
    return JSON.parse(atob(b64));
  } catch {
    return null;
  }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseImpersonationHash(hash: string): ImpersonationLaunch | null {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const token = params.get("token");
  if (!token || token.split(".").length !== 3) return null;
  let orgId = params.get("org_id") ?? params.get("org");
  if (!orgId) {
    const payload = b64urlJson(token.split(".")[1] ?? "") as { org_id?: unknown; imp?: { org_id?: unknown } } | null;
    const fromJwt = payload?.org_id ?? payload?.imp?.org_id;
    orgId = typeof fromJwt === "string" ? fromJwt : null;
  }
  return { token, orgId: orgId && UUID.test(orgId) ? orgId : null, slug: params.get("slug") };
}
