from urllib.parse import urlencode
from django import template
from django.template.context import Context as Context
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.template.loader_tags import BlockNode
from regex import F

register = template.Library()


@register.simple_tag
def breadcrumb(text, *args, **kwargs):
    """{% breadcrumb "text" url arg1 arg2 kwarg1='value' %}}"""
    url, *rest_args = args or [""]
    href = reverse(url, args=rest_args, kwargs=kwargs) if url else None

    return mark_safe(render_to_string("breadcrumb.html", {"href": href, "text": text}))


@register.tag
def wrapper_if_block_has_content(parser, token):
    """
    simple tag to wrap a block in some html if it has content otherwise render nothing

    What's the point?
    It allows child templates to add just the content of a block without having
    to worry about the surrounding html layout. In the example below, a child template
    only has to define the "breadcrumbs" block without having to worry about
    the the nav, ol and hr tags that are required around the breadcrumbs. By rendering
    nothing if the block content is empty, you don't end up with an empty breadcrumbs bar
    on pages that do not have breadcrumbs defined.

    Using block.super wont work because the parent template can't conditionally
    render based on the content of the child templates, and you can't put content
    inside a block.super tag.

    example:
    This will only render the nav, ol and hr if the "breadcrumbs" block has content
    {% wrapper_if_block_has_content breadcrumbs %}
        <nav style="--bs-breadcrumb-divider: '>';" aria-label="breadcrumb">
            <ol class="breadcrumb">
                {% block breadcrumbs %}
                    {% breadcrumb 'Pipeline' %}
                {% endblock breadcrumbs %}
            </ol>
        </nav>
        <hr>
    {% endwrapper %}

    This will render nothing as the "breadcrumbs" block has no content
    {% wrapper_if_block_has_content breadcrumbs %}
        <nav style="--bs-breadcrumb-divider: '>';" aria-label="breadcrumb">
            <ol class="breadcrumb">
                {% block breadcrumbs %}
                {% endblock breadcrumbs %}
            </ol>
        </nav>
        <hr>
    {% endwrapper %}
    """
    tag_name, wrapped_block_name = token.contents.split(None, 1)

    nodelist = parser.parse(("endwrapper",))

    wrapped_block = None
    for i, node in enumerate(nodelist):
        if isinstance(node, BlockNode) and node.name == wrapped_block_name:
            wrapped_block = nodelist[i]

    parser.delete_first_token()

    return WrapperNode(nodelist, wrapped_block)


class WrapperNode(template.Node):
    def __init__(self, nodelist, wrapped_block):
        self.nodelist = nodelist
        self.wrapped_block = wrapped_block

    def render(self, context):
        wrapped_block_rendered = self.wrapped_block.render(context)
        wrapped_block_has_content = wrapped_block_rendered.strip()
        if wrapped_block_has_content:
            return self.nodelist.render(context)
        return ""
