from django import template

from userprofile.guards import is_participant as _is_participant
from userprofile.guards import is_volunteer as _is_volunteer

register = template.Library()


@register.filter
def is_volunteer(user):
    """{% if someone|is_volunteer %}; prefetch groups when looping over people"""
    return user is not None and _is_volunteer(user)


@register.filter
def is_participant(user):
    return user is not None and _is_participant(user)
