from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

FIELDS = ["Bid Number", "Title", "Due Date", "Bid Submission Type", "Term of Bid",
          "Pre Bid Meeting", "Installation", "Bid Bond Requirement", "Delivery Date",
          "Payment Terms", "Any Additional Documentation Required", "MFG for Registration",
          "Contract or Cooperative to use", "Model_no", "Part_no", "Product", "contact_info",
          "company_name", "Bid Summary", "Product Specification"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    id: str
    bid_id: str
    file: str
    doc_type: str
    page: int | None = None
    locator: str = ""
    addendum_number: int | None = None
    document_date: str | None = None
    heading: str = ""
    text: str
    raw_text: str
    score: float = 0

    def prompt_data(self):
        # Raw page text is retained for audit, never sent as hidden extra prompt context.
        return self.model_dump(exclude={"raw_text", "score"})


class SearchRequest(StrictModel):
    query: str = Field(min_length=1)
    bid_ids: list[str] = Field(default_factory=list)
    doc_types: list[str] = Field(default_factory=list)
    addendum_numbers: list[int] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=50)
    mode: Literal["dense", "hybrid", "rerank"] = "hybrid"


class Citation(StrictModel):
    chunk_id: str
    file: str
    page: int | None
    locator: str = ""
    quote: str = Field(min_length=1)


class FieldValue(StrictModel):
    value: Any = None
    sources: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    notes: str = "Not found in documents"


class Extraction(StrictModel):
    fields: dict[str, FieldValue]


class ChangeRecord(StrictModel):
    field: str
    old_value: Any
    new_value: Any
    sources: list[Citation]
    reason: str


class Reconciliation(StrictModel):
    fields: dict[str, FieldValue]
    changes: list[ChangeRecord] = Field(default_factory=list)


class ValidationIssue(StrictModel):
    field: str
    reason: str


class Critique(StrictModel):
    issues: list[ValidationIssue] = Field(default_factory=list)


class Answer(StrictModel):
    answer: str
    sources: list[Citation] = Field(default_factory=list)
    notes: str = ""


class RunState(StrictModel):
    run_id: str
    mode: str
    bid_ids: list[str]
    plan: list[str] = Field(default_factory=list)
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    draft_fields: dict[str, FieldValue] = Field(default_factory=dict)
    changes: list[ChangeRecord] = Field(default_factory=list)
    validation: list[ValidationIssue] = Field(default_factory=list)
    retries: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    final_output: dict = Field(default_factory=dict)
