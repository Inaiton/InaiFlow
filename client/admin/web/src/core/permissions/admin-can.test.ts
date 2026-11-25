import { describe, expect, it } from "vitest";
import { adminCan } from "./admin-can";

describe("adminCan", () => {
  it("allows ANY endpoints for every role", () => {
    expect(adminCan("BILLING_ADMIN", "GET /admin/dashboard")).toBe(true);
  });
  it("mirrors contract role lists", () => {
    expect(adminCan("SUPERADMIN", "GET /admin/admins")).toBe(true);
    expect(adminCan("SUPPORT_ADMIN", "GET /admin/admins")).toBe(false);
    expect(adminCan("BILLING_ADMIN", "PATCH /admin/organizations/{org_id}/plan")).toBe(true);
    expect(adminCan("SUPPORT_ADMIN", "PATCH /admin/organizations/{org_id}/plan")).toBe(false);
    expect(adminCan("BILLING_ADMIN", "GET /admin/users")).toBe(false);
  });
  it("applies refinements", () => {
    expect(adminCan("SUPPORT_ADMIN", "org.lifecycle.SUSPEND")).toBe(true);
    expect(adminCan("SUPPORT_ADMIN", "org.lifecycle.ARCHIVE")).toBe(false);
    expect(adminCan("SUPERADMIN", "org.lifecycle.ARCHIVE")).toBe(true);
    expect(adminCan("BILLING_ADMIN", "org.lifecycle.ACTIVATE")).toBe(false);
  });
  it("denies without a role", () => {
    expect(adminCan(null, "GET /admin/dashboard")).toBe(false);
  });
});
