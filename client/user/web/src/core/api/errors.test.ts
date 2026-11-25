import { describe, expect, it } from "vitest";
import { describeError, errorMessage } from "./error-messages";
import { ApiError, toApiError } from "./errors";

describe("api error mapping", () => {
  it("parses the contract error body", () => {
    const e = toApiError(409, { error: { code: "PERIOD_LOCKED", message: "Locked till 31 Oct", details: null } });
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("PERIOD_LOCKED");
    expect(e.status).toBe(409);
    expect(describeError(e)).toBe("Books are locked for this period.");
  });
  it("falls back to status codes", () => {
    expect(toApiError(404, null).code).toBe("NOT_FOUND");
    expect(toApiError(503, "x").code).toBe("INTERNAL_ERROR");
    expect(toApiError(418, { error: { code: "WAT", message: "m", details: null } }).code).toBe("UNKNOWN");
  });
  it("extracts field errors", () => {
    const fastapi = toApiError(422, { detail: [{ loc: ["body", "email"], msg: "invalid email" }] });
    expect(fastapi.fieldErrors).toEqual({ email: "invalid email" });
    const contract = toApiError(400, { error: { code: "VALIDATION_ERROR", message: "Bad", details: { fields: { gstin: "Invalid GSTIN" } } } });
    expect(contract.fieldErrors).toEqual({ gstin: "Invalid GSTIN" });
    expect(describeError(contract)).toBe("Bad");
  });
  it("maps codes to copy", () => {
    expect(errorMessage("RATE_LIMITED")).toMatch(/Too many/);
    expect(errorMessage("UNKNOWN", "fallback")).toBe("fallback");
  });
});
