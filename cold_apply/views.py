from typing import Any, Dict

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from cold_apply.resume_formatting import (
    group_bullets_by_experience,
    group_bullets_by_skill,
)
from hl_main.mixins import HtmxViewMixin
from resume.models import (
    Bullet,
    CertProjectActivity,
    Concentration,
    Education,
    Experience,
    Organization,
    Overview,
    Position,
)
from resume.pdf import RESUME_TEMPLATE_SECTIONS_JSON, write_template_to_pdf

from .forms import (
    ApplicantForm,
    BulletForm,
    ExperienceForm,
    InteractionForm,
    ParticipantForm,
    ResumeConfigForm,
)
from .models import (
    Applicant,
    BulletKeyword,
    Job,
    KeywordAnalysis,
    Participant,
    Phase,
    Skill,
    WeightedBullet,
)
from .static.scripts.keyword_analyzer.keyword_analyzer import (
    analyze,
    hook_after_jd_analysis,
)
from .static.scripts.resume_writer.bullet_weighter import hook_after_weighting, weigh
from .static.scripts.resume_writer.file_writer import (
    write_chronological_resume,
    write_skills_resume,
)


# Index
class ParticipantListView(LoginRequiredMixin, ListView):
    model = Phase
    template_name = "cold_apply/participant_list.html"
    context_object_name = "phases"
    paginate_by = 10

    def get_queryset(self):
        return Phase.objects.all().order_by("order")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["participants"] = Participant.objects.all()
        context["now"] = timezone.now()

        return context


# process/
class PhaseListView(LoginRequiredMixin, ListView):
    model = Phase
    template_name = "cold_apply/process.html"
    context_object_name = "phases"

    def get_queryset(self):
        return Phase.objects.all().order_by("order")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context


# General-use confirmation page for creating and updating.
# TODO: Add details about what was created to context
class ConfirmCreateView(LoginRequiredMixin, TemplateView):
    template_name = "cold_apply/confirm_create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context


class ConfirmApplicationView(TemplateView):
    template_name = "confirm_application_submit.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context


# Participants


# Create new Participant
@login_required
def create_participant(request):
    if request.method == "POST":
        form = ParticipantForm(request.POST, request.FILES)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.created_by = request.user
            participant.updated_by = request.user
            participant.save()
            return redirect(reverse("cold_apply:index"))
        else:
            print(form.errors)
    else:
        form = ParticipantForm()
    context = {"form": form}
    return render(request, "cold_apply/participant_create.html", context)


# Read Participant details
class ParticipantDetailView(LoginRequiredMixin, DetailView):
    model = Participant
    template_name = "cold_apply/participant_detail.html"
    context_object_name = "participants"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        jobs = Job.objects.filter(participant=self.object)
        totals = jobs.aggregate(
            total=Count("pk"),
            open_jobs=Count("pk", filter=Q(status="Open")),
            closed_jobs=Count("pk", filter=Q(status="Closed")),
            rejected=Count("pk", filter=Q(status_reason="Candidate Rejected")),
        )
        latest_experience = (
            Experience.objects.filter(participant_id=self.kwargs["pk"])
            .order_by("-start_date")
            .first()
        )
        context["latest_experience"] = latest_experience
        context["jobs"] = jobs
        context["totals"] = totals
        context["highest_edu"] = Education.objects.filter(
            participant_id=self.kwargs["pk"]
        )
        context["now"] = timezone.now()

        return context


# Update Participant
@login_required
def update_participant(request, pk):
    participant = Participant.objects.get(id=pk)
    if request.method == "POST":
        form = ParticipantForm(request.POST, request.FILES, instance=participant)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.updated_by = request.user
            participant.save()
            return redirect(reverse("cold_apply:confirm_update_participant"))
        else:
            print(form.errors)
    else:
        form = ParticipantForm(instance=participant)
    context = {"form": form}
    return render(request, "cold_apply/participant_update.html", context)


# Organizations
class OrganizationCreateView(LoginRequiredMixin, CreateView):
    model = Organization
    template_name = "cold_apply/company_add.html"
    fields = ["name", "website", "org_type"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            organization = form.save(commit=False)
            organization.created_by = self.request.user
            organization.updated_by = self.request.user
            organization.save()

            return redirect(reverse("cold_apply:confirm_add_company"))
        else:
            print(form.errors)
        return super().form_valid(form)


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    template_name = "cold_apply/company_update.html"
    fields = ["name", "website", "org_type"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            organization = form.save(commit=False)
            organization.save()
            return redirect(reverse("cold_apply:confirm_update_company"))
        else:
            print(form.errors)
        return super().form_valid(form)


# Titles


class TitleCreateView(LoginRequiredMixin, CreateView):
    model = Position
    template_name = "cold_apply/title_create.html"
    fields = ["title"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            position = form.save(commit=False)
            position.save()
            return redirect(reverse("cold_apply:confirm_add_title"))
        else:
            print(form.errors)
        return super().form_valid(form)


class TitleUpdateView(LoginRequiredMixin, UpdateView):
    model = Position
    template_name = "cold_apply/title_update.html"
    fields = ["title"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            position = form.save(commit=False)
            position.save()
            return redirect(reverse("cold_apply:confirm_update_title"))
        else:
            print(form.errors)
        return super().form_valid(form)


# Jobs
class JobCreateView(LoginRequiredMixin, CreateView):
    model = Job
    template_name = "cold_apply/job_create.html"
    fields = [
        "title",
        "company",
        "application_link",
        "description",
        "status",
        "status_reason",
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pk"] = self.kwargs["pk"]
        context["participant"] = Participant.objects.get(id=self.kwargs["pk"])
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            job = form.save(commit=False)
            job.participant = Participant.objects.get(id=self.kwargs["pk"])
            job.created_by = self.request.user
            job.updated_by = self.request.user
            job.save()
            return redirect(reverse("cold_apply:confirm_add_job"))
        else:
            print(form.errors)
        return super().form_valid(form)


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "cold_apply/job_detail.html"
    context_object_name = "jobs"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if KeywordAnalysis.objects.filter(job=self.object).exists():
            context["keywords"] = KeywordAnalysis.objects.filter(job=self.object)
        else:
            analysis = analyze(self.object.description)
            hook_after_jd_analysis(analysis, self.object.id)
            context["keywords"] = KeywordAnalysis.objects.filter(job=self.object)

        context["now"] = timezone.now()

        return context


class JobUpdateView(LoginRequiredMixin, UpdateView):
    model = Job
    template_name = "cold_apply/job_update.html"
    fields = [
        "title",
        "company",
        "application_link",
        "description",
        "status",
        "status_reason",
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            job = form.save(commit=False)
            job.updated_by = self.request.user
            job.save()
            return redirect(reverse("cold_apply:confirm_update_job"))
        else:
            print(form.errors)
        return super().form_valid(form)


@login_required
def refresh_keywords(request, pk):
    KeywordAnalysis.objects.all().filter(job=pk).delete()
    return redirect(reverse("cold_apply:job_detail", kwargs={"pk": pk}))


@login_required
def delete_job(request, pk):
    participant = Job.objects.get(id=pk).participant.id
    Job.objects.get(id=pk).delete()
    return redirect(
        reverse("cold_apply:participant_detail", kwargs={"pk": participant})
    )


class ParticipantExperienceListView(LoginRequiredMixin, ListView):
    model = Experience
    template_name = "cold_apply/participant_experience_list.html"
    context_object_name = "experiences"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        participant = Participant.objects.get(id=self.kwargs["pk"])
        context["participant"] = participant
        context["education"] = Education.objects.filter(participant=participant)
        context["bullets"] = Bullet.objects.filter(experience__participant=participant)
        context["now"] = timezone.now()

        return context

    def get_queryset(self):
        return Experience.objects.filter(participant_id=self.kwargs["pk"]).order_by(
            "-start_date"
        )


class ParticipantExperienceBySkillListView(LoginRequiredMixin, ListView):
    model = Skill
    template_name = "cold_apply/participant_experience_by_skill_list.html"
    context_object_name = "skills"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        return {
            **super().get_context_data(**kwargs),
            "participant": Participant.objects.get(pk=self.kwargs["pk"]),
            "uncategorised_bullets": Bullet.objects.filter(
                experience__participant_id=self.kwargs["pk"], skills__isnull=True
            ),
        }

    def get_queryset(self):
        # get all skills for participant with tagged bullets
        # bullets can duplicate within skills
        return (
            self.model.objects.prefetch_related("bullet_set")
            .filter(bullet__experience__participant_id=self.kwargs["pk"])
            .distinct()
        )


class EducationCreateView(LoginRequiredMixin, CreateView):
    model = Education
    template_name = "cold_apply/education_create.html"
    fields = ["degree", "concentration", "org"]

    # form_class = ExperienceForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["participant"] = Participant.objects.get(id=self.kwargs["pk"])
        context["now"] = timezone.now()

        return context

    def get_success_url(self) -> str:
        return reverse(
            "cold_apply:confirm_add_education",
        )

    def form_valid(self, form):
        form.instance.participant_id = self.kwargs["pk"]
        return super().form_valid(form)


class EducationUpdateView(LoginRequiredMixin, UpdateView):
    model = Education
    template_name = "cold_apply/participant_update.html"
    fields = ["degree", "concentration", "org"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            education = form.save(commit=False)
            education.save()
            return redirect(reverse("cold_apply:confirm_update_education"))
        else:
            print(form.errors)
        return super().form_valid(form)


class ConcentrationCreateView(LoginRequiredMixin, CreateView):
    model = Concentration
    template_name = "cold_apply/concentration_create.html"
    fields = ["name"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            concentration = form.save(commit=False)
            concentration.save()
            return redirect(reverse("cold_apply:confirm_add_concentration"))
        else:
            print(form.errors)
        return super().form_valid(form)


@login_required
def delete_exp(request, pk):
    exp = get_object_or_404(Experience, pk=pk)
    participant_id = exp.participant_id

    exp.delete()
    return redirect(
        reverse("cold_apply:participant_experience_list", kwargs={"pk": participant_id})
    )


@login_required
def delete_education(request, pk):
    education = get_object_or_404(Education, pk=pk)
    participant_id = education.participant_id
    education.delete()
    return redirect(
        reverse("cold_apply:participant_experience_list", kwargs={"pk": participant_id})
    )


@login_required
def delete_bullet(request, pk):
    WeightedBullet.objects.filter(bullet=pk).delete()
    BulletKeyword.objects.filter(bullet=pk).delete()
    bullet = Bullet.objects.select_related("experience").get(id=pk)
    participant_id = bullet.experience.participant_id
    bullet.delete()
    return redirect(
        reverse("cold_apply:participant_experience_list", kwargs={"pk": participant_id})
    )


@login_required
def configure_tailored_resume_view(request, job_pk):
    job = get_object_or_404(Job.objects.select_related("participant"), pk=job_pk)
    experiences = Experience.objects.filter(participant=job.participant)
    skills = Skill.objects.filter(
        bullet__experience__participant=job.participant
    ).distinct()
    certifications = CertProjectActivity.objects.filter(participant=job.participant)
    if request.method == "POST":
        form = ResumeConfigForm(
            request.POST,
            experiences=experiences,
            skills=skills,
            certifications=certifications,
        )
    else:
        form = ResumeConfigForm(
            experiences=experiences, skills=skills, certifications=certifications
        )
    return render(
        request,
        "cold_apply/configure_tailored_resume.html",
        context={
            "form": form,
            "job": job,
            "resume_template_sections_json": RESUME_TEMPLATE_SECTIONS_JSON,
        },
    )


class ConfigureTailoredResumeView(LoginRequiredMixin, CreateView):
    def get_form(self, form_class):
        experiences = Experience.objects.filter(participant=self.kwargs[""])


class TailoredResumView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "resume/index.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)


def weigh_bullets(bullets, job, keywords):
    for bullet in bullets:
        weight = weigh(bullet=bullet, jd_keywords=keywords)

        weighted_bullet = hook_after_weighting(
            weight,
            participant_id=job.participant.id,
            position_id=job.title.id,
            bullet_id=bullet.id,
        )

    return WeightedBullet.objects.filter(bullet_id__in=bullets)


@login_required
@require_http_methods(["POST"])
def tailored_resume_view(request, job_pk):
    job = get_object_or_404(
        Job.objects.select_related(
            "title",
            "participant",
            "participant__location__country",
            "participant__location__state",
        ).prefetch_related("keywordanalysis_set"),
        pk=job_pk,
    )
    job.participant.experience_set.first()

    experiences = Experience.objects.filter(participant=job.participant)
    skills = Skill.objects.filter(
        bullet__experience__participant=job.participant
    ).distinct()
    certifications = CertProjectActivity.objects.filter(participant=job.participant)

    form = ResumeConfigForm(
        request.POST,
        skills=skills,
        experiences=experiences,
        certifications=certifications,
    )

    if form.is_valid():
        bullets_content = form.cleaned_data["bullets_content"]

        # delete existing weightings
        WeightedBullet.objects.filter(participant=job.participant).delete()

        bullets = Bullet.objects.filter(experience__participant=job.participant)

        keywords = job.keywordanalysis_set.all()
        overview = Overview.objects.filter(
            participant=job.participant, title=job.title
        ).first()
        education = Education.objects.filter(participant=job.participant)

        context = {}

        if bullets_content == "chronological":
            bullets = bullets.filter(experience_id__in=form.cleaned_data["experiences"])

            weighted_bullets = weigh_bullets(bullets, job, keywords)
            weighted_bullets = weighted_bullets.select_related(
                "bullet__experience"
            ).order_by("-weight", "-bullet__experience__start_date")

            context["chronological_experiences"] = group_bullets_by_experience(
                weighted_bullets
            )

        elif bullets_content == "skills":
            weighted_bullets = weigh_bullets(bullets, job, keywords)
            weighted_bullets = list(
                weighted_bullets.select_related("bullet").prefetch_related(
                    "bullet__skills"
                )
            )

            skills = (
                Skill.objects.filter(
                    bullet__experience__participant=job.participant,
                    id__in=form.cleaned_data["skills"],
                )
                # exclude skills being rendered in the main bullets
                .distinct()
            )

            context["skills_with_bullets"] = group_bullets_by_skill(
                weighted_bullets, skills
            )

            # exclude skills being rendered in the main bullets
            skills = (
                Skill.objects.filter(bullet__experience__participant=job.participant)
                .exclude(id__in=skills)
                .distinct()
            )

        context.update(
            {
                "bullets_content": bullets_content,
                "job": job,
                "title": job.title,
                "overview": overview,
                "participant": job.participant,
                "education": education,
                "now": timezone.now(),
                "form": form,
                "skills": skills,
                "certifications": certifications,
            }
        )
        resume_template = f"resume/resume_{form.cleaned_data['resume_template']}.html"

        if form.cleaned_data.get("preview", False) is True:
            return render(request, resume_template, context=context)

        pdf_content = write_template_to_pdf(request, resume_template, context=context)
        response = HttpResponse(pdf_content, content_type="application/pdf")
        # response['Content-Disposition'] = 'attachment; filename=test.pdf'
        return response

    # shouldn't get here but just rerender the config page if the form is invalid
    return configure_tailored_resume_view(request, job.pk)


class OverviewCreateView(LoginRequiredMixin, CreateView):
    model = Overview
    template_name = "cold_apply/overview_create.html"
    fields = ["text"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["participant"] = Participant.objects.get(id=self.kwargs["pk"])
        context["position"] = Position.objects.get(id=self.kwargs["position_pk"])
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            overview = form.save(commit=False)
            overview.participant = Participant.objects.get(id=self.kwargs["pk"])
            overview.title = Position.objects.get(id=self.kwargs["position_pk"])
            overview.save()
            return redirect(
                reverse(
                    "cold_apply:index",
                    # kwargs={"pk": self.kwargs["pk"], "overview_pk": overview.id},
                )
            )
        else:
            print(form.errors)
        return super().form_valid(form)


class OverviewUpdateView(LoginRequiredMixin, UpdateView):
    model = Overview
    template_name = "cold_apply/participant_update.html"
    fields = ["text"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["position"] = Position.objects.get(id=self.kwargs["position_pk"])
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            overview = form.save(commit=False)
            overview.title = Position.objects.get(id=self.kwargs["position_pk"])
            overview.save()
            return redirect(reverse("cold_apply:confirm_update_overview"))
        else:
            print(form.errors)
        return super().form_valid(form)


class ExperienceCreateView(LoginRequiredMixin, CreateView):
    model = Experience
    template_name = "cold_apply/create_update.html"
    form_class = ExperienceForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["participant"] = Participant.objects.get(id=self.kwargs["pk"])
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        form.instance.participant_id = self.kwargs["pk"]
        experience = form.save()

        return redirect(
            reverse(
                "cold_apply:participant_experience_list",
                kwargs={"pk": self.kwargs["pk"]},
            )
        )


# TODO: ExperienceUpdateView


class ExperienceUpdateView(LoginRequiredMixin, UpdateView):
    model = Experience
    template_name = "cold_apply/participant_update.html"
    fields = ["start_date", "end_date", "org", "position"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            experience = form.save(commit=False)
            experience.save()
            return redirect(reverse("cold_apply:confirm_update_experience"))
        else:
            print(form.errors)
        return super().form_valid(form)


# TODO: ExperienceDetailView


class BulletCreateView(HtmxViewMixin, LoginRequiredMixin, CreateView):
    model = Bullet
    template_name = "cold_apply/bullet_create.html"
    htmx_template = "cold_apply/partials/bullet_create_form.html"
    form_class = BulletForm

    def get_success_url(self) -> str:
        return reverse("cold_apply:bullet_detail", kwargs={"pk": self.object.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        experience = Experience.objects.get(id=self.kwargs["experience_pk"])
        context["experience"] = experience
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        form.instance.experience = Experience.objects.get(
            id=self.kwargs["experience_pk"]
        )
        form.instance.type = "Work"
        response = super().form_valid(form)

        if "Hx-Request" in self.request.headers:
            # already on the experience list page so just
            # refresh on successful create to update the list
            return HttpResponse(
                headers={
                    "HX-Refresh": "true",
                    # Could use HX-Redirect as it does the same but it causes a scroll to top
                    # so HX-Refresh looks better, use HX-Redirect if
                    # you need full page reload navigation to somewhere else e.g:
                    # "HX-Redirect": reverse(
                    #     "cold_apply:participant_experience_list",
                    #     kwargs={"pk": self.object.experience.participant_id},
                    # )
                }
            )

        return response


class BulletUpdateView(HtmxViewMixin, LoginRequiredMixin, UpdateView):
    model = Bullet
    template_name = "cold_apply/participant_update.html"
    htmx_template = "cold_apply/partials/bullet_update_form.html"
    refresh_on_save = True
    form_class = BulletForm

    def get_success_url(self) -> str:
        return reverse("cold_apply:bullet_detail", kwargs={"pk": self.object.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["experience"] = self.object.experience
        context["now"] = timezone.now()

        return context


# TODO: BulletDetailView
class BulletDetailView(HtmxViewMixin, LoginRequiredMixin, DetailView):
    model = Bullet
    htmx_template = "cold_apply/partials/bullet_detail_li.html"
    template_name = "cold_apply/bullet_detail.html"
    context_object_name = "bullet"


# TODO Create Interaction using generic CreateView
@login_required
def create_interaction(request):
    if request.method == "POST":
        form = InteractionForm(request.POST)
        if form.is_valid():
            interaction = form.save(commit=False)
            interaction.user = request.user
            interaction.save()
            return redirect(reverse("cold_apply:index"))
        else:
            print(form.errors)
    else:
        form = InteractionForm()
    context = {"form": form}
    return render(request, "cold_apply/create_interaction.html", context)


# TODO View interactions using generic ListView

# TODO View interaction details using generic DetailView


def create_applicant(request):
    if request.method == "POST":
        form = ApplicantForm(request.POST, request.FILES)
        if form.is_valid():
            applicant = form.save(commit=False)
            applicant.save()
            return redirect(reverse("cold_apply:confirm_create_applicant"))
        else:
            print(form.errors)
    else:
        form = ApplicantForm()
    context = {"form": form}
    return render(request, "cold_apply/applicant_create.html", context)


# TODO View applicant list using generic ListView (login required)
class ApplicantListView(LoginRequiredMixin, ListView):
    model = Applicant
    template_name = "cold_apply/applicant_list.html"
    context_object_name = "applicant_list"

    def get_queryset(self):
        return Applicant.objects.all().order_by("name")


# TODO View applicant details using generic DetailView (login required)
