import json
import re

import httpx

from app.core.config import settings
from app.services import retrieval
from app.services.live_worker import model_lock

VALID_STATUSES = {"supported", "conflicting", "insufficient"}


def _build_prompt(discussion_point: str, passages: list[dict]) -> str:
    lines = [f"[{i}] {p['position']}: {p['text']}" for i, p in enumerate(passages, 1)]
    context = "\n\n".join(lines)
    return (
        "You are a retrieval assistant for a legal meeting. "
        "Do NOT invent content or give legal advice.\n\n"
        f"RETRIEVED PASSAGES (verbatim from the contract):\n{context}\n\n"
        f"DISCUSSION POINT: {discussion_point}\n\n"
        'Respond with ONLY a JSON object (no prose, no markdown) with these keys:\n'
        '- "verbatim_passage": the single most relevant passage copied character-for-character '
        "from the RETRIEVED PASSAGES above (empty string if none is relevant).\n"
        '- "passage_position": the position label of that passage (empty string if none).\n'
        '- "issue_question": the issue stated narrowly as a QUESTION (never a conclusion).\n'
        '- "evidence_status": one of "supported", "conflicting", "insufficient".\n'
        '- "suggested_question": one suggested question the lawyer may raise in the meeting.\n\n'
        "Rules: if no passage is relevant, set evidence_status to \"insufficient\" and say so "
        "plainly; never fabricate a passage or a legal conclusion. Respond in the language of "
        "the discussion point (EN or DE)."
    )


def _call_llm(prompt: str) -> str:
    resp = httpx.post(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        json={"model": settings.MODEL_NAME, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def _parse_response(raw: str) -> dict:
    raw = raw.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def analyze(
    document_id: str,
    discussion_point: str,
    transcript_excerpt: str | None = None,
) -> tuple[dict, str]:
    query = discussion_point
    if transcript_excerpt:
        query = f"{transcript_excerpt}\n{discussion_point}"
    passages = retrieval.retrieve(document_id, query)
    if not passages:
        return {
            "verbatim_passage": "",
            "passage_position": None,
            "issue_question": "",
            "evidence_status": "insufficient",
            "suggested_question": None,
        }, "retrieval_only"

    try:
        with model_lock:
            raw = _call_llm(_build_prompt(discussion_point, passages))
        data = _parse_response(raw)
        status = data.get("evidence_status", "insufficient")
        if status not in VALID_STATUSES:
            status = "insufficient"
        return {
            "verbatim_passage": data.get("verbatim_passage", ""),
            "passage_position": data.get("passage_position") or None,
            "issue_question": data.get("issue_question", ""),
            "evidence_status": status,
            "suggested_question": data.get("suggested_question") or None,
        }, "llm_grounded"
    except Exception:
        top = passages[0]
        return {
            "verbatim_passage": top["text"],
            "passage_position": top["position"],
            "issue_question": "",
            "evidence_status": "insufficient",
            "suggested_question": None,
        }, "retrieval_only"
