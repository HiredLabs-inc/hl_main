import json

from django.db import models
from django.template.loader import render_to_string
from playwright.sync_api import sync_playwright


class ResumeFormatChoices(models.TextChoices):
    CHRONOLOGICAL = "chronological", "Chronological Work Experience"
    SKILLS = "skills", "Top Skills"


class ResumeSections(models.TextChoices):
    """Sections that can be configured in a resume"""

    OVERVIEW = "overview"
    # BULLETS = "bullets"
    EDUCATION = "education"
    SKILLS = "skills"
    AWARDS = "awards"


class ResumeCoreTemplates(models.TextChoices):
    """Values correspond to resume/templates/resume/resume_{choice_value}.html"""

    STANDARD = "standard"
    CORAL = "coral"
    ARIAL = "arial"
    MODERN_WRITER = "modern_writer"
    SWISS = "swiss"
    SERIFF = "seriff"


class ResumeExploratoryTemplates(models.TextChoices):
    """Values correspond to resume/templates/resume/resume_{choice_value}.html"""

    SIMPLE_RED = "simple_red"
    SPEARMINT = "spearmint"
    STEELY = "steely"
    NO_NONSENSE = "no_nonsense"
    BUSINESS_MINDED = "business_minded"


RESUME_TEMPLATE_SECTIONS = {
    ResumeCoreTemplates.STANDARD: [
        ResumeSections.OVERVIEW,
        ResumeSections.EDUCATION,
        ResumeSections.SKILLS,
        ResumeSections.AWARDS,
    ],
    ResumeCoreTemplates.CORAL: [
        ResumeSections.OVERVIEW,
        ResumeSections.EDUCATION,
        ResumeSections.SKILLS,
        ResumeSections.AWARDS,
    ],
    ResumeCoreTemplates.ARIAL: [
        ResumeSections.OVERVIEW,
        ResumeSections.EDUCATION,
    ],
    ResumeCoreTemplates.MODERN_WRITER: [
        ResumeSections.OVERVIEW,
        ResumeSections.EDUCATION,
        ResumeSections.SKILLS,
        ResumeSections.AWARDS,
    ],
    ResumeCoreTemplates.SWISS: [
        ResumeSections.OVERVIEW,
        ResumeSections.EDUCATION,
        ResumeSections.SKILLS,
        ResumeSections.AWARDS,
    ],
    ResumeCoreTemplates.SERIFF: [
        ResumeSections.OVERVIEW,
        ResumeSections.EDUCATION,
        ResumeSections.SKILLS,
        ResumeSections.AWARDS,
    ],
}


RESUME_TEMPLATE_SECTIONS_JSON = json.dumps(RESUME_TEMPLATE_SECTIONS)


def write_template_to_pdf(request, template_name, context):
    html_content = render_to_string(template_name, context=context)
    base_url = request.build_absolute_uri("/")
    return write_html_to_pdf(base_url, html_content)


def write_html_to_pdf(base_url, html_content):
    """Generates a PDF from html string and returns it as a buffer.

    Launches a headless chromimum browser, sets the page content to the html string then
    uses the browser to write to a pdf

    :param request: django request object
    :param html_content: HTML string
    :returns PDF buffer

    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        # in order to let chromimum make requests for css e.g
        # <link href={% static 'styles/style.css' %}>
        # need to add a <base href={request.build_absolute_uri("/")} /> element in the html
        # playwright seems to ignore any relative links otherwise

        base_tag = f'<base href="{base_url}">'

        page.set_content(base_tag + html_content)
        page.wait_for_load_state("networkidle")

        return page.pdf(print_background=True)
