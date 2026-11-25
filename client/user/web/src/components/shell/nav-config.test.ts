import { describe, expect, it } from "vitest";
import { activeNav } from "./nav-config";

describe("activeNav", () => {
  it("matches the longest prefix", () => {
    expect(activeNav("/accounts")).toEqual({ module: "accounts", item: "gateway" });
    expect(activeNav("/accounts/vouchers/new")).toEqual({ module: "accounts", item: "vouchers" });
    expect(activeNav("/organization/acl")).toEqual({ module: "organization", item: "roles" });
    expect(activeNav("/documents/scan")).toEqual({ module: "documents", item: "scan" });
    expect(activeNav("")).toEqual({ module: null, item: null });
  });
});
