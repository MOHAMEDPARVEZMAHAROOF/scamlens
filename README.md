# ScamLens

Paste a suspicious message, get a scam verdict — in English **and** Tamil.

ScamLens is a scam-message screening assistant built for users in India. It
combines a **deterministic pre-screener** (regex artifact extraction +
multilingual keyword lexicons) with an **LLM verdict** (NVIDIA Nemotron 3
Super) that explains the trick in plain English, plus a deterministic Tamil
explanation and an actionable safety checklist. When the LLM is unreachable,
a weighted rules-based fallback still returns a verdict, so the tool never
goes silent.

Built for the **ForgeHacks Online 2026** hackathon, **AI + Cybersecurity**
track.

## The problem

KYC-expiry fraud, UPI collect-request tricks, "digital arrest" intimidation
calls, and fake work-from-home job offers target millions of people in India
every year — often in a mix of English, Hinglish, and Tamil. Most victims
never get a second opinion before they act. ScamLens gives them one: paste
the message, see what's wrong with it, and learn what to do next.

## Features

- **Paste-and-scan** — drop in an SMS, WhatsApp message, or call transcript.
- **Deterministic pre-screener** — extracts URLs (flags shorteners), UPI IDs,
  phone numbers, and OTP-like digit runs; matches English/Hinglish/Tamil-
  transliteration keyword lexicons (urgency, fake authority, payment demands,
  secrecy pressure, too-good offers).
- **LLM verdict** — NVIDIA Nemotron 3 Super returns strict JSON: calibrated
  `SAFE | SUSPICIOUS | SCAM` verdict, confidence, verbatim-quoted red flags,
  a plain-English explanation of the trick, and a safety checklist.
  The Tamil explanation is a deterministic human-written template matched to
  the verdict — the model cannot reliably generate Tamil-script prose, so we
  don't ask it to.
- **Rules fallback** — if the LLM fails or returns garbage, a weighted-score
  rules engine answers instead (`"mode": "rules"` vs `"mode": "llm"`).
- **Scan history** — every scan is stored in SQLite and listed in the UI.
- **Shareable text card** — `GET /api/card/{id}` renders a plain-text verdict
  card you can forward to family members.
- **Bilingual by design** — every result ships with an English explanation
  (AI-generated) and a Tamil explanation (deterministic template).

## Tech stack

- **Backend:** FastAPI, SQLite (stdlib `sqlite3`), vanilla JS frontend
- **LLM:** NVIDIA Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`) via
  the OpenAI-compatible chat-completions API at `integrate.api.nvidia.com`
- **Pre-screener:** deterministic, stdlib-only (`scamlens/prescreen.py` +
  keyword lists in `scamlens/lexicons.py`)
- **Tests:** pytest, fully offline (the LLM is monkeypatched to fail so the
  API tests always exercise the rules path)

## Quickstart

```bash
cd scamlens
bash run.sh
# open http://127.0.0.1:8000
```

`run.sh` creates `.venv` on first run, installs `requirements.txt`, and
serves the app with uvicorn. Scan data lives in `data/` (override with the
`SCAMLENS_DATA` env var).

To run the tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

## API overview

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/status` | Scan count, LLM availability, model label |
| `POST` | `/api/scan` | `{"text": "..."}` → scan result (`id`, `verdict`, `confidence`, `red_flags`, `trick_en`, `trick_ta`, `checklist`, `mode`) |
| `GET` | `/api/scans` | List recent scans (id, verdict, confidence, excerpt) |
| `GET` | `/api/scans/{id}` | Full stored scan |
| `DELETE` | `/api/scans/{id}` | Delete a scan |
| `GET` | `/api/card/{id}` | Plain-text shareable verdict card |

`verdict` is one of `SAFE | SUSPICIOUS | SCAM`; `mode` is `llm` when the
model answered or `rules` when the deterministic fallback did.

## Honesty notes

- **The six files in `sample_inputs/` are self-authored archetypes** of
  publicly documented scam patterns (fake bank-KYC SMS, UPI collect-request
  fraud, Tamil "digital arrest" intimidation, fake part-time job offer) plus
  two genuine messages (a bank credit alert, a login OTP). They are
  illustrative test fixtures — not real messages, not scraped data, and not
  evidence of any real sender's behavior. Phone numbers, UPI IDs, and links
  in them are fictional.
- **Verdicts are advisory, not legal or financial advice.** ScamLens is an
  automated screening aid. It can be wrong in both directions.
- **No accuracy claims** are made about detection rates; the tool has not
  been evaluated on a labeled dataset.
- If you receive a genuinely suspicious message: verify through an official
  channel (your bank's official app or a number from their official site —
  never one from the message), never share OTPs/PINs/CVV, and report fraud
  at [cybercrime.gov.in](https://cybercrime.gov.in) (helpline **1930**).

## License

MIT — see [LICENSE](LICENSE).
