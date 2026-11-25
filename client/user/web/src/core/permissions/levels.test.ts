import { describe, expect, it } from "vitest";
import { hasLevel, resolveLevel } from "./levels";

const ctx = {
  is_owner: false,
  permissions: { "accounts.vouchers": "WRITE", "accounts.reports": "READ", "operations.items": "NONE" } as const,
};

describe("permission resolution", () => {
  it("orders levels", () => {
    expect(hasLevel("FULL", "WRITE")).toBe(true);
    expect(hasLevel("READ", "WRITE")).toBe(false);
    expect(hasLevel(undefined, "READ")).toBe(false);
    expect(hasLevel("NONE", "NONE")).toBe(true);
  });
  it("resolves keys with NONE default", () => {
    expect(resolveLevel(ctx, "accounts.vouchers")).toBe("WRITE");
    expect(resolveLevel(ctx, "documents.explorer")).toBe("NONE");
    expect(resolveLevel(null, "accounts.vouchers")).toBe("NONE");
  });
  it("owner is always FULL", () => {
    expect(resolveLevel({ ...ctx, is_owner: true }, "organization.billing")).toBe("FULL");
  });
  it("module wildcard takes the max", () => {
    expect(resolveLevel(ctx, "accounts.*")).toBe("WRITE");
    expect(resolveLevel(ctx, "operations.*")).toBe("NONE");
  });
});
