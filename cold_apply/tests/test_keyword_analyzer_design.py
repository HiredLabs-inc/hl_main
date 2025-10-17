import pytest
pytest.importorskip("sklearn")

from cold_apply.static.scripts.keyword_analyzer.keyword_analyzer import analyze

def test_analyze_runs_without_db_access_now_pure():
    STOPWORDS = {
        "nltk english stopwords": ["the", "and", "of", "to", "in"],
        "low value": ["responsible", "various", "ability"],
        "industry protected": ["google", "microsoft"],
    }
    flat = sorted({w for lst in STOPWORDS.values() for w in lst})
    result = analyze("Simple text with no dependency on DB.", stopwords=flat)
    assert set(result.keys()) == {"unigram", "bigram", "trigram"}
    # sanity: stopwords should not appear
    for sw in flat:
        assert sw not in result["unigram"]
        assert sw not in result["bigram"]
        assert sw not in result["trigram"]
    for ngram_type, values in result.items():
        assert ngram_type in {"unigram", "bigram", "trigram"}
        assert isinstance(values, list)
