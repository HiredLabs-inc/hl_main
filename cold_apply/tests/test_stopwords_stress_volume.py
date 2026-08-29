# cold_apply/tests/test_stopwords_stress_volume.py
import pytest, string
from cold_apply.models import StopwordGroup

def make_tokens(n=100_000):
    # deterministic short tokens to keep payload size realistic
    base = [f"w{x}" for x in range(n)]
    return ", ".join(base)

@pytest.mark.django_db
def test_stopwordgroup_parsing_100k_tokens(benchmark):
    csv = make_tokens()
    g = StopwordGroup.objects.create(
        category="nltk english stopwords",
        words=csv
    )

    def parse():
        return {t for t in (w.strip().lower() for w in g.words.split(",")) if t}

    tokens = benchmark(parse)  # pytest-benchmark
    assert len(tokens) == 100_000
