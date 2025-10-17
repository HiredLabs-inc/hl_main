import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from cold_apply.models import Job, StopwordGroup, KeywordAnalysis, Participant


def _normalize(words):
    return sorted({w.strip().lower() for w in words if w and w.strip()})


@pytest.mark.django_db
def test_refactor_jobdetail_flattens_and_creates_single_row(monkeypatch, client):
    StopwordGroup.objects.create(category="nltk english stopwords", words="a, an , the")
    StopwordGroup.objects.create(category="low value", words="detail-oriented, results")
    job = Job.objects.create(description="a detail-oriented engineer builds results")

    User = get_user_model()
    user = User.objects.create_user(username="u1", password="pw")
    participant = Participant.objects.create(user=user)
    job = Job.objects.create(description="a detail-oriented engineer builds results", participant=participant)
    client.force_login(user)

    seen = {}

    def fake_analyze(text, **kwargs):
        seen["text"] = text
        if "stopwords" in kwargs and kwargs["stopwords"] is not None:
            seen["stopwords"] = _normalize(kwargs["stopwords"])
        elif "stopwords_by_category" in kwargs and kwargs["stopwords_by_category"] is not None:
            flat = []
            for lst in kwargs["stopwords_by_category"].values():
                flat.extend(lst)
            seen["stopwords"] = _normalize(flat)
        else:
            seen["stopwords"] = []
        return {"unigram": ["x"], "bigram": [], "trigram": []}

    monkeypatch.setattr("cold_apply.views.analyze", fake_analyze, raising=True)

    resp = client.get(reverse("cold_apply:job_detail", args=[job.pk]))
    assert resp.status_code in (200, 302)
    assert seen["text"] == job.description
    assert seen["stopwords"] == ["a", "an", "detail-oriented", "results", "the"]

    qa = KeywordAnalysis.objects.get(job=job)
    assert qa.unigram == "x"
    assert not hasattr(qa, "category")


@pytest.mark.django_db
def test_refactor_jobdetail_handles_missing_groups(monkeypatch, client):
    job = Job.objects.create(description="hello world")

    User = get_user_model()
    user = User.objects.create_user(username="u2", password="pw")
    participant = Participant.objects.create(user=user)
    job = Job.objects.create(description="hello world", participant=participant)
    client.force_login(user)

    called = {}

    def fake_analyze(text, **kwargs):
        if "stopwords" in kwargs and kwargs["stopwords"] is not None:
            called["stopwords"] = list(kwargs["stopwords"])
        elif "stopwords_by_category" in kwargs and kwargs["stopwords_by_category"] is not None:
            flat = []
            for lst in kwargs["stopwords_by_category"].values():
                flat.extend(lst)
            called["stopwords"] = _normalize(flat)
        else:
            called["stopwords"] = []
        return {"unigram": ["hello", "world"], "bigram": [], "trigram": []}

    monkeypatch.setattr("cold_apply.views.analyze", fake_analyze, raising=True)

    resp = client.get(reverse("cold_apply:job_detail", args=[job.pk]))
    assert resp.status_code in (200, 302)
    assert called["stopwords"] == []
