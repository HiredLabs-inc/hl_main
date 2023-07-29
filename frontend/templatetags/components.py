from django import template
from django.template.base import VariableNode, token_kwargs
from django.template.context import Context
from django.template.loader_tags import BlockNode, IncludeNode, construct_relative_path

register = template.Library()


@register.tag
def section(parser, token):
    """
    Usage:
        {% component %}
            {% section "body" %}
                <p>My content</p>
            {% endsection %}
        {% endcomponent %}
    """
    bits = token.split_contents()

    nodelist = parser.parse(("endsection",))

    parser.delete_first_token()

    return SectionNode(nodelist, name=bits[1])


class SectionNode(template.Node):
    def __init__(self, nodelist, name):
        self.nodelist = nodelist
        self.name = name

    def render(self, context):
        return self.nodelist.render(context)


@register.tag
def component(parser, token):
    """
    # cards/card.html
    <h1>Card</h1>
    <div>
        {{body}}
    </div>
    <h2>Footer</h2>
    {{footer}}

    Usage:
        {% component "card" title="My Title" %}
            <p>My content</p>
            {% section footer %}
            {% endsection %}
        {% endcomponent %}

    Any content outside of a section will be rendered in the body section.
    """
    bits = token.split_contents()
    _, template_name, *kwargs = bits
    kwargs = token_kwargs(kwargs, parser)

    nodelist = parser.parse(("endcomponent",))

    parser.delete_first_token()

    template_name = construct_relative_path(parser.origin.template_name, bits[1])
    sections = [(node.name, node) for node in nodelist if isinstance(node, SectionNode)]
    if sections:
        nodelist[:] = [node for node in nodelist if not isinstance(node, SectionNode)]
    return ComponentNode(
        nodelist,
        sections,
        parser.compile_filter(template_name),
        extra_context=kwargs,
    )


class ComponentNode(IncludeNode):
    def __init__(self, nodelist, sections, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nodelist = nodelist
        self.sections = sections

    def render(self, context):
        """construct a seperate context isolated to the component"""
        extra = {name: var.resolve(context) for name, var in self.extra_context.items()}
        extra["body"] = self.nodelist.render(context)

        for section in self.sections:
            extra.update({section[0]: section[1].render(context)})

        with context.push(extra):
            return super().render(context)


@register.tag
def wrapper(parser, token):
    """Wraps a variable node e.g {{footer}} with some html.
    Usage:
        {% wrapper %}
            <h1>Footer</h1>
            {{footer}}
        {% endwrapper}
    Will only render the h1 if the {{footer}} node has content
    """
    if len(token.split_contents()) != 2:
        raise template.TemplateSyntaxError(
            f"{token.contents.split()[0]} tag requires a single argument"
        )
    _, target_var_name = token.split_contents()

    nodelist = parser.parse(("endwrapper",))

    variable_node = [
        node
        for node in nodelist
        if (
            isinstance(node, VariableNode)
            and node.filter_expression.token == target_var_name
        )
        or (isinstance(node, BlockNode) and node.name == target_var_name)
    ]
    if variable_node:
        variable_node = variable_node[0]

    parser.delete_first_token()

    return WrapperNode(nodelist, variable_node)


class WrapperNode(template.Node):
    def __init__(self, nodelist, variable_node, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nodelist = nodelist
        self.variable_node = variable_node

    def render(self, context):
        if self.variable_node and self.variable_node.render(context).strip():
            return self.nodelist.render(context)

        return ""
