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
    transcript_excerpt: Optional[str] = None


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


class Observation(BaseModel):
    obs_id: str
    timestamp: str
    issue_question: str
    evidence_status: EvidenceStatus
    suggested_question: Optional[str] = None
    transcript_excerpt: str
    dismissed: bool = False


class ObservationsResponse(BaseModel):
    session_id: str
    observations: list[Observation]
    all: list[Observation]
    last_index: int


class ConsentRequest(BaseModel):
    session_id: str
    country: str
    participants: list[str]
    consent_given: bool


class ConsentResponse(BaseModel):
    session_id: str
    consents: list[dict]


class TranscribeResponse(BaseModel):
    text: str
    language: str


class DictationResponse(BaseModel):
    text: str
    language: str


class TranscriptResponse(BaseModel):
    session_id: str
    transcript: list[dict]


class DiarizeRequest(BaseModel):
    expected_speakers: Optional[int] = None


class CorrectSpeakerRequest(BaseModel):
    chunk_index: int
    speaker: str


class CaptureRequest(BaseModel):
    capture_disabled: bool


class TTSRequest(BaseModel):
    text: str
    lang: str = "en"
