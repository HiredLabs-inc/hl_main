from urllib.parse import urlencode
from django import template
from django import forms

register = template.Library()


@register.filter
def error_class(bound_field, class_names):
    # relies on Alpine.js
    if hasattr(bound_field, "errors") and bound_field.errors:
        bound_field.field.widget.attrs[":class"] = f"touched || '{class_names}'"
        bound_field.field.widget.attrs["@input"] = "touched=true;"
    return bound_field


@register.filter
def bootstrap_input(bound_field):
    if isinstance(bound_field.field.widget, forms.Select):
        bound_field.field.widget.attrs["class"] = "form-select"
    elif isinstance(bound_field.field.widget, forms.CheckboxInput):
        pass

    else:
        bound_field.field.widget.attrs["class"] = "form-control"
    return bound_field


@register.filter
def input_class(bound_field, class_name):
    bound_field.field.widget.attrs["class"] = class_name
    return bound_field


@register.filter
def input_attrs(bound_field, attrs):
    attributes = attrs.split(",")
    for attribute in attributes:
        name, value = attribute.split(":")
        bound_field.field.widget.attrs[name.strip()] = value.strip()
    return bound_field


@register.filter
def input_styles(bound_field, styles):
    bound_field.field.widget.attrs["style"] = styles
    return bound_field


@register.filter
def print_value(a):
    print(a.__dict__)


@register.filter
def add_wrapper_attributes(bound_field, attrs):
    attributes = attrs.split(",")

    wrapper_attrs = {}
    for attribute in attributes:
        name, value = attribute.split(":")
        wrapper_attrs[name.strip()] = value.strip()
    bound_field.field.widget.wrapper_attrs = wrapper_attrs

    return bound_field


@register.filter
def add_attributes(bound_field, attrs):
    attributes = attrs.split(",")
    for attribute in attributes:
        name, value = attribute.split(":")
        bound_field.field.widget.attrs[name.strip()] = value.strip()
    return bound_field


@register.filter()
def dict_key(d, k):
    """Returns the given key from a dictionary."""
    return d.get(k)


@register.filter()
def urlencode_dict(query_params):
    return urlencode(dict(query_params), doseq=True)