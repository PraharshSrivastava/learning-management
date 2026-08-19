from __future__ import annotations

from app.generation.tts_normalization import clean_text_for_tts, normalize_financial_text


def test_normalize_financial_text_preserves_paragraph_breaks() -> None:
    text = "Intro line.\n\nRevenue grew 12% in FY23-24.\nNext idea."

    assert normalize_financial_text(text) == (
        "Intro line.\n\n"
        "Revenue grew 12 percent in financial year 23 24.\n"
        "Next idea."
    )


def test_clean_text_for_tts_keeps_tts_pacing_breaks() -> None:
    text = "Welcome to SEBI basics.\n\nNext, we explain SIPs and ETFs."

    assert clean_text_for_tts(text) == (
        "Welcome to Sebee basics.\n\n"
        "Next, we explain S I P's and E T F's."
    )
