"""ScamLens test suite — fully offline, no live-LLM dependency.

Covers:
  * scamlens/lexicons.py — exact list names, lowercase entries, contract phrases
  * scamlens/prompts.py  — VERDICT_SYSTEM contract requirements
  * sample_inputs/       — the six self-authored archetype messages
  * scamlens/prescreen.py — artifact extraction (URL / UPI ID / phone),
                            lexicon hits, and rules_verdict() verdicts
  * scamlens/app.py      — FastAPI lifecycle via TestClient with SCAMLENS_DATA
                            pointed at tmp_path and the LLM forced to fail, so
                            every scan runs in deterministic "rules" mode.

Run:  cd ~/workspace/scamlens && .venv/bin/python -m pytest tests/ -q
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from scamlens import lexicons, prescreen, prompts
from scamlens.prescreen import prescreen as prescreen_text, rules_verdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = PROJECT_ROOT / "sample_inputs"


def sample(name: str) -> str:
    return (SAMPLES / f"{name}.txt").read_text(encoding="utf-8").strip()


# ================================================================== lexicons
class TestLexicons:
    EXPECTED = {
        "URGENCY": ["urgent", "immediately", "account blocked",
                    "turant", "udane", "avasaram", "udanae"],
        "AUTHORITY": ["rbi", "cbi", "police", "customs", "income tax",
                      "bank manager", "kyc department", "digital arrest",
                      "cyber crime"],
        "PAYMENT": ["otp", "cvv", "upi", "collect request", "pay now",
                    "refund", "processing fee", "account verify"],
        "SECRECY": ["do not tell", "keep secret", "don't disconnect",
                    "stay on the line", "maatram", "yarukkum solladha"],
        "OFFERS": ["lottery", "prize", "cashback", "work from home",
                   "part-time job", "double your money"],
    }

    @pytest.mark.parametrize("name", list(EXPECTED))
    def test_list_exists_and_is_clean(self, name):
        words = getattr(lexicons, name)
        assert isinstance(words, list), f"{name} must be a plain list"
        assert words, f"{name} must not be empty"
        for w in words:
            assert isinstance(w, str) and w, f"{name} has a bad entry: {w!r}"
            assert w == w.lower(), f"{name} entry not lowercase: {w!r}"
        assert len(set(words)) == len(words), f"{name} has duplicates"

    @pytest.mark.parametrize("name,phrases",
                             [(n, p) for n, ps in EXPECTED.items() for p in ps])
    def test_contract_phrase_present(self, name, phrases):
        assert phrases in getattr(lexicons, name), \
            f"{name} missing contract phrase {phrases!r}"


# =================================================================== prompts
class TestPrompts:
    def test_verdict_system_exists(self):
        assert isinstance(prompts.VERDICT_SYSTEM, str)
        assert len(prompts.VERDICT_SYSTEM) > 500

    def test_strict_json_schema_demanded(self):
        p = prompts.VERDICT_SYSTEM
        for key in ['"verdict"', '"confidence"', '"red_flags"',
                    '"trick_en"', '"checklist"',
                    '"phrase"', '"category"', '"why"']:
            assert key in p, f"VERDICT_SYSTEM missing schema key {key}"
        # Tamil is produced by a separate translation step, not the verdict LLM
        assert '"trick_ta"' not in p
        assert "JSON" in p
        assert "SAFE" in p and "SUSPICIOUS" in p and "SCAM" in p

    def test_tamil_via_deterministic_template(self):
        # The LLM cannot reliably generate Tamil-script prose, so the Tamil
        # explanation is a fixed human-written template matched to the verdict.
        from scamlens import prescreen
        for verdict, has_hits in [("SCAM", True), ("SUSPICIOUS", False), ("SAFE", False)]:
            ta = prescreen.template_ta(verdict, has_hits)
            assert isinstance(ta, str) and len(ta) > 20
            assert any(0x0B80 <= ord(c) <= 0x0BFF for c in ta)
            # no wrong scripts mixed in
            for c in ta:
                o = ord(c)
                assert not (0x0400 <= o <= 0x04FF or 0x4E00 <= o <= 0x9FFF), \
                    f"non-Tamil script char in template: {c!r}"

    def test_calibration_and_quoting_rules(self):
        p = prompts.VERDICT_SYSTEM.lower()
        assert "safe only if" in p or "safe only" in p
        assert "verbatim" in p

    def test_checklist_mandates(self):
        p = prompts.VERDICT_SYSTEM.lower()
        assert "cybercrime.gov.in" in p
        assert "official channel" in p

    def test_no_advice_claims(self):
        p = prompts.VERDICT_SYSTEM.lower()
        assert "not" in p and "legal" in p and "financial advice" in p


# =================================================================== samples
class TestSamples:
    NAMES = ["kyc_sms", "upi_collect", "digital_arrest_ta",
             "job_offer", "genuine_bank", "genuine_otp"]

    @pytest.mark.parametrize("name", NAMES)
    def test_sample_exists_and_nonempty(self, name):
        path = SAMPLES / f"{name}.txt"
        assert path.exists(), f"missing {path}"
        assert sample(name), f"{name}.txt is empty"

    def test_kyc_sms_has_url_and_lexicon_hits(self):
        hits = prescreen_text(sample("kyc_sms"))
        urls = [h for h in hits if h["kind"] == "url"]
        assert urls and any("http" in h["match"] for h in urls)
        cats = {h["category"] for h in hits if h["kind"] == "lexicon"}
        assert "urgency" in cats and "authority" in cats

    def test_upi_collect_has_upi_id_and_phone(self):
        hits = prescreen_text(sample("upi_collect"))
        upis = [h for h in hits if h["kind"] == "upi"]
        assert upis and any("@" in h["match"] for h in upis)
        phones = [h for h in hits if h["kind"] == "phone"]
        assert phones and any(c.isdigit() for h in phones for c in h["match"])

    def test_digital_arrest_ta_lexicon_categories(self):
        hits = prescreen_text(sample("digital_arrest_ta"))
        cats = {h["category"] for h in hits if h["kind"] == "lexicon"}
        assert {"urgency", "authority", "secrecy"} <= cats

    def test_job_offer_has_url_and_offer_hit(self):
        hits = prescreen_text(sample("job_offer"))
        assert any(h["kind"] == "url" for h in hits)
        cats = {h["category"] for h in hits if h["kind"] == "lexicon"}
        assert "offers" in cats

    @pytest.mark.parametrize("name", ["genuine_bank", "genuine_otp"])
    def test_genuine_samples_have_no_url(self, name):
        hits = prescreen_text(sample(name))
        assert not [h for h in hits if h["kind"] == "url"], \
            f"{name} unexpectedly contains a URL hit"


# ============================================================= rules verdict
def _verdict_for(name: str) -> dict:
    text = sample(name)
    return rules_verdict(text, prescreen_text(text))


class TestRulesVerdict:
    def test_result_shape(self):
        rv = _verdict_for("kyc_sms")
        for key in ("verdict", "confidence", "red_flags",
                    "trick_en", "trick_ta", "checklist", "mode"):
            assert key in rv, f"rules_verdict missing {key!r}"
        assert rv["mode"] == "rules"
        assert isinstance(rv["red_flags"], list)
        assert isinstance(rv["checklist"], list) and rv["checklist"]
        assert 0 <= rv["confidence"] <= 100

    def test_kyc_sms_is_scam(self):
        assert _verdict_for("kyc_sms")["verdict"] == "SCAM"

    def test_upi_collect_is_scam(self):
        assert _verdict_for("upi_collect")["verdict"] == "SCAM"

    def test_digital_arrest_ta_is_scam(self):
        assert _verdict_for("digital_arrest_ta")["verdict"] == "SCAM"

    def test_job_offer_is_suspicious(self):
        assert _verdict_for("job_offer")["verdict"] == "SUSPICIOUS"

    def test_genuine_bank_is_safe(self):
        assert _verdict_for("genuine_bank")["verdict"] == "SAFE"

    def test_genuine_otp_is_safe(self):
        assert _verdict_for("genuine_otp")["verdict"] == "SAFE"


# ======================================================================== API
def _fresh_client(monkeypatch, tmp_path):
    """Import scamlens.app with SCAMLENS_DATA=tmp_path and the LLM rigged
    to fail, so /api/scan always exercises the deterministic rules path."""
    monkeypatch.setenv("SCAMLENS_DATA", str(tmp_path))
    for mod in [m for m in list(sys.modules)
                if m == "scamlens.app" or m.startswith("scamlens.app.")]:
        del sys.modules[mod]
    app_module = importlib.import_module("scamlens.app")
    llm_module = importlib.import_module("scamlens.llm")

    def _boom(*args, **kwargs):
        raise RuntimeError("LLM disabled in tests")

    monkeypatch.setattr(llm_module, "complete", _boom)
    if hasattr(app_module, "complete"):  # defensive: direct-import style
        monkeypatch.setattr(app_module, "complete", _boom)
    from fastapi.testclient import TestClient
    return TestClient(app_module.app)


def _post_scan(client, text):
    resp = client.post("/api/scan", json={"text": text})
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestAPI:
    def test_scan_scam_in_rules_mode_matches_contract(self, monkeypatch,
                                                      tmp_path):
        client = _fresh_client(monkeypatch, tmp_path)
        body = _post_scan(client, sample("kyc_sms"))
        assert body["mode"] == "rules"          # LLM was forced to fail
        assert body["verdict"] == "SCAM"
        for key in ("verdict", "confidence", "red_flags",
                    "trick_en", "trick_ta", "checklist"):
            assert key in body, f"scan response missing {key!r}"
        assert isinstance(body["red_flags"], list) and body["red_flags"]
        assert isinstance(body["checklist"], list) and body["checklist"]
        assert "id" in body

    def test_scan_safe_sample(self, monkeypatch, tmp_path):
        client = _fresh_client(monkeypatch, tmp_path)
        body = _post_scan(client, sample("genuine_bank"))
        assert body["mode"] == "rules"
        assert body["verdict"] == "SAFE"

    def test_scan_lifecycle_list_card_delete(self, monkeypatch, tmp_path):
        client = _fresh_client(monkeypatch, tmp_path)
        created = _post_scan(client, sample("upi_collect"))
        scan_id = created["id"]

        # GET /api/scans lists it
        listed = client.get("/api/scans")
        assert listed.status_code == 200
        ids = [s["id"] for s in listed.json()]
        assert scan_id in ids

        # GET /api/card/{id} is text/plain containing "ScamLens"
        card = client.get(f"/api/card/{scan_id}")
        assert card.status_code == 200
        assert "text/plain" in card.headers["content-type"]
        assert "ScamLens" in card.text

        # DELETE removes it
        deleted = client.delete(f"/api/scans/{scan_id}")
        assert deleted.status_code == 200
        ids_after = [s["id"] for s in client.get("/api/scans").json()]
        assert scan_id not in ids_after
        assert client.get(f"/api/card/{scan_id}").status_code == 404
