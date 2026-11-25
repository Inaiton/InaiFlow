import { describe, expect, it } from "vitest";
import { parseImpersonationHash } from "./impersonation";

const enc = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "");
const ORG = "11111111-2222-3333-4444-555555555555";

describe("parseImpersonationHash", () => {
  it("reads token and org from the fragment", () => {
    const token = `${enc({ alg: "HS256" })}.${enc({ sub: "x" })}.sig`;
    expect(parseImpersonationHash(`#token=${token}&org_id=${ORG}`)).toEqual({ token, orgId: ORG, slug: null });
  });
  it("falls back to the JWT payload", () => {
    const token = `${enc({ alg: "HS256" })}.${enc({ imp: { org_id: ORG } })}.sig`;
    expect(parseImpersonationHash(`#token=${token}`)?.orgId).toBe(ORG);
  });
  it("rejects junk", () => {
    expect(parseImpersonationHash("#token=abc")).toBeNull();
    expect(parseImpersonationHash("")).toBeNull();
  });
});
