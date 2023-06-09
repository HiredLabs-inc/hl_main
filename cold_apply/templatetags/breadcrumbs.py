from urllib.parse import urlencode
from django import template
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def breadcrumb(text, *args, **kwargs):
    """{% breadcrumb "text" url arg1 arg2 kwarg1='value' %}}"""
    url, *rest_args = args or [""]
    href = reverse(url, args=rest_args, kwargs=kwargs) if url else None

    return mark_safe(render_to_string("breadcrumb.html", {"href": href, "text": text}))
