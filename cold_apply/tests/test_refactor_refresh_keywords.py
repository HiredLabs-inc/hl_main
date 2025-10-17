import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from cold_apply.models import Job, KeywordAnalysis


@pytest.mark.django_db
def test_refactor_refresh_keywords_deletes_row(client):
    job = Job.objects.create(description="text")
    old = KeywordAnalysis.objects.create(job=job, unigram="old", bigram="", trigram="")

    # login
    User = get_user_model()
    user = User.objects.create_user(username="u3", password="pw")
    client.force_login(user)

    resp = client.post(reverse("cold_apply:refresh_keywords", args=[job.pk]))
    assert resp.status_code in (200, 302)

    # current implementation deletes and redirects; no row should remain
    assert not KeywordAnalysis.objects.filter(job=job).exists()
