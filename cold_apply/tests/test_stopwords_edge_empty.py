# cold_apply/tests/test_stopwords_edge_empty.py
import re
import pytest
from cold_apply.models import StopwordGroup

@pytest.mark.django_db
def test_empty_stopword_group_yields_empty_set():
    g, _ = StopwordGroup.objects.get_or_create(
        category="nltk english stopwords",
        defaults={"words": ""},  # empty CSV
    )
    # simple, explicit CSV -> set normalizer used by analyzer
    tokens = {t for t in (w.strip().lower() for w in g.words.split(",")) if t}
    assert tokens == set()
