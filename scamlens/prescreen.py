"""Deterministic pre-screener for ScamLens (stdlib only).

Regexes catch machine-readable artifacts (URLs, UPI IDs, phone numbers,
OTP-style digit runs); lexicon lists (owned by scamlens/lexicons.py) catch
scammy phrasing. rules_verdict() is the weighted-score fallback used when the
LLM is unreachable.
"""
from __future__ import annotations

import re

try:
    from .lexicons import URGENCY, AUTHORITY, PAYMENT, SECRECY, OFFERS
except ImportError:  # lexicons.py owned by another worker
    URGENCY, AUTHORITY, PAYMENT, SECRECY, OFFERS = [], [], [], [], []

# ------------------------------------------------------------------ patterns
URL_RE = re.compile(
    r"(https?://[^\s<>\"]+|www\.[^\s<>\"]+|"
    r"(?:bit\.ly|tinyurl\.com|goo\.gl|t\.co|is\.gd|ow\.ly|t\.me)[^\s<>\"]*)",
    re.IGNORECASE)
UPI_RE = re.compile(r"[\w.\-]{2,}@[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?91[\s\-]?\d{5}[\s\-]?\d{5}|\b[6-9]\d{9}\b)")
DIGITRUN_RE = re.compile(r"\b\d{4,}\b")  # OTPs, account-ish numbers

SHORTENER_HINT = re.compile(
    r"bit\.ly|tinyurl|goo\.gl|t\.co|is\.gd|ow\.ly|rb\.gy|shorturl", re.IGNORECASE)


def _lexicon_hits(text: str) -> list[dict]:
    hits = []
    seen = set()
    for category, words in (("urgency", URGENCY), ("authority", AUTHORITY),
                            ("payment", PAYMENT), ("secrecy", SECRECY),
                            ("offers", OFFERS)):
        for word in words:
            if not word:
                continue
            pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
            m = pattern.search(text)
            if m and (category, word.lower()) not in seen:
                seen.add((category, word.lower()))
                hits.append({"kind": "lexicon", "match": m.group(0),
                             "category": category})
    return hits


def prescreen(text: str) -> list[dict]:
    """Return list of hits: {"kind","match","category"}."""
    hits: list[dict] = []
    for m in URL_RE.finditer(text):
        url = m.group(0)
        cat = "shortened_url" if SHORTENER_HINT.search(url) else "url"
        hits.append({"kind": "url", "match": url, "category": cat})
    for m in UPI_RE.finditer(text):
        upi = m.group(0)
        if not re.match(r"^https?://", upi, re.IGNORECASE):
            hits.append({"kind": "upi", "match": upi, "category": "upi_id"})
    for m in PHONE_RE.finditer(text):
        hits.append({"kind": "phone", "match": m.group(0), "category": "phone"})
    for m in DIGITRUN_RE.finditer(text):
        hits.append({"kind": "digits", "match": m.group(0), "category": "otp_or_account"})
    hits.extend(_lexicon_hits(text))
    return hits


# ------------------------------------------------------------- rules fallback
WEIGHTS = {"url": 25, "upi": 25, "phone": 10, "digits": 5, "lexicon": 15}

CHECKLIST = [
    "Never share OTPs, bank passwords, or UPI PINs with anyone — real banks never ask.",
    "Do not click shortened or unknown links; verify the sender through the official app or website.",
    "Call the company/bank directly using a number from their official site, not one in the message.",
    "Do not send money to verify, unlock, or receive a payment — refunds never need a payment from you.",
    "Screenshot the message and report it: your bank's fraud helpline, 1930 (India), or the platform you got it on.",
]

_CATEGORY_LABELS = {
    "shortened_url": "shortened link",
    "url": "link",
    "upi_id": "UPI ID",
    "phone": "phone number",
    "otp_or_account": "OTP/account number",
    "urgency": "pressure/urgency",
    "authority": "fake authority",
    "payment": "money/payment demand",
    "secrecy": "secrecy pressure",
    "offers": "too-good offer",
}

# Tamil templates — plain, simple, correct Tamil (kept short for reliability).
_TA_TRICK_HAS_HITS = (
    "இந்தச் செய்தி உங்களை அவசரப்படுத்தி, பணம் அனுப்பவோ, OTP அல்லது வங்கி "
    "விவரங்களைப் பகிரவோ தூண்ட முயற்சிக்கிறது. இது பொதுவான மோசடி முறை: "
    "நம்பிக்கையை உருவாக்கி, பணம் அல்லது தகவலைப் பறிக்கிறார்கள்.")
_TA_TRICK_SUSPICIOUS = (
    "இந்தச் செய்தியில் சந்தேகத்திற்கிடமான அறிகுறிகள் உள்ளன. பணம் அனுப்பவோ, "
    "OTP பகிரவோ முன், அதிகாரப்பூர்வ ஆதாரத்தில் உறுதிப்படுத்துங்கள்.")
_TA_TRICK_SAFE = (
    "இந்தச் செய்தியில் மோசடியின் தெளிவான அறிகுறிகள் தென்படவில்லை. இருந்தாலும், "
    "பணம் அல்லது OTP சம்பந்தப்பட்டால் எப்போதும் கவனமாக இருங்கள்.")


def template_ta(verdict: str, has_hits: bool) -> str:
    """Deterministic Tamil explanation matched to the verdict.

    The LLM cannot reliably generate Tamil-script prose (it leaks reasoning
    in other scripts), so the Tamil explanation is always a fixed,
    human-written template. The English explanation is AI-generated.
    """
    if has_hits or verdict == "SCAM":
        return _TA_TRICK_HAS_HITS
    if verdict == "SUSPICIOUS":
        return _TA_TRICK_SUSPICIOUS
    return _TA_TRICK_SAFE


def rules_verdict(text: str, hits: list[dict]) -> dict:
    """Weighted-score fallback verdict when the LLM fails.

    score: url=25, upi=25, phone=10, digits=5, each lexicon hit=15,
    +10 urgency bonus if >=2 urgency-category lexicon hits.
    thresholds: >=60 SCAM, >=30 SUSPICIOUS, else SAFE.
    """
    score = sum(WEIGHTS.get(h["kind"], 0) for h in hits)
    urgency_hits = sum(1 for h in hits
                       if h["kind"] == "lexicon" and h["category"] == "urgency")
    if urgency_hits >= 2:
        score += 10

    if score >= 60:
        verdict, confidence = "SCAM", min(95, 40 + score)
    elif score >= 30:
        verdict, confidence = "SUSPICIOUS", min(95, 40 + score)
    else:
        verdict, confidence = "SAFE", min(95, 40 + score)

    seen: dict[tuple[str, str], dict] = {}
    for h in hits:
        cat = _CATEGORY_LABELS.get(h["category"], h["category"])
        key = (h["match"].strip(), cat)
        if key not in seen:
            seen[key] = {"phrase": h["match"].strip()[:80],
                         "category": cat,
                         "why": _why(cat, h["kind"])}
    red_flags = list(seen.values())

    if red_flags:
        phrases = "; ".join(f"{f['phrase']} ({f['category']})" for f in red_flags[:6])
        trick_en = (f"This message shows classic scam signals: {phrases}. "
                    f"Scammers use these to create urgency and get you to send "
                    f"money or share OTPs/bank details before you can think.")
        trick_ta = _TA_TRICK_HAS_HITS
    elif verdict == "SUSPICIOUS":
        trick_en = ("This message has some suspicious signals but no clear scam "
                    "pattern. Verify the sender through official channels before "
                    "acting.")
        trick_ta = _TA_TRICK_SUSPICIOUS
    else:
        trick_en = ("No clear scam signals were found in this message. Stay cautious "
                    "anyway — never share OTPs or send money based on a message alone.")
        trick_ta = _TA_TRICK_SAFE

    return {"verdict": verdict, "confidence": round(confidence, 1),
            "red_flags": red_flags, "trick_en": trick_en,
            "trick_ta": trick_ta, "checklist": list(CHECKLIST),
            "mode": "rules"}


def _why(category: str, kind: str) -> str:
    reasons = {
        "shortened link": "Shortened links hide the real destination and are common in phishing.",
        "link": "Unknown links can lead to fake login/payment pages that steal credentials.",
        "UPI ID": "Payments to a stranger's UPI ID are almost impossible to reverse.",
        "phone number": "Scammers ask you to call or share details on a personal number.",
        "OTP/account number": "Never share OTPs or bank details — real banks never ask for them.",
        "pressure/urgency": "Artificial urgency ('immediately', 'last chance') stops you from thinking.",
        "fake authority": "Claims of authority (bank, police, tax office) to force compliance.",
        "money/payment demand": "Demands for payment, fees, or 'verification' charges.",
        "secrecy pressure": "Asking you to keep it secret blocks you from asking for help.",
        "too-good offer": "Prize/lottery/job offers that are too good to be true usually are.",
    }
    return reasons.get(category, f"Flagged as {category} by the deterministic pre-screener.")
