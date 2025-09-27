import pytest
pytest.importorskip("sklearn")

from cold_apply.static.scripts.keyword_analyzer.keyword_analyzer import analyze

def test_analyze_runs_without_db_access_now_pure():
    STOPWORDS = {
        "nltk english stopwords": ["the", "and", "of", "to", "in"],
        "low value": ["responsible", "various", "ability"],
        "industry protected": ["google", "microsoft"],
    }
    result = analyze("Simple text with no dependency on DB.", stopwords_by_category=STOPWORDS)
    assert set(result.keys()) == {
        "nltk english stopwords",
        "low value",
        "industry protected",
    }
    for cat in result:
        for ngram_type in ("unigram", "bigram", "trigram"):
            assert isinstance(result[cat][ngram_type], list)
