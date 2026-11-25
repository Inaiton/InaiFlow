import type { components } from "./schema";

export type ErrorCode = components["schemas"]["ErrorCode"];

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: ErrorCode | "NETWORK_ERROR" | "UNKNOWN",
    message: string,
    public details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function toApiError(status: number, body: unknown): ApiError {
  if (typeof body === "object" && body && "error" in body) {
    const e = (body as components["schemas"]["Error"]).error;
    return new ApiError(status, e.code, e.message, e.details);
  }
  if (typeof body === "object" && body && "detail" in body) {
    return new ApiError(status, "VALIDATION_ERROR", "Validation failed", (body as { detail: unknown }).detail);
  }
  return new ApiError(status, "UNKNOWN", `Request failed (${status})`);
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}
