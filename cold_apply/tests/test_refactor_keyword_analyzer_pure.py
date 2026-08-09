from cold_apply.static.scripts.keyword_analyzer import keyword_analyzer as ka


def test_refactor_analyze_pure_payload():
    out = ka.analyze("alpha beta beta gamma", stopwords=["gamma"])
    assert set(out.keys()) == {"unigram", "bigram", "trigram"}
    assert isinstance(out["unigram"], list)
    assert isinstance(out["bigram"], list)
    assert isinstance(out["trigram"], list)
    assert "gamma" not in out["unigram"]


def test_refactor_analyze_uses_flat_stopwords():
    text = "A quick brown fox jumps over the lazy dog"
    flat = ["a", "the", "over", "lazy"]
    out = ka.analyze(text, stopwords=flat)
    assert "a" not in out["unigram"]
    assert "the" not in out["unigram"]
