import logging
import pytest
from cold_apply.models import StopwordGroup

# --- Test 1: general Unicode robustness (pure non-Latin + ASCII normalization) ---
@pytest.mark.django_db
def test_unicode_roundtrip():
    sample = ["的", "и", "🚀", "𓂀", "Data", "DATA", " data "]
    g = StopwordGroup.objects.create(
        category="nltk english stopwords",
        words=", ".join(sample),
    )
    tokens = {t for t in (w.strip().lower() for w in g.words.split(",")) if t}

    # ASCII normalization
    assert "data" in tokens
    assert "DATA" not in tokens and " data " not in tokens

    # Non-Latin preserved
    for tk in ["的", "и", "🚀", "𓂀"]:
        assert tk in tokens

# --- Test 2: mixed-script confusables + exotic combos; no ASCII lookalikes created ---
logger = logging.getLogger("stopwords_mixed_unicode")

@pytest.mark.django_db
def test_mixed_unicode_roundtrip_and_no_ascii_confusion(caplog):
    caplog.set_level(logging.INFO, logger="stopwords_mixed_unicode")

    confusables = [
        "pаypal",    # Latin p + Cyrillic а
        "gооgle",    # Latin g + Cyrillic о + о
        "microsоft", # Latin micros + Cyrillic о + ft
        "amazоn",    # Latin amaz + Cyrillic о + n
        "facebооk",  # Latin faceb + Cyrillic о + о + k
        "twittеr",   # Latin twitt + Cyrillic е + r
        "linkеdin",  # Latin link + Cyrillic е + din
    ]
    exotic = [
        "𓂀", "的", "測試", "data𓂀", "測試test", "テストtest", "данныеdata", "data🚀"
    ]

    g = StopwordGroup.objects.create(
        category="nltk english stopwords",
        words=", ".join(confusables + exotic),
    )
    tokens = {t for t in (w.strip().lower() for w in g.words.split(",")) if t}

    logger.info("Parsed %d tokens. Preview: %r", len(tokens), sorted(tokens)[:40])

    # Positive: every inserted token present (case-folded)
    for s in confusables + exotic:
        assert s.lower() in tokens, f"missing token: {s!r}"

    # Negative: no unintended ASCII lookalikes created
    ascii_equivalents = [
        "paypal", "google", "microsoft", "amazon",
        "facebook", "twitter", "linkedin", "data", "test"
    ]
    for ascii_word in ascii_equivalents:
        assert ascii_word not in tokens, f"unexpected ascii token: {ascii_word!r}"
