import { z } from "zod";

export const emailField = z.email("Enter a valid email address").trim().toLowerCase();
/** Plan §3.2: 10–128 chars (server also rejects email-equal and common passwords). */
export const passwordField = z.string().min(10, "Use at least 10 characters").max(128, "Use at most 128 characters");
export const codeField = z.string().trim().regex(/^\d{6}$/, "Enter the 6-digit code");

export const loginSchema = z.object({
  email: emailField,
  password: z.string().min(1, "Enter your password"),
  remember: z.boolean(),
});

export const mfaSchema = z.object({
  code: z.string().trim().min(6, "Enter the 6-digit code or a backup code").max(32),
});

export const signupSchema = z
  .object({
    first_name: z.string().trim().min(1, "Enter your first name").max(80),
    last_name: z.string().trim().max(80),
    email: emailField,
    password: passwordField,
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "Passwords don’t match" })
  .refine((v) => v.password.toLowerCase() !== v.email, { path: ["password"], message: "Password can’t be your email" });

export const verifySchema = z.object({ email: emailField, code: codeField });
export const forgotSchema = z.object({ email: emailField });
export const resetSchema = z
  .object({ email: emailField, code: codeField, new_password: passwordField, confirm: z.string() })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Passwords don’t match" });
