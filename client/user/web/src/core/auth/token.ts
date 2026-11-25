import { z } from "zod";

/**
 * Auth token payload (`TokenOut`). Validated at runtime before it is kept in memory — a malformed
 * login/refresh response must never install a bogus token. (The old TokenOut name collision is fixed.)
 */
const accessTokenSchema = z.object({
  access_token: z.string().min(10),
  token_type: z.string(),
  expires_in: z.number(),
});

export type AccessToken = z.infer<typeof accessTokenSchema>;

export function readAccessToken(value: unknown): AccessToken {
  const parsed = accessTokenSchema.safeParse(value);
  if (!parsed.success) throw new Error("Malformed token response");
  return parsed.data;
}
