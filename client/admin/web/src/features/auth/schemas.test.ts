import { describe, expect, it } from "vitest";
import { codeSchema, otpSecretFromUri, passwordChangeSchema } from "./schemas";

describe("auth schemas", () => {
  it("parses otpauth secret", () => {
    expect(otpSecretFromUri("otpauth://totp/InaiFlow:a@b.c?secret=JBSWY3DPEHPK3PXP&issuer=InaiFlow")).toBe("JBSWY3DPEHPK3PXP");
    expect(otpSecretFromUri("nope")).toBeNull();
  });
  it("validates code and password", () => {
    expect(codeSchema.safeParse("123456").success).toBe(true);
    expect(codeSchema.safeParse("12345").success).toBe(false);
    expect(passwordChangeSchema.safeParse({ new_password: "short", confirm: "short" }).success).toBe(false);
    expect(passwordChangeSchema.safeParse({ new_password: "long-enough-pw", confirm: "long-enough-pw" }).success).toBe(true);
  });
});
