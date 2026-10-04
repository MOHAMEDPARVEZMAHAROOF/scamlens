"""ScamLens web server: paste a message, get a scam verdict (EN + Tamil)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import db, llm, prescreen

try:
    from .prompts import VERDICT_SYSTEM
except ImportError:  # prompts.py owned by another worker
    VERDICT_SYSTEM = (
        "You are ScamLens, a scam-detection assistant. Analyze the message and "
        "reply with ONLY a JSON object: {\"verdict\": \"SAFE\"|\"SUSPICIOUS\"|\"SCAM\", "
        "\"confidence\": 0-100, "
        "\"red_flags\": [{\"phrase\": \"exact suspicious phrase\", \"category\": \"short string\", \"why\": \"one-line reason\"}], "
        "\"trick_en\": \"2-3 sentence plain-English explanation of the trick\", "
        "\"trick_ta\": \"the same explanation in simple Tamil (2-3 sentences)\", "
        "\"checklist\": [\"safety tips as short strings\"]}. "
        "Be careful and evidence-based: label SCAM only when clear scam signals "
        "exist (payment demands, OTP/bank detail requests, phishing links, "
        "impersonation, urgency + secrecy).")

BASE = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("SCAMLENS_DATA", BASE / "data"))
DB = DATA / "scamlens.db"
WEB = BASE / "web"

app = FastAPI(title="ScamLens")

if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB), name="static")

MAX_TEXT = 8000
VALID_VERDICTS = {"SAFE", "SUSPICIOUS", "SCAM"}


# ------------------------------------------------------------------ pages
@app.get("/")
def home():
    index = WEB / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<html><body><h1>ScamLens backend</h1>"
        "<p>Frontend (web/index.html) is not built yet. API is live at "
        "<code>/api/status</code>.</p></body></html>")


# ------------------------------------------------------------------ helpers
def _parse_model_json(raw: str) -> dict:
    """Extract and validate the verdict JSON from model output."""
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    obj = json.loads(raw[start:end])

    verdict = str(obj.get("verdict", "")).strip().upper()
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"bad verdict: {verdict!r}")
    try:
        confidence = float(obj.get("confidence", 0))
    except (TypeError, ValueError):
        raise ValueError("bad confidence")
    confidence = max(0.0, min(100.0, confidence))

    flags = []
    raw_flags = obj.get("red_flags") or []
    if isinstance(raw_flags, list):
        for f in raw_flags:
            if not isinstance(f, dict):
                continue
            phrase = str(f.get("phrase", "")).strip()
            if not phrase:
                continue
            flags.append({"phrase": phrase[:200],
                          "category": str(f.get("category", ""))[:60],
                          "why": str(f.get("why", ""))[:300]})

    checklist = [str(c)[:300] for c in (obj.get("checklist") or [])
                 if str(c).strip()][:10]
    return {"verdict": verdict, "confidence": round(confidence, 1),
            "red_flags": flags,
            "trick_en": str(obj.get("trick_en", "")).strip()[:2000],
            "trick_ta": str(obj.get("trick_ta", "")).strip()[:2000],
            "checklist": checklist}


_JSON_FMT = {"type": "json_object"}


def _verdict_for(text: str) -> dict:
    hits = prescreen.prescreen(text)
    hit_lines = [f"- {h['kind']}/{h['category']}: {h['match']}" for h in hits]
    user_msg = (
        "Analyze this message for scam indicators:\n\n"
        f"{text}\n\n"
        "Deterministic pre-screen hits:\n"
        + ("\n".join(hit_lines) if hit_lines else "(none)"))
    try:
        raw = llm.complete(
            [{"role": "system", "content": VERDICT_SYSTEM},
             {"role": "user", "content": user_msg}],
            temperature=0.2, max_tokens=8192, timeout=300.0,
            response_format=_JSON_FMT)
        try:
            result = _parse_model_json(raw)
        except ValueError:
            # reasoning leak: nudge once for JSON-only output
            raw = llm.complete(
                [{"role": "system", "content": VERDICT_SYSTEM},
                 {"role": "user", "content": user_msg + "\n\nReply with ONLY the JSON object, no other text."}],
                temperature=0.1, max_tokens=8192, timeout=300.0,
                response_format=_JSON_FMT)
            result = _parse_model_json(raw)
        result["mode"] = "llm"
        if not result["checklist"]:
            result["checklist"] = list(prescreen.CHECKLIST)
        # Tamil explanation is a deterministic template (the LLM cannot
        # reliably generate Tamil-script prose); English is AI-generated.
        result["trick_ta"] = prescreen.template_ta(
            result["verdict"], bool(result["red_flags"]))
        return result
    except Exception:  # LLM down / bad output -> deterministic fallback
        return prescreen.rules_verdict(text, hits)


# ------------------------------------------------------------------ API
@app.get("/api/status")
def status():
    conn = db.connect(DB)
    try:
        scans = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
    finally:
        conn.close()
    return {"scans": scans, "llm": llm.configured(),
            "backend": llm.backend_label()}


@app.post("/api/scan")
def scan(body: dict):
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Empty text.")
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT]
    result = _verdict_for(text)
    conn = db.connect(DB)
    try:
        cur = conn.execute(
            "INSERT INTO scans (text, verdict, confidence, red_flags, trick_en,"
            " trick_ta, checklist, mode, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (text, result["verdict"], result["confidence"],
             json.dumps(result["red_flags"], ensure_ascii=False),
             result["trick_en"], result["trick_ta"],
             json.dumps(result["checklist"], ensure_ascii=False),
             result["mode"], db.now()))
        conn.commit()
        scan_id = cur.lastrowid
    finally:
        conn.close()
    return {"id": scan_id, **result}


@app.get("/api/scans")
def scans():
    conn = db.connect(DB)
    try:
        rows = conn.execute(
            "SELECT id, verdict, confidence, text, created_at FROM scans"
            " ORDER BY created_at DESC LIMIT 50").fetchall()
    finally:
        conn.close()
    return [{"id": r["id"], "verdict": r["verdict"],
             "confidence": r["confidence"],
             "excerpt": r["text"][:120], "created_at": r["created_at"]}
            for r in rows]


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: int):
    conn = db.connect(DB)
    try:
        row = conn.execute("SELECT * FROM scans WHERE id=?",
                           (scan_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Scan not found.")
    return {"id": row["id"], "text": row["text"], "verdict": row["verdict"],
            "confidence": row["confidence"],
            "red_flags": json.loads(row["red_flags"]),
            "trick_en": row["trick_en"], "trick_ta": row["trick_ta"],
            "checklist": json.loads(row["checklist"]),
            "mode": row["mode"], "created_at": row["created_at"]}


@app.delete("/api/scans/{scan_id}")
def delete_scan(scan_id: int):
    conn = db.connect(DB)
    try:
        conn.execute("DELETE FROM scans WHERE id=?", (scan_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.get("/api/card/{scan_id}")
def card(scan_id: int):
    conn = db.connect(DB)
    try:
        row = conn.execute(
            "SELECT verdict, confidence, red_flags, created_at FROM scans"
            " WHERE id=?", (scan_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Scan not found.")
    flags = json.loads(row["red_flags"])
    lines = [
        f"ScamLens verdict: {row['verdict']} ({row['confidence']:.0f}%)",
    ]
    if flags:
        lines.append("Red flags:")
        for f in flags[:8]:
            lines.append(f"  - {f['phrase']} [{f['category']}]")
    lines.append("")
    lines.append("Advisory: This is an automated screening, not legal or "
                 "financial advice. Verify suspicious messages through official "
                 "channels before acting. Never share OTPs, PINs, or bank details.")
    return PlainTextResponse("\n".join(lines))
