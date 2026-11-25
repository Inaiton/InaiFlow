import type { ErrorCode } from "./types";

const KNOWN_CODES = new Set<string>([
  "VALIDATION_ERROR", "UNAUTHENTICATED", "TOKEN_EXPIRED", "INVALID_CREDENTIALS", "EMAIL_NOT_VERIFIED",
  "MFA_REQUIRED", "MFA_INVALID", "MFA_SETUP_REQUIRED", "ACCOUNT_SUSPENDED", "RATE_LIMITED", "FORBIDDEN",
  "PERMISSION_DENIED", "ORG_SUSPENDED", "MEMBERSHIP_EXPIRED", "NOT_FOUND", "CONFLICT", "ALREADY_EXISTS",
  "INVALID_STATE", "DOUBLE_ENTRY_IMBALANCE", "PERIOD_LOCKED", "LEDGER_IN_USE", "SYSTEM_RECORD", "STEP_LOCKED",
  "STEP_NOT_ACTIVE", "QTY_MISMATCH", "INSTRUMENT_EXPIRED", "WORKFLOW_INVALID", "WORKFLOW_PUBLISHED",
  "FOLDER_LOCKED", "FOLDER_NOT_EMPTY", "DOCUMENT_LOCKED", "SEGREGATION_OF_DUTIES", "UPLOAD_INCOMPLETE",
  "FILE_TOO_LARGE", "UNSUPPORTED_MEDIA", "PAYROLL_NOT_READY", "IP_NOT_ALLOWED", "IDEMPOTENCY_CONFLICT",
  "QUOTA_EXCEEDED", "INTERNAL_ERROR",
]);

/** Client-only codes for failures that never reached the contract error body. */
export type ClientErrorCode = "NETWORK_ERROR" | "UNKNOWN";
export type AnyErrorCode = ErrorCode | ClientErrorCode;

export type FieldErrors = Record<string, string>;

/** Typed error for every failed API call (body = contract `Error`). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: AnyErrorCode;
  readonly details: unknown;

  constructor(status: number, code: AnyErrorCode, message: string, details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  is(...codes: AnyErrorCode[]): boolean {
    return codes.includes(this.code);
  }

  /** Field-level messages from `details` (`{fields:{name:msg}}`, `{name:msg}` or FastAPI `[{loc,msg}]`). */
  get fieldErrors(): FieldErrors {
    return extractFieldErrors(this.details);
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function extractFieldErrors(details: unknown): FieldErrors {
  const out: FieldErrors = {};
  const fromList = (list: unknown[]) => {
    for (const item of list) {
      if (!isRecord(item)) continue;
      const loc = Array.isArray(item.loc) ? item.loc.filter((p) => p !== "body").join(".") : item.field;
      const msg = item.msg ?? item.message;
      if (typeof loc === "string" && loc && typeof msg === "string") out[loc] = msg;
    }
  };
  if (Array.isArray(details)) fromList(details);
  else if (isRecord(details)) {
    const fields = details.fields ?? details.errors;
    if (Array.isArray(fields)) fromList(fields);
    else if (isRecord(fields)) {
      for (const [k, v] of Object.entries(fields)) if (typeof v === "string") out[k] = v;
    }
  }
  return out;
}

function codeForStatus(status: number): AnyErrorCode {
  if (status === 401) return "UNAUTHENTICATED";
  if (status === 403) return "FORBIDDEN";
  if (status === 404) return "NOT_FOUND";
  if (status === 409) return "CONFLICT";
  if (status === 413) return "FILE_TOO_LARGE";
  if (status === 422 || status === 400) return "VALIDATION_ERROR";
  if (status === 429) return "RATE_LIMITED";
  if (status >= 500) return "INTERNAL_ERROR";
  return "UNKNOWN";
}

/** Build an ApiError from any parsed response body (contract Error, FastAPI `{detail}`, or junk). */
export function toApiError(status: number, body: unknown): ApiError {
  if (isRecord(body) && isRecord(body.error)) {
    const e = body.error;
    const code = typeof e.code === "string" && KNOWN_CODES.has(e.code) ? (e.code as ErrorCode) : codeForStatus(status);
    const message = typeof e.message === "string" ? e.message : "Request failed";
    return new ApiError(status, code, message, e.details ?? null);
  }
  if (isRecord(body) && "detail" in body) {
    const detail = body.detail;
    const message = typeof detail === "string" ? detail : "Some fields are invalid";
    return new ApiError(status, codeForStatus(status), message, Array.isArray(detail) ? detail : null);
  }
  return new ApiError(status, codeForStatus(status), status ? `Request failed (${status})` : "Network error");
}

export const isApiError = (e: unknown): e is ApiError => e instanceof ApiError;
