import pytest
from datetime import date

from django.contrib.auth import get_user_model
from django.db import DataError, transaction

from cold_apply.models import Participant, Job, KeywordAnalysis
from cold_apply.static.scripts.keyword_analyzer.keyword_analyzer import (
    hook_after_jd_analysis,
)

# Schema limits we expect in the *migrated* DB:
UNIGRAM_LIMIT = 200
BIGRAM_LIMIT = 500
TRIGRAM_LIMIT = 800


def build_ngrams(n: int, target_len: int) -> list[str]:
    """
    Generate a list of n-gram strings whose ", ".join(...) length is ~target_len.
    Uses realistic-ish tokens (alpha/bravo/...) with indices appended to vary length.
    """
    base = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]
    grams: list[str] = []

    i = 0
    # Add n-gram strings until the joined length reaches target_len
    while True:
        # construct one n-gram like "alpha0 bravo1" or "alpha0 bravo1 charlie2"
        tokens = [f"{base[(i + k) % len(base)]}{i + k}" for k in range(n)]
        grams.append(" ".join(tokens))
        i += 1
        if len(", ".join(grams)) >= target_len:
            return grams


@pytest.mark.django_db
def test_keywordanalysis_field_capacity_handles_realistic_ngrams():
    """
    With bigram=CharField(500) and trigram=CharField(800):

      - "under-limit" values should insert successfully
      - "over-limit" values should raise DataError

    NOTE: This test requires you to have migrated the DB with:
      bigram  max_length=500
      trigram max_length=800
    """

    User = get_user_model()
    user = User.objects.create_user(username="cap_user", password="pw")
    participant = Participant.objects.create(user=user)
    job = Job.objects.create(participant=participant, description="capacity probe")

    # --- Case A: all fields comfortably below limits
    uni_ok = ", ".join(build_ngrams(1, 150))   # < 200
    bi_ok  = ", ".join(build_ngrams(2, 450))   # < 500
    tri_ok = ", ".join(build_ngrams(3, 750))   # < 800

    ka = KeywordAnalysis.objects.create(job=job, unigram=uni_ok, bigram=bi_ok, trigram=tri_ok)
    assert ka.pk is not None
    assert len(ka.unigram) < UNIGRAM_LIMIT
    assert len(ka.bigram)  < BIGRAM_LIMIT
    assert len(ka.trigram) < TRIGRAM_LIMIT

    # --- Case B: bigram string just over 500
    bi_long = ", ".join(build_ngrams(2, 520))
    assert len(bi_long) > BIGRAM_LIMIT

    with pytest.raises(DataError):
        with transaction.atomic():
            KeywordAnalysis.objects.create(job=job, unigram=uni_ok, bigram=bi_long, trigram=tri_ok)

    # --- Case C: trigram string just over 800
    tri_long = ", ".join(build_ngrams(3, 820))
    assert len(tri_long) > TRIGRAM_LIMIT

    with pytest.raises(DataError):
        with transaction.atomic():
            KeywordAnalysis.objects.create(job=job, unigram=uni_ok, bigram=bi_ok, trigram=tri_long)


@pytest.mark.django_db
def test_hook_after_jd_analysis_respects_new_limits():
    """
    Exercise hook_after_jd_analysis with lists of n-grams.

    Under-limit lists should succeed; over-limit lists should raise DataError
    with the current CharField limits (200/500/800).
    """

    User = get_user_model()
    user = User.objects.create_user(username="hook_user", password="pw")
    participant = Participant.objects.create(user=user)
    job = Job.objects.create(participant=participant, description="hook capacity probe")

    # Under-limit lists (their joined strings are below limits)
    uni_list_ok = build_ngrams(1, 160)   # < 200 when joined
    bi_list_ok  = build_ngrams(2, 450)   # < 500
    tri_list_ok = build_ngrams(3, 750)   # < 800

    analysis_ok = {"unigram": uni_list_ok, "bigram": bi_list_ok, "trigram": tri_list_ok}

    # Should NOT raise
    hook_after_jd_analysis(job.id, analysis_ok)
    assert KeywordAnalysis.objects.filter(job=job).exists()

    # Over-limit bigram (joined > 500)
    bi_list_long = build_ngrams(2, 520)
    analysis_bi_long = {"unigram": uni_list_ok, "bigram": bi_list_long, "trigram": tri_list_ok}

    with pytest.raises(DataError):
        with transaction.atomic():
            hook_after_jd_analysis(job.id, analysis_bi_long)

    # Over-limit trigram (joined > 800)
    tri_list_long = build_ngrams(3, 820)
    analysis_tri_long = {"unigram": uni_list_ok, "bigram": bi_list_ok, "trigram": tri_list_long}

    with pytest.raises(DataError):
        with transaction.atomic():
            hook_after_jd_analysis(job.id, analysis_tri_long)
