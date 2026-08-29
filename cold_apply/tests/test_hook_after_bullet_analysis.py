from datetime import date
import pytest
from django.contrib.auth import get_user_model

from cold_apply.models import Participant, BulletKeyword
from resume.models import (
    Organization,
    Experience,
    Position,
    Bullet,
)
from cold_apply.static.scripts.keyword_analyzer.keyword_analyzer import hook_after_bullet_analysis


@pytest.mark.django_db
def test_hook_after_bullet_analysis_creates_and_replaces_rows():
    """
    Directly exercise hook_after_bullet_analysis(bullet_id, items) in isolation,
    ensuring it creates BulletKeyword rows from a list of dict items and
    replaces existing rows on subsequent calls.
    """
    # --- minimal participant setup ---
    User = get_user_model()
    user = User.objects.create_user(username="bk_user", password="pw")
    p = Participant.objects.create(user=user)

    # --- organization, position, and experience ---
    org = Organization.objects.create(name="ACME Corp", website="example.com")
    pos = Position.objects.create(title="Engineer")
    exp = Experience.objects.create(
        participant=p,
        org=org,                # FK → Organization
        position=pos,           # FK → Position
        start_date=date(2020, 1, 1),
    )

    # --- bullet tied to experience ---
    bullet = Bullet.objects.create(experience=exp, text="did a thing", type="Work")

    # --- first items payload (list of dicts) ---
    items_v1 = [
        {"unigram": "x", "bigram": "y z", "trigram": "a b c"},
        {"unigram": "m", "bigram": "", "trigram": ""},
    ]
    hook_after_bullet_analysis(bullet.id, items_v1)

    # --- verify initial creation ---
    rows = list(BulletKeyword.objects.filter(bullet=bullet).order_by("id"))
    assert len(rows) == 2
    assert rows[0].unigram == "x"
    assert rows[0].bigram == "y z"
    assert rows[0].trigram == "a b c"
    assert rows[1].unigram == "m"
    assert rows[1].bigram == ""
    assert rows[1].trigram == ""

    # --- second payload: should replace, not append ---
    items_v2 = [{"unigram": "u", "bigram": "v w", "trigram": ""}]
    hook_after_bullet_analysis(bullet.id, items_v2)

    # --- verify replacement ---
    rows = list(BulletKeyword.objects.filter(bullet=bullet))
    assert len(rows) == 1
    assert rows[0].unigram == "u"
    assert rows[0].bigram == "v w"
    assert rows[0].trigram == ""
