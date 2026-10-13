from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel


class EvidenceStatus(str, Enum):
    supported = "supported"
    conflicting = "conflicting"
    insufficient = "insufficient"


class UploadResponse(BaseModel):
    document_id: str
    session_id: str


class AnalyzeRequest(BaseModel):
    document_id: str
    discussion_point: str


class Finding(BaseModel):
    verbatim_passage: str
    passage_position: Optional[str] = None
    issue_question: str
    evidence_status: EvidenceStatus
    suggested_question: Optional[str] = None
    draft_label: str = "draft — review required"


class AnalyzeResponse(Finding):
    mode: Literal["llm_grounded", "retrieval_only"] = "llm_grounded"


class SessionFindings(BaseModel):
    session_id: str
    findings: list[Finding]
