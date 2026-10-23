import uuid
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.api.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ConsentRequest,
    ConsentResponse,
    CorrectSpeakerRequest,
    DictationResponse,
    DiarizeRequest,
    Finding,
    Observation,
    ObservationsResponse,
    SessionFindings,
    TranscribeResponse,
    TranscriptResponse,
    TTSRequest,
    UploadResponse,
)
from app.core.config import settings
from app.services import (
    analysis,
    consent_store,
    country_check,
    diarization,
    ingest,
    live_worker,
    observation_store,
    observer,
    session_store,
    transcription,
    tts,
)

router = APIRouter(prefix="/api/live", tags=["live"])


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _transcribe_audio(file: UploadFile) -> dict:
    content = file.file.read()
    try:
        with live_worker.model_lock:
            return transcription.transcribe_audio(content)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


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
        if finding.get("source") == "retrieval_only":
            story.append(
                Paragraph(
                    "retrieval-based finding — LLM output unavailable this run",
                    styles["Italic"],
                )
            )
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


@router.post("/session", response_model=UploadResponse)
def create_session() -> UploadResponse:
    session_id = uuid.uuid4().hex
    session_store.create_session(session_id, "")
    return UploadResponse(document_id=session_id, session_id=session_id)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    session = session_store.load_session(req.document_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown document")
    finding_data, mode = analysis.analyze(
        req.document_id, req.discussion_point, req.transcript_excerpt
    )
    finding = Finding(**finding_data)
    stored = {**finding.model_dump(), "source": finding_data.get("source", mode)}
    session_store.add_finding(session["session_id"], stored)
    return AnalyzeResponse(**finding.model_dump(), mode=mode)


@router.get("/country/{code}")
def country(code: str) -> dict:
    rules = country_check.get_country(code)
    return {
        "code": code.strip().upper(),
        "disclaimer": country_check.DISCLAIMER,
        **rules,
    }


@router.post("/consent", response_model=ConsentResponse)
def record_consent(req: ConsentRequest) -> ConsentResponse:
    consent_store.record_consent(
        req.session_id,
        req.country,
        req.participants,
        req.consent_given,
    )
    consents = consent_store.get_consents(req.session_id)
    return ConsentResponse(session_id=req.session_id, consents=consents)


@router.get("/consent/{session_id}", response_model=ConsentResponse)
def get_consents(session_id: str) -> ConsentResponse:
    consents = consent_store.get_consents(session_id)
    return ConsentResponse(session_id=session_id, consents=consents)


@router.post("/transcribe", response_model=TranscribeResponse)
def transcribe(
    session_id: str = Form(...),
    file: UploadFile = File(...),
) -> TranscribeResponse:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if not consent_store.has_consent(session_id):
        raise HTTPException(
            status_code=403,
            detail="Audio capture refused: no recorded consent for this session",
        )
    result = _transcribe_audio(file)
    session_store.append_transcript(
        session_id,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "meeting",
            **result,
        },
    )
    return TranscribeResponse(**result)


@router.post("/session/{session_id}/dictation", response_model=DictationResponse)
def dictation(
    session_id: str,
    file: UploadFile = File(...),
) -> DictationResponse:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    result = _transcribe_audio(file)
    session_store.append_transcript(
        session_id,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "dictation",
            **result,
        },
    )
    return DictationResponse(**result)


@router.get("/session/{session_id}/transcript", response_model=TranscriptResponse)
def get_transcript(session_id: str) -> TranscriptResponse:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    transcript = session_store.get_transcript(session_id)
    return TranscriptResponse(session_id=session_id, transcript=transcript)


@router.post("/session/{session_id}/diarize")
def diarize(session_id: str, body: DiarizeRequest | None = None) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    expected = None
    if body is not None and body.expected_speakers is not None:
        expected = body.expected_speakers
        if not 2 <= expected <= 6:
            raise HTTPException(
                status_code=400, detail="expected_speakers must be between 2 and 6"
            )
    try:
        chunk_speakers = diarization.diarize(session_id, expected)
    except diarization.DiarizationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    session_store.apply_speakers(session_id, chunk_speakers)
    return {
        "session_id": session_id,
        "speakers_detected": len(set(chunk_speakers.values())),
        "transcript": session_store.get_transcript(session_id),
    }


@router.post("/session/{session_id}/correct-speaker")
def correct_speaker(session_id: str, body: CorrectSpeakerRequest) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    speaker = body.speaker.strip()
    if not speaker:
        raise HTTPException(status_code=400, detail="speaker must not be empty")
    updated = session_store.set_speaker(session_id, body.chunk_index, speaker)
    return {
        "session_id": session_id,
        "chunk_index": body.chunk_index,
        "speaker": speaker,
        "updated": updated,
        "transcript": session_store.get_transcript(session_id),
    }


@router.post("/session/{session_id}/chunk")
def upload_chunk(
    session_id: str,
    chunk_index: int = Form(...),
    mode: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if mode == "full" and not consent_store.has_consent(session_id):
        raise HTTPException(
            status_code=403,
            detail="Audio capture refused: no recorded consent",
        )
    if mode not in ("full", "dictation"):
        raise HTTPException(status_code=400, detail="Unknown mode")

    content = file.file.read()
    audio_dir = settings.DATA_DIR / "audio" / session_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / f"chunk_{chunk_index}.webm").write_bytes(content)

    result = live_worker.enqueue_chunk(session_id, chunk_index, content)
    live_worker.mark_recording(session_id, True)
    return {"chunk_index": chunk_index, "status": result}


@router.get("/session/{session_id}/transcript/live")
def live_transcript(session_id: str, since: int = 0) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    entries = [
        entry
        for entry in session_store.get_transcript(session_id)
        if entry.get("chunk_index", 0) > since
    ]
    return {"session_id": session_id, "transcript": entries}


@router.get("/session/{session_id}/status")
def status(session_id: str) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return live_worker.status(session_id)


@router.post("/session/{session_id}/stop")
def stop(session_id: str) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    live_worker.mark_recording(session_id, False)
    flushed = live_worker.flush(session_id)
    return {**live_worker.status(session_id), "flushed": flushed}


@router.get("/session/{session_id}/findings", response_model=SessionFindings)
def get_findings(session_id: str) -> SessionFindings:
    session = session_store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    findings = [Finding(**f) for f in session["findings"]]
    return SessionFindings(session_id=session_id, findings=findings)


@router.get("/session/{session_id}/observations", response_model=ObservationsResponse)
def get_observations(
    session_id: str,
    since: int = 0,
    document_id: str | None = None,
) -> ObservationsResponse:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    doc_id = document_id or session_id
    result = observer.check_recent_transcript(session_id, since, doc_id)
    new_observations = [
        observation_store.add_observation(session_id, obs)
        for obs in result["observations"]
    ]
    all_observations = [
        obs
        for obs in observation_store.get_observations(session_id)
        if not obs.get("dismissed")
    ]
    return ObservationsResponse(
        session_id=session_id,
        observations=[Observation(**o) for o in new_observations],
        all=[Observation(**o) for o in all_observations],
        last_index=result["last_index"],
    )


@router.post("/session/{session_id}/observations/{obs_id}/dismiss")
def dismiss_observation(session_id: str, obs_id: str) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    observation_store.dismiss_observation(session_id, obs_id)
    remaining = [
        obs
        for obs in observation_store.get_observations(session_id)
        if not obs.get("dismissed")
    ]
    return {"session_id": session_id, "observations": remaining}


@router.post("/session/{session_id}/speak")
def speak(session_id: str, body: TTSRequest) -> Response:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=tts.EMPTY_TEXT)
    try:
        audio = tts.speak(text, body.lang)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    headers = {"X-Audio-Truncated": "true"} if len(text) > tts.MAX_CHARS else {}
    return Response(content=audio, media_type="audio/wav", headers=headers)


@router.get("/session/{session_id}/observations/all")
def all_observations(session_id: str) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return {"session_id": session_id, "observations": observation_store.get_observations(session_id)}


@router.get("/session/{session_id}/export")
def export(session_id: str) -> Response:
    session = session_store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    pdf_bytes = _build_pdf(session_id, session.get("filename", ""), session["findings"])
    headers = {
        "Content-Disposition": f'attachment; filename="niyosh-findings-{session_id[:8]}.pdf"',
        "Cache-Control": "no-store",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.delete("/session/{session_id}")
def delete(session_id: str) -> dict:
    if session_store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    session_store.delete_session(session_id)
    return {"deleted": True, "session_id": session_id}
