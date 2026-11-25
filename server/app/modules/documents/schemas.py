"""Documents contract models (names match docs/api/contract.api exactly)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from app.core.schemas import InModel, OutModel, UploadRequest, UploadTicket

ApprovalStatus = Literal["DRAFT", "UNDER_REVIEW", "APPROVED", "OBSOLETE"]


class FolderOut(OutModel):
    id: uuid.UUID
    parent_folder_id: uuid.UUID | None
    name: str
    system_kind: str | None
    fy_label: str | None
    month_date: date | None
    is_system_locked: bool
    linked_period_run_id: uuid.UUID | None
    child_count: int
    document_count: int
    created_at: datetime


class FolderIn(InModel):
    parent_folder_id: uuid.UUID
    name: str


class FolderUpdateIn(InModel):
    name: str | None = None
    parent_folder_id: uuid.UUID | None = None


class EnsureMonthIn(InModel):
    month: date


class ReportBlock(InModel):
    id: str
    type: str
    data: Any


class ReportContent(InModel):
    blocks: list[ReportBlock]


class DocumentSummary(OutModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    title: str
    source_type: str
    file_name: str | None
    file_mime_type: str | None
    file_size: int | None
    upload_status: str
    iso_doc_number: str | None
    revision_no: int
    approval_status: ApprovalStatus
    linked_voucher_id: uuid.UUID | None
    linked_period_run_id: uuid.UUID | None
    linked_step_id: uuid.UUID | None
    linked_stock_item_id: uuid.UUID | None
    prepared_by_name: str
    created_at: datetime
    updated_at: datetime


class DocumentOut(DocumentSummary):
    rich_content: Any | None
    template_id: uuid.UUID | None
    ocr_text: str | None
    reviewed_by_name: str | None
    review_comment: str | None
    approved_by_name: str | None
    approved_at: datetime | None
    previous_revision_id: uuid.UUID | None
    folder_path: list[str]
    can_delete: bool


class DocUploadIn(InModel):
    folder_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str
    size_bytes: int
    source_type: str | None = None
    iso_doc_number: str | None = None
    linked_voucher_id: uuid.UUID | None = None
    linked_period_run_id: uuid.UUID | None = None
    linked_step_id: uuid.UUID | None = None
    linked_stock_item_id: uuid.UUID | None = None


class DocUploadOut(OutModel):
    document: DocumentOut
    upload: UploadTicket


class CompleteUploadIn(InModel):
    checksum_sha256: str | None = None
    ocr_text: str | None = None


class RenderContext(InModel):
    stock_item_id: uuid.UUID | None = None
    period_run_id: uuid.UUID | None = None
    step_id: uuid.UUID | None = None
    voucher_id: uuid.UUID | None = None


class DocCreateIn(InModel):
    folder_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    source_type: str
    template_id: uuid.UUID | None = None
    rich_content: ReportContent | None = None
    context: RenderContext | None = None
    iso_doc_number: str | None = None
    linked_period_run_id: uuid.UUID | None = None
    linked_step_id: uuid.UUID | None = None
    linked_stock_item_id: uuid.UUID | None = None
    linked_voucher_id: uuid.UUID | None = None


class DocUpdateIn(InModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    rich_content: ReportContent | None = None
    folder_id: uuid.UUID | None = None
    iso_doc_number: str | None = None


class TransitionIn(InModel):
    to: ApprovalStatus
    comment: str | None = None


class ReviewIn(InModel):
    comment: str | None = None


class ReviseIn(InModel):
    file: UploadRequest | None = None


class ReviseOut(OutModel):
    document: DocumentOut
    upload: UploadTicket | None


class TemplateOut(OutModel):
    id: uuid.UUID
    template_type: str
    name: str
    description: str | None
    is_system_default: bool
    content_schema: Any
    created_by_name: str | None
    created_at: datetime


class TemplateIn(InModel):
    template_type: str
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    content_schema: Any


class TemplateUpdateIn(InModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    content_schema: Any | None = None


class TemplateTokenOut(OutModel):
    token: str
    label: str
    group: str
    sample: str


class PreviewIn(InModel):
    context: RenderContext


class PreviewOut(OutModel):
    rich_content: Any
    warnings: list[str]


class SearchHit(OutModel):
    document: DocumentSummary
    snippet: str | None
    folder_path: list[str]
