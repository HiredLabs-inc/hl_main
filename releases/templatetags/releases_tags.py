from django import template

from releases.models import App

register = template.Library()


@register.simple_tag
def release_apps():
    """Apps with release notes, for the staff nav"""
    return App.objects.order_by("name")
