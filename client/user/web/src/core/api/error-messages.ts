import { ApiError, type AnyErrorCode } from "./errors";

/** Friendly, calm copy for toasts. Server `message` is used when no mapping exists. */
const MESSAGES: Partial<Record<AnyErrorCode, string>> = {
  NETWORK_ERROR: "Can’t reach InaiFlow. Check your connection and try again.",
  UNAUTHENTICATED: "Your session has ended. Please sign in again.",
  TOKEN_EXPIRED: "Your session has ended. Please sign in again.",
  INVALID_CREDENTIALS: "That email and password don’t match.",
  EMAIL_NOT_VERIFIED: "Verify your email first — we’ve sent you a code.",
  MFA_REQUIRED: "Two-factor sign-in is required for this action.",
  MFA_INVALID: "That code didn’t work. Try the latest code from your app.",
  ACCOUNT_SUSPENDED: "This account is suspended. Contact support.",
  RATE_LIMITED: "Too many attempts. Please wait a few minutes and try again.",
  FORBIDDEN: "You don’t have access to this.",
  PERMISSION_DENIED: "Your role doesn’t allow this action.",
  ORG_SUSPENDED: "This organization is suspended. Contact its owner.",
  MEMBERSHIP_EXPIRED: "Your access to this organization has expired.",
  NOT_FOUND: "We couldn’t find that. It may have been removed.",
  CONFLICT: "This changed elsewhere. Refresh and try again.",
  ALREADY_EXISTS: "That already exists.",
  INVALID_STATE: "This action isn’t available in the current state.",
  DOUBLE_ENTRY_IMBALANCE: "Debit and credit totals must match.",
  PERIOD_LOCKED: "Books are locked for this period.",
  LEDGER_IN_USE: "This ledger has entries and can’t be removed.",
  SYSTEM_RECORD: "System records can’t be changed or deleted.",
  STEP_LOCKED: "This step is signed off and locked.",
  STEP_NOT_ACTIVE: "This step isn’t active yet.",
  QTY_MISMATCH: "Accepted + rejected + rework must equal the input quantity.",
  INSTRUMENT_EXPIRED: "The measuring instrument’s calibration has expired.",
  WORKFLOW_INVALID: "The workflow has errors. Fix them before publishing.",
  WORKFLOW_PUBLISHED: "Published versions can’t be edited — create a new version.",
  FOLDER_LOCKED: "System folders can’t be renamed, moved or deleted.",
  FOLDER_NOT_EMPTY: "The folder isn’t empty.",
  DOCUMENT_LOCKED: "This document is locked.",
  SEGREGATION_OF_DUTIES: "The preparer can’t review or approve their own document.",
  UPLOAD_INCOMPLETE: "The upload didn’t finish. Try again.",
  FILE_TOO_LARGE: "That file is too large (max 50 MB).",
  UNSUPPORTED_MEDIA: "That file type isn’t supported.",
  PAYROLL_NOT_READY: "Finalize attendance for every employee first.",
  IP_NOT_ALLOWED: "Sign-in isn’t allowed from this network.",
  IDEMPOTENCY_CONFLICT: "This request was already submitted.",
  QUOTA_EXCEEDED: "Your plan limit is reached. Upgrade to continue.",
  INTERNAL_ERROR: "Something went wrong on our side. Please try again.",
};

export function errorMessage(code: AnyErrorCode, fallback?: string): string {
  return MESSAGES[code] ?? fallback ?? "Something went wrong. Please try again.";
}

/** Message for any thrown value — prefers the mapped copy, then the server message. */
export function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "VALIDATION_ERROR" || err.code === "UNKNOWN") return err.message || errorMessage(err.code);
    return errorMessage(err.code, err.message);
  }
  if (err instanceof Error && err.message) return err.message;
  return errorMessage("UNKNOWN");
}
