"""OpenAPI modeli postojecih preview/apply odgovora Excel importa."""

from typing import Literal

from pydantic import BaseModel


class ImportIssueResponse(BaseModel):
    sheet: str
    row: int | None
    code: str
    message: str
    severity: Literal["error", "warning"]


class ImportSampleResponse(BaseModel):
    sheet: str
    row: int
    card_code: str
    printing_id: int
    quantity_in_file: int
    before_quantity: int | None
    after_quantity: int
    action: Literal["create", "update", "unchanged", "skip_zero"]


class CollectionImportPreviewResponse(BaseModel):
    mode: Literal["replace", "add"]
    can_apply: bool
    file_sha256: str
    plan_token: str
    sheets_read: int
    rows_with_quantity: int
    blank_rows_skipped: int
    matched: int
    create: int
    update: int
    unchanged: int
    skip_zero: int
    error_count: int
    warning_count: int
    issues: list[ImportIssueResponse]
    issues_truncated: bool
    samples: list[ImportSampleResponse]


class CollectionImportApplyResponse(CollectionImportPreviewResponse):
    status: Literal["applied"]
