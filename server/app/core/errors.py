"""Domain errors + exception handlers producing the contract ``Error`` body.

Services raise ``DomainError`` subclasses (never ``HTTPException``). Every ``ErrorCode`` of the contract
has exactly one subclass here; ``ERROR_CLASSES`` maps code -> class.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("inaiflow.errors")


class DomainError(Exception):
    code: ClassVar[str] = "INTERNAL_ERROR"
    status: ClassVar[int] = 500
    default_message: ClassVar[str] = "Something went wrong"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details
        self.headers = headers
        super().__init__(self.message)

    def body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ValidationFailedError(DomainError):
    code, status, default_message = "VALIDATION_ERROR", 400, "The request is invalid"


class UnauthenticatedError(DomainError):
    code, status, default_message = "UNAUTHENTICATED", 401, "Authentication required"


class TokenExpiredError(DomainError):
    code, status, default_message = "TOKEN_EXPIRED", 401, "The token has expired"


class InvalidCredentialsError(DomainError):
    code, status, default_message = "INVALID_CREDENTIALS", 401, "Invalid email or password"


class EmailNotVerifiedError(DomainError):
    code, status, default_message = "EMAIL_NOT_VERIFIED", 403, "Email address is not verified"


class MfaRequiredError(DomainError):
    code, status, default_message = "MFA_REQUIRED", 403, "Two-factor authentication is required"


class MfaInvalidError(DomainError):
    code, status, default_message = "MFA_INVALID", 401, "Invalid two-factor code"


class MfaSetupRequiredError(DomainError):
    code, status, default_message = "MFA_SETUP_REQUIRED", 403, "Two-factor setup is required"


class AccountSuspendedError(DomainError):
    code, status, default_message = "ACCOUNT_SUSPENDED", 403, "This account is suspended"


class RateLimitedError(DomainError):
    code, status, default_message = "RATE_LIMITED", 429, "Too many attempts, try again later"


class ForbiddenError(DomainError):
    code, status, default_message = "FORBIDDEN", 403, "You are not allowed to do this"


class PermissionDeniedError(DomainError):
    code, status, default_message = "PERMISSION_DENIED", 403, "Your role does not allow this action"


InsufficientPermissionError = PermissionDeniedError


class OrgSuspendedError(DomainError):
    code, status, default_message = "ORG_SUSPENDED", 403, "This organization is suspended"


class MembershipExpiredError(DomainError):
    code, status, default_message = "MEMBERSHIP_EXPIRED", 403, "Your access to this organization has expired"


class NotFoundError(DomainError):
    code, status, default_message = "NOT_FOUND", 404, "Not found"


class ConflictError(DomainError):
    code, status, default_message = "CONFLICT", 409, "The request conflicts with the current state"


class AlreadyExistsError(DomainError):
    code, status, default_message = "ALREADY_EXISTS", 409, "It already exists"


class InvalidStateError(DomainError):
    code, status, default_message = "INVALID_STATE", 409, "Not allowed in the current state"


class DoubleEntryImbalanceError(DomainError):
    code, status, default_message = "DOUBLE_ENTRY_IMBALANCE", 400, "Total debit must equal total credit"


class PeriodLockedError(DomainError):
    code, status, default_message = "PERIOD_LOCKED", 423, "The books are locked for this period"


class LedgerInUseError(DomainError):
    code, status, default_message = "LEDGER_IN_USE", 409, "The ledger has transactions"


class SystemRecordError(DomainError):
    code, status, default_message = "SYSTEM_RECORD", 409, "System records cannot be changed"


class StepLockedError(DomainError):
    code, status, default_message = "STEP_LOCKED", 423, "This step is signed off and locked"


class StepNotActiveError(DomainError):
    code, status, default_message = "STEP_NOT_ACTIVE", 409, "This step is not active"


class QtyMismatchError(DomainError):
    code, status, default_message = "QTY_MISMATCH", 400, "Quantities do not add up"


class InstrumentExpiredError(DomainError):
    code, status, default_message = "INSTRUMENT_EXPIRED", 423, "The instrument's calibration has expired"


class WorkflowInvalidError(DomainError):
    code, status, default_message = "WORKFLOW_INVALID", 400, "The workflow graph is invalid"


class WorkflowPublishedError(DomainError):
    code, status, default_message = "WORKFLOW_PUBLISHED", 409, "Published workflows cannot be edited"


class FolderLockedError(DomainError):
    code, status, default_message = "FOLDER_LOCKED", 409, "System folders cannot be changed"


class FolderNotEmptyError(DomainError):
    code, status, default_message = "FOLDER_NOT_EMPTY", 409, "The folder is not empty"


class DocumentLockedError(DomainError):
    code, status, default_message = "DOCUMENT_LOCKED", 409, "This document is locked"


class SegregationOfDutiesError(DomainError):
    code, status, default_message = "SEGREGATION_OF_DUTIES", 403, "The same person cannot perform both steps"


class UploadIncompleteError(DomainError):
    code, status, default_message = "UPLOAD_INCOMPLETE", 409, "The file upload is not complete"


class FileTooLargeError(DomainError):
    code, status, default_message = "FILE_TOO_LARGE", 413, "The file is too large"


class UnsupportedMediaError(DomainError):
    code, status, default_message = "UNSUPPORTED_MEDIA", 415, "This file type is not allowed"


class PayrollNotReadyError(DomainError):
    code, status, default_message = "PAYROLL_NOT_READY", 409, "Payroll is not ready to lock"


class IpNotAllowedError(DomainError):
    code, status, default_message = "IP_NOT_ALLOWED", 403, "Access from this network is not allowed"


class IdempotencyConflictError(DomainError):
    code, status, default_message = (
        "IDEMPOTENCY_CONFLICT",
        409,
        "Idempotency-Key was reused with a different request",
    )


class QuotaExceededError(DomainError):
    code, status, default_message = "QUOTA_EXCEEDED", 403, "Your plan limit has been reached"


class InternalError(DomainError):
    code, status, default_message = "INTERNAL_ERROR", 500, "Something went wrong"


ERROR_CLASSES: dict[str, type[DomainError]] = {
    cls.code: cls for cls in DomainError.__subclasses__() if cls is not DomainError
}

_HTTP_CODE = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "NOT_FOUND",
    409: "CONFLICT",
    413: "FILE_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA",
    422: "VALIDATION_ERROR",
    423: "INVALID_STATE",
    429: "RATE_LIMITED",
}

DOUBLE_ENTRY_MARKER = "Double-entry imbalance"


def error_response(
    status: int, code: str, message: str, details: Any = None, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
        headers=headers,
    )


def translate_db_error(exc: DBAPIError) -> DomainError:
    """Map a database error to a DomainError (used by handlers and by services that catch)."""
    text = str(getattr(exc, "orig", exc))
    if DOUBLE_ENTRY_MARKER in text:
        return DoubleEntryImbalanceError()
    if isinstance(exc, IntegrityError):
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(
            getattr(exc, "orig", None), "pgcode", None
        )
        if sqlstate == "23505":
            return AlreadyExistsError("A record with the same unique value already exists")
        if sqlstate == "23503":
            return ConflictError("The record references or is referenced by other records")
        return ConflictError("The change violates a data integrity rule")
    if "row-level security" in text:
        return NotFoundError()
    return InternalError()


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()
        ]
        return error_response(422, "VALIDATION_ERROR", "Request validation failed", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODE.get(exc.status_code, "INTERNAL_ERROR" if exc.status_code >= 500 else "VALIDATION_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return error_response(exc.status_code, code, message, None, getattr(exc, "headers", None))

    @app.exception_handler(DBAPIError)
    async def _db(_: Request, exc: DBAPIError) -> JSONResponse:
        err = translate_db_error(exc)
        if isinstance(err, InternalError):
            log.exception("database error", exc_info=exc)
        return error_response(err.status, err.code, err.message, err.details)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=exc)
        return error_response(500, "INTERNAL_ERROR", "Something went wrong", None)
