import { z } from "zod";

export const loginSchema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const codeSchema = z.string().regex(/^\d{6}$/, "Enter the 6-digit code");

export const passwordChangeSchema = z
  .object({
    new_password: z.string().min(10, "At least 10 characters").max(128, "At most 128 characters"),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Passwords do not match" });

/** Extracts the base32 secret from an otpauth:// URI for manual entry. */
export function otpSecretFromUri(uri: string): string | null {
  try {
    return new URL(uri).searchParams.get("secret");
  } catch {
    return null;
  }
}
