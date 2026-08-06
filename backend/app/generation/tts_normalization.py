"""Normalize narration text before sending it to TTS."""

import re


# Add TTS-specific spellings here when the speech model mispronounces a term.
# Replacements should be written the way the voice model should read them.
PRONUNCIATION_MAP = {
    # Scratch project mappings.
    "Mazagon": "Mazgaon",
    "Mazagon's": "Mazgaon's",
    # Indian markets, regulators, and institutions.
    "SEBI": "Sebee",
    "NSE": "N S E",
    "BSE": "B S E",
    "RBI": "R B I",
    "IRDAI": "I R D A I",
    "AMFI": "Amfee",
    "NISM": "N I S M",
    "NSDL": "N S D L",
    "CDSL": "C D S L",
    "NPCI": "N P C I",
    "UPI": "U P I",
    "GST": "G S T",
    "PAN": "P A N",
    "KYC": "K Y C",
    "Aadhaar": "Aadhaar",
    # Securities, products, and portfolio terms.
    "IPO": "I P O",
    "FPO": "F P O",
    "QIP": "Q I P",
    "OFS": "O F S",
    "NCD": "N C D",
    "NCDs": "N C D's",
    "ETF": "E T F",
    "ETFs": "E T F's",
    "REIT": "Reet",
    "REITs": "Reets",
    "InvIT": "Invit",
    "InvITs": "Invits",
    "SIP": "S I P",
    "SIPs": "S I P's",
    "SWP": "S W P",
    "STP": "S T P",
    "NAV": "N A V",
    "AUM": "A U M",
    "CAGR": "C A G R",
    "XIRR": "X I R R",
    "YTM": "Y T M",
    "MTM": "M T M",
    "VaR": "value at risk",
    "alpha": "alpha",
    "beta": "beta",
    # Accounting and company performance.
    "EBITDA": "E B I T D A",
    "EBIT": "E B I T",
    "PAT": "P A T",
    "PBT": "P B T",
    "ROE": "R O E",
    "ROCE": "R O C E",
    "ROA": "R O A",
    "EPS": "E P S",
    "DPS": "D P S",
    "P/E": "P E",
    "P/B": "P B",
    "EV/EBITDA": "E V to E B I T D A",
    "P&L": "P and L",
    "YoY": "year on year",
    "QoQ": "quarter on quarter",
    "MoM": "month on month",
    "YTD": "year to date",
    "MRR": "M R R",
    "ARR": "A R R",
    "ARPU": "A R P U",
    "LTV": "L T V",
    "CAC": "C A C",
    "GMV": "G M V",
    # Sales, business operations, and go-to-market.
    "CRM": "C R M",
    "ERP": "E R P",
    "SaaS": "sass",
    "B2B": "B to B",
    "B2C": "B to C",
    "D2C": "D to C",
    "SME": "S M E",
    "MSME": "M S M E",
    "MOU": "M O U",
    "RFP": "R F P",
    "RFQ": "R F Q",
    "SLA": "S L A",
    "KPI": "K P I",
    "KPIs": "K P I's",
    "OKR": "O K R",
    "OKRs": "O K R's",
    "SKU": "S K U",
    "SKUs": "S K U's",
    "TAM": "T A M",
    "SAM": "S A M",
    "SOM": "S O M",
    "GTX": "G T X",
    "GTM": "G T M",
    "MoU": "M O U",
}

_CURRENCY_REPLACEMENTS = (
    (re.compile(r"\bRs\.?\s*", re.IGNORECASE), "Rupees "),
    (re.compile(r"\bINR\s*", re.IGNORECASE), "Rupees "),
    (re.compile(r"\bUSD\s*", re.IGNORECASE), "US dollars "),
    (re.compile(r"\bEUR\s*", re.IGNORECASE), "euros "),
    (re.compile(r"\bGBP\s*", re.IGNORECASE), "British pounds "),
)

_UNIT_REPLACEMENTS = (
    (re.compile(r"\bcr\.?\b", re.IGNORECASE), "crore"),
    (re.compile(r"\bcrs\.?\b", re.IGNORECASE), "crores"),
    (re.compile(r"\blakh\b", re.IGNORECASE), "lakh"),
    (re.compile(r"\blacs?\b", re.IGNORECASE), "lakhs"),
    (re.compile(r"\bbps\b", re.IGNORECASE), "basis points"),
)


def _term_pattern(term: str) -> re.Pattern:
    prefix = r"(?<![A-Za-z0-9])" if re.match(r"[A-Za-z0-9]", term[0]) else ""
    suffix = r"(?![A-Za-z0-9])" if re.match(r"[A-Za-z0-9]", term[-1]) else ""
    return re.compile(prefix + re.escape(term) + suffix, re.IGNORECASE)


def apply_pronunciation_map(text: str) -> str:
    for word, replacement in sorted(PRONUNCIATION_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        text = _term_pattern(word).sub(replacement, text)
    return text


def _expand_percent(match: re.Match) -> str:
    return f"{match.group(1)} percent"


def _expand_financial_year(match: re.Match) -> str:
    year = match.group(1)
    suffix = match.group(2)
    return f"financial year {year} {suffix}"


def normalize_financial_text(text: str) -> str:
    if not text:
        return text

    normalized = text
    for pattern, replacement in _CURRENCY_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    for pattern, replacement in _UNIT_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)

    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*%", _expand_percent, normalized)
    normalized = re.sub(
        r"\bFY\s*([0-9]{2})(?:\s*[-/]\s*)?([0-9]{2})\b",
        _expand_financial_year,
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\bQ([1-4])\s*FY\s*([0-9]{2})\b",
        r"quarter \1 financial year \2",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def clean_text_for_tts(text: str) -> str:
    cleaned_text = re.sub(r"<[^>]+>", "", text)
    cleaned_text = cleaned_text.replace("\\", "'").replace('"', "'")
    cleaned_text = apply_pronunciation_map(cleaned_text)
    cleaned_text = normalize_financial_text(cleaned_text)
    cleaned_text = cleaned_text.replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    cleaned_text = cleaned_text.replace("...", ".")
    cleaned_text = re.sub(r"\b[A-Z]{2,}\b", lambda match: " ".join(match.group(0)), cleaned_text)
    cleaned_text = cleaned_text.replace("Ltd.", "Limited").replace("Rs ", "Rupees ")
    return cleaned_text
