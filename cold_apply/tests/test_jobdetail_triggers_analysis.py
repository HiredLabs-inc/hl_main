import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from cold_apply.models import (
    Participant, Organization, Position, Job,
    StopwordGroup, KeywordAnalysis,
)

@pytest.mark.django_db
def test_job_detail_auto_triggers_analysis(client):
    # seed stopwords for all categories expected by analyze()
    payload = {
        "nltk english stopwords": "the, and, of, to, in",
        "low value": "responsible, various, ability",
        "industry protected": "google, microsoft",
    }
    for k, v in payload.items():
        StopwordGroup.objects.create(category=k, words=v)

    # minimal graph
    User = get_user_model()
    u = User.objects.create_user(username="u", password="p")
    p = Participant.objects.create(user=u)
    org = Organization.objects.create(name="Org")
    pos = Position.objects.create(title="Jr NLP/ML Engineer")
    job = Job.objects.create(
        participant=p, company=org, title=pos,
        description="Build NLP models, tokenize text, train classifiers, deploy services.",
    )

    client.force_login(u)
    url = reverse("cold_apply:job_detail", args=[job.id])
    resp = client.get(url)
    assert resp.status_code == 200
    assert KeywordAnalysis.objects.filter(job=job).exists()
