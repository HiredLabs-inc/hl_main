import cold_apply.static.scripts.keyword_analyzer.keyword_analyzer as ka

def _csv_to_list(csv: str):
    return [w.strip() for w in csv.split(",") if w.strip()]

def test_parse_removes_punctuation_and_stopwords():
    text = "Hello, world! And hello again; world and more."
    stopwords_csv = "and, the, or"
    a = ka.Analyzer(text, stopwords=_csv_to_list(stopwords_csv))
    cleaned = a.cleaned_words
    assert "hello" in cleaned and "world" in cleaned and "again" in cleaned and "more" in cleaned
    for sw in _csv_to_list(stopwords_csv):
        assert sw not in cleaned
    assert all(tok.islower() for tok in cleaned)

def test_parse_case_normalization_only_stopword_is_removed():
    text = "Python, pythonic; PYTHON!"
    stopwords_csv = "pythonic"
    a = ka.Analyzer(text, stopwords=_csv_to_list(stopwords_csv))
    cleaned = a.cleaned_words
    # "pythonic" removed; "python" tokens remain (lowercased, punctuation stripped)
    assert "pythonic" not in cleaned
    assert cleaned.count("python") >= 1

def test_find_keywords_shapes():
    text = (
        "Data science uses data analysis and data engineering. "
        "Engineering supports analysis and modeling."
    )
    a = ka.Analyzer(text, stopwords=["and", "the", "or"])
    uni = a.find_keywords(1, 1)
    bi = a.find_keywords(2, 2)
    tri = a.find_keywords(3, 3)
    assert isinstance(uni, list) and isinstance(bi, list) and isinstance(tri, list)
    assert len(uni) <= 20 and len(bi) <= 20 and len(tri) <= 20
    assert all(isinstance(x, str) for x in uni + bi + tri)
