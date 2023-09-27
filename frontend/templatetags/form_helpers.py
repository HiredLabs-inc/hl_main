from urllib.parse import urlencode

from django import forms, template

register = template.Library()


@register.filter
def error_class(bound_field, class_names):
    # relies on Alpine.js

    attrs = bound_field.field.widget.attrs
    if hasattr(bound_field, "errors") and bound_field.errors:
        attrs[":class"] = f"{{'{class_names}': !touched}}"
        attrs["class"] = (attrs.get("class", "") + " " + class_names).strip()
        attrs["@input"] = "touched=true;"
    return bound_field


@register.filter
def bootstrap_input(bound_field):
    if isinstance(bound_field.field.widget, forms.Select):
        bound_field.field.widget.attrs["class"] = "form-select"
    elif (
        isinstance(bound_field.field.widget, forms.CheckboxInput)
        or isinstance(bound_field.field.widget, forms.CheckboxSelectMultiple)
        or isinstance(bound_field.field.widget, forms.RadioSelect)
    ):
        pass

    else:
        bound_field.field.widget.attrs["class"] = "form-control"
    return bound_field


@register.filter
def input_class(bound_field, class_name):
    attrs = bound_field.field.widget.attrs
    attrs["class"] = attrs.get("class", "") + " " + class_name
    return bound_field


@register.filter
def input_attrs(bound_field, attrs):
    if attrs:
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
