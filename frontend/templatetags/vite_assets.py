import json
import os
from time import sleep

from django import template
from django.apps import apps
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


def get_manifest():
    if settings.DEBUG:
        # stall while vite is rewriting the manifest
        count = 0
        while not os.path.exists("frontend/build/manifest.json"):
            sleep(0.01)
            count += 1
            if count == 500:
                raise Exception("frontend build failed, manifest.json not found")
            print("waiting for manifest.json to be created")
    with open("frontend/build/manifest.json") as manifest_file:
        return json.load(manifest_file)


def prepend_app_dirs(file_name):
    # if file_name starts with an app name, add app_name/templates/app_name
    # to mimic django's app_dirs behaviour when finding assets
    # so you can use {% load_vite_js 'orders/something.js'%}
    # rather than {% loadi_vite_js 'orders/templates/orders/something.js' %}
    split_name = file_name.split("/")
    prefix = split_name[0]
    app_names = [config.name for config in apps.get_app_configs()]
    if prefix in app_names:
        split_name[0] = f"{prefix}/templates/{prefix}"
        return "/".join(split_name)
    return file_name


@register.simple_tag
def get_static_name(file_name):
    return "/" + mark_safe(get_manifest().get(file_name)["file"])


@register.simple_tag
def load_vite_js(file_name):
    found = get_manifest().get(file_name)

    if found:
        src = found["file"]
        tag = f'<script type="module" src="/{src}" ></script>'

        css_list = found.get("css", [])
        if css_list:
            css_tags = []
            for css in css_list:
                css_tags.append(f'<link rel="stylesheet" href="/{css}"/>')

            tag = "\n".join([tag, *css_tags])

        return mark_safe(tag)

    print(f"vite file not found for {file_name}")
    return ""


@register.simple_tag
def load_vite_css(file_name):
    found = get_manifest().get(file_name)
    if found:
        href = found["file"]
        tag = f'<link rel="stylesheet" href="/{href}"/>'
        return mark_safe(tag)

    return ""
