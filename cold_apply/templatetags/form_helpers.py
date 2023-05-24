from django import template

register = template.Library()


@register.filter
def error_class(bound_field, class_name):

    # relies on Alpine.js
    if hasattr(bound_field, 'errors') and bound_field.errors:

        bound_field.field.widget.attrs['class'] = class_name
        bound_field.field.widget.attrs[':class'] = "{'input-invalid': !touched}"
        bound_field.field.widget.attrs['@input'] = "touched=true;"
    return bound_field


@register.filter
def input_class(bound_field, class_name):

    bound_field.field.widget.attrs['class'] = class_name
    return bound_field


@register.filter
def input_styles(bound_field, styles):
    bound_field.field.widget.attrs['style'] = styles
    return bound_field

