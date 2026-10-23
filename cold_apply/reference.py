"""Rules for shared reference data: companies, titles, concentrations and locations.

Participants pick these on their own Experience, Education and Job forms, and add
new ones when theirs is missing (BUG-030). The person who added a row can edit or
delete it while nobody else's records use it; staff can edit any row and delete
any unused one. Deleting a row in use is never allowed: the resume foreign keys
are PROTECT, and the pages refuse first with a count.
"""
from dataclasses import dataclass

from django.db.models import Count

from cold_apply.models import Location
from resume.models import Concentration, Organization, Position


@dataclass(frozen=True)
class Kind:
    slug: str
    model: type
    label: str
    fields: tuple
    # Compared case-insensitively; the rest of match_fields must be equal
    text_field: str
    match_fields: tuple


KINDS = {
    kind.slug: kind
    for kind in (
        Kind("companies", Organization, "Companies", ("name", "website", "org_type"), "name", ("name",)),
        Kind("titles", Position, "Titles", ("title",), "title", ("title",)),
        Kind("concentrations", Concentration, "Concentrations", ("name",), "name", ("name",)),
        Kind("locations", Location, "Locations", ("city", "state", "country"), "city", ("city", "state", "country")),
    )
}


def kind_for(model):
    return next(kind for kind in KINDS.values() if kind.model is model)


def find_existing(model, values, exclude_pk=None):
    """The row that already has these values, ignoring case in its name"""
    kind = kind_for(model)
    lookup = {
        (f"{field}__iexact" if field == kind.text_field else field): values.get(field)
        for field in kind.match_fields
    }
    return model.objects.filter(**lookup).exclude(pk=exclude_pk).first()


def _related(model):
    """(model, field name) for every foreign key that points at model"""
    for rel in model._meta.related_objects:
        if rel.one_to_many or rel.one_to_one:
            yield rel.related_model, rel.field.name


def usage(objs, user=None):
    """{pk: (records using it, how many of those aren't user's own)} for objs,
    one or two grouped queries per foreign key. Records with no participant (an
    owner we can't check) count as someone else's. Without a user, only the
    first count is filled."""
    objs = list(objs)
    counts = {obj.pk: [0, 0] for obj in objs}
    if not objs:
        return {}
    for model, field in _related(type(objs[0])):
        rows = model.objects.filter(**{f"{field}__in": counts})
        querysets = [rows]
        if user is not None:
            has_owner = any(f.name == "participant" for f in model._meta.fields)
            querysets.append(rows.exclude(participant__user=user) if has_owner else rows)
        for i, queryset in enumerate(querysets):
            # order_by() so a model's default ordering doesn't split the groups
            for pk, n in queryset.order_by().values(field).annotate(n=Count("pk")).values_list(field, "n"):
                counts[pk][i] += n
    return {pk: tuple(n) for pk, n in counts.items()}


def uses(obj):
    """How many records point at obj"""
    return usage([obj])[obj.pk][0]


def visible(model, user):
    """Rows the user can list: staff see all, participants what they added"""
    if user.is_staff:
        return model.objects.all()
    return model.objects.filter(created_by=user)


def can_edit(user, obj, used=None):
    """used is obj's usage() entry, when the caller already has it"""
    if user.is_staff:
        return True
    _, others = used or usage([obj], user)[obj.pk]
    # Renaming changes the row on every resume that uses it
    return obj.created_by_id == user.pk and not others


def can_delete(user, obj, used=None):
    total, _ = used or usage([obj], user)[obj.pk]
    return (user.is_staff or obj.created_by_id == user.pk) and not total
