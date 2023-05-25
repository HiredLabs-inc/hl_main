from datetime import timedelta
from django.utils import timezone


def group_bullets_by_skill(weighted_bullets, skills, cutoff=5):
    bullets_list = list(weighted_bullets)
    skill_list = [{"obj": skill, "bullets": []} for skill in skills]

    for skill in skill_list:
        picked = []
        remaining = []
        count = 0
        for bullet in bullets_list:
            if skill["obj"] in bullet.bullet.skills.all():
                picked.append(bullet)
                count += 1
            else:
                remaining.append(bullet)

            if count == 5:
                break

        skill["bullets"] = picked
        bullets_list = remaining

    return skill_list


def group_bullets_by_experience(weighted_bullets, cutoff=5):
    # build a list of dicts like this: [{"obj": Experience, "bullets": [WeightedBullets]}]
    # to iterate over in the resume template.

    experiences = {}
    for bullet in weighted_bullets:
        experience = bullet.bullet.experience
        entry = experiences.setdefault(
            experience.id, {"obj": experience, "bullets": []}
        )
        entry["bullets"].append(bullet)

    five_years_ago = (timezone.now() - timedelta(weeks=260)).date()
    ten_years_ago = (timezone.now() - timedelta(weeks=520)).date()

    for exp in experiences.values():
        cutoff = 1

        if exp["obj"].end_date is None:
            cutoff = 5
        elif exp["obj"].end_date > five_years_ago:
            cutoff = 5
        elif exp["obj"].end_date > ten_years_ago:
            cutoff = 3
        exp["bullets"] = exp["bullets"][:cutoff]

    return experiences.values()
