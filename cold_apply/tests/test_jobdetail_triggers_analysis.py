import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from cold_apply.models import Participant, Job


@pytest.mark.django_db
def test_job_detail_triggers_jd_analysis(monkeypatch, client):
    """
    Visiting the job detail should call analyze() and then hook_after_jd_analysis(job_id, result).
    This stays focused on the JD path only.
    """
    # user -> participant -> job
    User = get_user_model()
    user = User.objects.create_user(username="jd_user", password="pw")
    participant = Participant.objects.create(user=user)
    job = Job.objects.create(description="a detail-oriented engineer builds results",
                             participant=participant)

    # make sure we're logged in
    client.force_login(user)

    # fake analyzer output
    fake_result = {"unigram": ["x"], "bigram": [], "trigram": []}

    # monkeypatch analyze (pure, deterministic)
    def fake_analyze(text, **kwargs):
        return fake_result

    # spy on hook_after_jd_analysis
    called = {}
    def fake_hook_after_jd_analysis(job_id, result):
        # NOTE: some code calls (analysis, job_id) or (job_id, analysis).
        # Adjust the order below to match refactor. If your view calls
        # hook_after_jd_analysis(analysis, job_id), keep this arg order.
        called["job_id"] = job_id
        called["result"] = result

    monkeypatch.setattr("cold_apply.views.analyze", fake_analyze, raising=True)
    monkeypatch.setattr("cold_apply.views.hook_after_jd_analysis", fake_hook_after_jd_analysis, raising=True)

    # hit the page
    resp = client.get(reverse("cold_apply:job_detail", args=[job.pk]))

    # sanity: page rendered
    assert resp.status_code == 200

    # assert hook was called with expected payload + job id
    assert called["job_id"] == job.id
    assert called["result"] == fake_result
