"""Keyword lexicons for the ScamLens deterministic pre-screener.

Imported by scamlens/prescreen.py (names must stay exact). All entries are
lowercase; prescreen.py matches them case-insensitively with word boundaries.
Covers English, Hinglish, and Tamil transliteration (Tanglish) phrasing seen
in common Indian scam messages (fake KYC, UPI collect-request, digital
arrest, fake job offers).
"""

# Pressure / manufactured urgency: English + Hinglish + Tamil transliteration.
URGENCY = [
    # English
    "urgent",
    "urgently",
    "immediately",
    "immediate action",
    "act now",
    "right now",
    "account blocked",
    "blocked within",
    "within 24 hours",
    "last chance",
    "final notice",
    "final warning",
    "expires today",
    "today only",
    "limited time",
    "hurry",
    "don't delay",
    "do not delay",
    "asap",
    "at once",
    # Hinglish
    "turant",
    "turant karo",
    "abhi",
    "abhi karo",
    "jaldi",
    "jaldi karo",
    "foran",
    # Tamil transliteration (Tanglish): udane/udanae = immediately,
    # avasaram = urgency/emergency, seekiram = quickly
    "udane",
    "udanae",
    "avasaram",
    "seekiram",
]

# Impersonated authorities / institutions scammers pose as.
AUTHORITY = [
    "rbi",
    "reserve bank",
    "cbi",
    "police",
    "cyber police",
    "customs",
    "income tax",
    "income-tax",
    "enforcement directorate",
    "ed officer",
    "bank manager",
    "kyc department",
    "digital arrest",
    "cyber crime",
    "cybercrime",
    "court",
    "supreme court",
    "high court",
    "narcotics",
    "trai",
    "sebi",
    "government of india",
    "govt of india",
    "ministry of",
    "interpol",
    "officer",
]

# Money / credential extraction cues.
PAYMENT = [
    "otp",
    "cvv",
    "upi",
    "upi pin",
    "atm pin",
    "collect request",
    "pay now",
    "refund",
    "processing fee",
    "registration fee",
    "advance payment",
    "account verify",
    "verify your account",
    "share otp",
    "enter otp",
    "card number",
    "bank details",
    "approve the request",
    "payment link",
]

# Isolation tactics: stop the victim asking for help or hanging up.
SECRECY = [
    "do not tell",
    "don't tell",
    "tell no one",
    "keep secret",
    "keep this confidential",
    "keep it confidential",
    "do not disconnect",
    "don't disconnect",
    "don't cut",
    "stay on the line",
    # Tamil transliteration: maatram = only/merely (as in "don't cut the phone"),
    # yarukkum solladha = don't tell anyone, veliya solladha = don't tell
    # outside, cut pannadha = don't cut (the call), ragasiyam = secret
    "maatram",
    "yarukkum solladha",
    "veliya solladha",
    "cut pannadha",
    "ragasiyam",
]

# Too-good-to-be-true lures.
OFFERS = [
    "lottery",
    "prize",
    "cashback",
    "work from home",
    "part-time job",
    "double your money",
    "winner",
    "you have won",
    "you've won",
    "free gift",
    "earn from home",
    "no investment",
    "easy money",
    "data entry",
    "part time",
    "work-from-home",
]
