import { describe, expect, it } from "vitest";
import { safeNext } from "./RequireAuth";

describe("safeNext", () => {
  it("blocks open redirects", () => {
    expect(safeNext("/o/acme/accounts")).toBe("/o/acme/accounts");
    expect(safeNext("https://evil.example")).toBe("/");
    expect(safeNext("//evil.example")).toBe("/");
    expect(safeNext("/\\evil")).toBe("/");
    expect(safeNext(null, "/me")).toBe("/me");
  });
});
