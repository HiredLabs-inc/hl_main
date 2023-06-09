from datetime import datetime, timedelta
from pprint import pprint
from time import sleep
from urllib.parse import parse_qs, urlparse
from django.db import models
from django.core.management.base import BaseCommand, CommandError
from playwright.sync_api import sync_playwright
from django.utils import timezone
from django_q.tasks import async_task

from cold_apply.models import Job, Participant
from resume.models import Organization, Position


chip_params = {
    "date_posted": ["3days"],
    "job_family_1": ["senior"],
}


# CSS selectors used to find elements in the page
JOB_LIST_ITEM_SELECTOR = ".iFjolb"
JOB_TEXT_SELECTOR = "span.HBvzbc"

# SVG paths used to identify a tag's details
SALARY_SVG_PATH = "M2 5v14h20V5H2zm18 12H4V7h16v10zm-5-5.25c1.03 0 1.87-.84 1.87-1.88S16.03 8 15 8s-1.88.84-1.88 1.88.85 1.87 1.88 1.87zm0 .5c-1.34 0-4 .69-4 2.06V16h8v-1.69c0-1.37-2.66-2.06-4-2.06z"
HOURS_SVG_PATH = "M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z"
TIME_POSTED_SVG_PATH = "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"
WORK_FROM_HOME_PATH = "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"


class DatePostedFilter(models.Choices):
    TODAY = "today"
    THREE_DAYS = "3days"
    WEEK = "week"
    MONTH = "month"
    ALL = "all"


def get_jobs_from_google(main_query: str, chip_filters=None, limit=25):
    limit = limit if limit < 25 else 25

    jobs = []
    with sync_playwright() as playwright:
        # set headless=False to see the browser running
        browser = playwright.chromium.launch(headless=False)

        context = browser.new_context()
        context.add_cookies(
            [
                {
                    "name": "CONSENT",
                    "value": "YES+",
                    "domain": ".google.com",
                    "path": "/",
                }
            ]
        )
        page = context.new_page()
        jobs_url = get_job_url(main_query, chip_filters)
        page.goto(jobs_url)
        # sleep(20000)
        page.wait_for_load_state("networkidle")

        # this is the right hand side content box
        main_content = page.locator("#tl_ditc").first

        # these are the jobs listed on the left hand side
        for i in range(limit):
            # page uses infinite scroll so we can't just loop through the list
            # we need to update the job list every time and get the item by index
            job_list = page.locator(".iFjolb").all()
            li = job_list[i]
            if not li:
                break
            # loop through each job and click on it's link
            # this updates the main content with the job's details
            # then we can scrape the details from the main content

            li.click()
            page.wait_for_load_state("networkidle")
            sleep(0.5)

            job_title = main_content.locator("h2.KLsYvd").first.text_content()
            job_text = main_content.locator("span.HBvzbc").first.text_content()
            job_id = main_content.locator("div.KGjGe").first.get_attribute(
                "data-encoded-doc-id"
            )

            apply_button = main_content.locator("a.pMhGee.Co68jc.j0vryd").first
            apply_link = apply_button.get_attribute("href")

            try:
                apply_agent = (
                    apply_button.text_content().split(" on ")[1].strip()
                )  # [1].trim()
            except IndexError:
                apply_agent = None

            # click the share button to generate the link
            # page.get_by_role("button", name="Share").click()
            # wait for google to shorten the link
            # sleep(1)
            # link_element = page.get_by_role("textbox", name="Share link")
            # link_text = link_element.input_value()
            # page.wait_for_load_state("networkidle")
            # page.get_by_role("button", name="Close").click()

            company_text = main_content.locator(
                "div.nJlQNd.sMzDkb"
            ).first.text_content()
            location_text = main_content.locator("div.sMzDkb").last.text_content()

            page.wait_for_load_state("networkidle")

            job = {
                "title": job_title,
                "text": job_text,
                "location": location_text,
                "id": job_id,
                "application_link": apply_link,
                "application_agent": apply_agent,
                "company_detail": company_text,
            }

            # each jobs as an certain number of "tags" with details about the job
            # e.g Salary, Hours, Time posted, Work from home
            # these number of tags aren't fixed so each job has a different amount
            # but they always use the same svg so we can use the svg to
            # identify what the tag is showing

            tag_container = main_content.locator(".ocResc.KKh3md").first
            for tag in tag_container.locator(".I2Cbhb").all():
                svg = tag.locator("svg").first
                tag_text = tag.locator(".LL4CDc").first.text_content()

                for path in svg.locator("path").all():
                    if path.get_attribute("d") == SALARY_SVG_PATH:
                        job["salary"] = tag_text
                        break
                    if path.get_attribute("d") == HOURS_SVG_PATH:
                        job["hours"] = tag_text
                        break
                    if path.get_attribute("d") == TIME_POSTED_SVG_PATH:
                        job["time_posted"] = tag_text
                        break
                    if path.get_attribute("d") == WORK_FROM_HOME_PATH:
                        job["work_from_home"] = tag_text
                        break

            jobs.append(job)
            sleep(0.5)
    return jobs


def get_job_url(
    main_query: str,
    chip_filters=None,
):
    base_url = f"https://www.google.com/search?q={'+'.join(main_query.split(' '))}&ibp=htl;jobs"
    if chip_filters:
        base_url += get_chip_url_params(chip_filters)

    return base_url


def get_chip_url_params(chip_filters: dict) -> str:
    """Chips are the extra filters applied on the Google jobs page.
    This function takes a dictionary of chip filters and returns the url params

    htichips format = {chip_name}:{chip_value},{chip_name}:{chip_value}
    htiscips format = {chip_name};{chip_value};{chip_value},{chip_name};{chip_value};{chip_value}
    """
    chip_hti_url_params = ",".join(
        [
            f"{key}:{value}"
            for key, values in chip_filters.items()
            if values
            for value in values
        ]
    )

    chip_htis_url_params = ",".join(
        [f"{key};{';'.join(values)}" for key, values in chip_filters.items() if values]
    )
    search_radius_km = 48.2802

    return f"#htivrt=jobs&htilrad={search_radius_km}&htichips={chip_hti_url_params}&htischips={chip_htis_url_params}"


def get_relative_time(time_posted_str):
    now = timezone.now()
    if time_posted_str is None:
        return now
    if "hours" in time_posted_str:
        diff = time_posted_str.split(" ")[0]
        return now - timedelta(hours=int(diff))
    if "days" in time_posted_str:
        diff = time_posted_str.split(" ")[0]
        return now - timedelta(days=int(diff))

    return now


def make_job_from_google(participant, job):
    return Job(
        participant=participant,
        title=Position.objects.get_or_create(title=job.get("title"))[0],
        company_detail=job.get("company_detail"),
        company=Organization.objects.get_or_create(name=job.get("company_detail"))[0],
        description=job.get("text"),
        location_detail=job.get("location", ""),
        application_link=job.get("application_link", ""),
        application_agent=job.get("application_agent", ""),
        status="New",
        posted_at=get_relative_time(job.get("time_posted")),
        salary=job.get("salary", ""),
        remote=job.get("work_from_home", ""),
        source_id=job.get("id", ""),
        auto_generated=True,
    )


def get_jobs_for_participant(
    participant, search_query, keywords=None, date_posted=None
):
    if date_posted == "all":
        date_posted = None

    scraped_jobs = get_jobs_from_google(
        search_query,
        {
            "date_posted": [date_posted] if date_posted else [],
            "job_family_1": keywords,
        },
    )
    new_jobs = []
    for job in scraped_jobs:
        # check for duplicates on source_id
        if not Job.objects.filter(
            participant=participant, source_id=job["id"]
        ).exists():
            new_jobs.append(make_job_from_google(participant, job))
        else:
            print(f"Duplicate found: {job['id']}")
    print(
        f"Found {len(new_jobs)} jobs for {participant.first_name} {participant.last_name}"
    )

    if new_jobs:
        Job.objects.bulk_create(new_jobs)


def q_get_jobs_for_participant(
    participant,
    search_query,
    keywords=None,
    date_posted=None,
):
    return async_task(
        "cold_apply.jobs.get_jobs_for_participant",
        participant,
        search_query,
        keywords=None,
        date_posted=None,
    )


def q_test_job_task(number):
    return async_task("cold_apply.jobs.test_job_task", number)


def test_job_task(number):
    sleep(number)
    return 12


# class Command(BaseCommand):
#     def handle(self, *args, **options):
#         participant = Participant.objects.get(pk=25)
#         Job.objects.get_or_create
#         participant.job_set.filter(status="New").delete()
#         get_jobs_for_participant(participant, "python developer london")
