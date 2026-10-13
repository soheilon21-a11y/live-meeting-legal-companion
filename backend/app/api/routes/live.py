import uuid
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.api.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Finding,
    SessionFindings,
    UploadResponse,
)
from app.services import analysis, ingest, session_store

router = APIRouter(prefix="/api/live", tags=["live"])


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_pdf(session_id: str, filename: str, findings: list[dict]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Niyosh — Live Analysis Findings", styles["Title"]),
        Spacer(1, 0.4 * cm),
        Paragraph(f"Session: {_esc(session_id)}", styles["Normal"]),
        Paragraph(f"Document: {_esc(filename)}", styles["Normal"]),
        Paragraph("Draft — review required. Not legal advice.", styles["Italic"]),
        Spacer(1, 0.6 * cm),
    ]
    if not findings:
        story.append(Paragraph("No findings.", styles["Normal"]))
    for i, finding in enumerate(findings, 1):
        story.append(Paragraph(f"Finding {i}", styles["Heading2"]))
        story.append(Paragraph(f"Issue: {_esc(finding.get('issue_question') or '—')}", styles["Normal"]))
        story.append(Paragraph(f"Evidence: {_esc(finding.get('evidence_status') or '')}", styles["Normal"]))
        passage = finding.get("verbatim_passage") or ""
        if passage:
            story.append(Paragraph(f"Passage ({_esc(finding.get('passage_position') or '')}):", styles["Normal"]))
            story.append(Paragraph(f"“{_esc(passage)}”", styles["Italic"]))
        suggested = finding.get("suggested_question") or ""
        if suggested:
            story.append(Paragraph(f"Suggested question: {_esc(suggested)}", styles["Normal"]))
        story.append(Spacer(1, 0.4 * cm))
    doc.build(story)
    return buf.getvalue()


@router.post("/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...)) -> UploadResponse:
    filename = file.filename or "document"
    content = file.file.read()
    doc_id = uuid.uuid4().hex
    try:
        ingest.ingest(doc_id, filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    session_store.create_session(doc_id, filename)
    return UploadResponse(document_id=doc_id, session_id=doc_id)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    session = session_store.load_session(req.document_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown document")
    finding_data, mode = analysis.analyze(req.document_id, req.discussion_point)
    finding = Finding(**finding_data)
    session_store.add_finding(session["session_id"], finding.model_dump())
    return AnalyzeResponse(**finding.model_dump(), mode=mode)


@router.get("/session/{session_id}/findings", response_model=SessionFindings)
def get_findings(session_id: str) -> SessionFindings:
    session = session_store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    findings = [Finding(**f) for f in session["findings"]]
    return SessionFindings(session_id=session_id, findings=findings)


@router.post("/session/{session_id}/export")
def export(session_id: str) -> Response:
    session = session_store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    pdf_bytes = _build_pdf(session_id, session.get("filename", ""), session["findings"])
    headers = {"Content-Disposition": f'attachment; filename="niyosh-findings-{session_id[:8]}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.delete("/session/{session_id}")
def delete(session_id: str) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    session_store.delete_session(session_id)
    return {"deleted": True, "session_id": session_id}
