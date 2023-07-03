from datetime import datetime, timedelta
from typing import Any, Dict
from django import http
from django.forms.models import BaseModelForm
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import models as model_forms
from django.http import HttpResponse, JsonResponse
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import Resolver404, resolve, reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from django.views.decorators.http import require_http_methods
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.views.generic.edit import FormMixin

from requests import head
from background_tasks.models import Task, TaskStatusChoices
from background_tasks.queue import queue_task, work_task

from cold_apply.jobs import (
    get_jobs_for_participant,
    q_get_jobs_for_participant,
)
from cold_apply.resume_formatting import (
    group_bullets_by_experience,
    group_bullets_by_skill,
)
from hl_main.mixins import HtmxViewMixin
from rates.models import Country
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
    FindNewJobsForm,
    InteractionForm,
    NewJobSelectionForm,
    ParticipantForm,
    ResumeConfigForm,
)
from .models import (
    Applicant,
    BulletKeyword,
    Job,
    JobSearch,
    KeywordAnalysis,
    Location,
    Participant,
    Phase,
    Skill,
    Step,
    WeightedBullet,
)
from .static.scripts.keyword_analyzer.keyword_analyzer import (
    analyze,
    hook_after_jd_analysis,
)
from .static.scripts.resume_writer.bullet_weighter import hook_after_weighting, weigh


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
class ParticipantCreateView(LoginRequiredMixin, CreateView):
    model = Participant
    form = ParticipantForm
    fields = ParticipantForm.Meta.fields

    template_name = "cold_apply/participant_create.html"

    def get_initial(self) -> Dict[str, Any]:
        applicant_id = self.request.GET.get("applicant_id")
        if applicant_id:
            applicant = get_object_or_404(Applicant, pk=applicant_id)

            return {
                "applicant": applicant,
                "first_name": applicant.first_name,
                "last_name": applicant.last_name,
                "email": applicant.email,
                "phone": applicant.phone,
                "uploaded_resume": applicant.resume,
                "veteran": not applicant.service_branch == "Not a Veteran",
                "current_step": Step.objects.filter(order=0).first(),
            }

    def get_from_url(self):
        from_url = self.request.GET.get("from")
        try:
            resolve(from_url)
        except Resolver404:
            from_url = reverse("cold_apply:index")
        return from_url

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["applicant"] = context["form"].initial.get("applicant")
        context["from_url"] = self.get_from_url()

        return context


# Read Participant details
class ParticipantDetailView(LoginRequiredMixin, FormMixin, DetailView):
    model = Participant
    template_name = "cold_apply/participant_detail.html"
    context_object_name = "participants"
    queryset = Participant.objects.prefetch_related("job_set").all()

    def get_success_url(self) -> str:
        return reverse("cold_apply:participant_detail", args=[self.object.id])

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        if isinstance(form, NewJobSelectionForm):
            form.save()
            return super().form_valid(form)

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "participant": self.object,
            "user": self.request.user,
        }

    def get_form_class(self):
        return NewJobSelectionForm
        if self.request.GET.get("form") == "new_jobs":
            return NewJobSelectionForm
        return super().get_form_class()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        latest_experience = (
            Experience.objects.filter(participant_id=self.kwargs["pk"])
            .order_by("-start_date")
            .first()
        )
        context["latest_experience"] = latest_experience
        context["jobs"] = self.object.job_set.all()
        context["highest_edu"] = Education.objects.filter(
            participant_id=self.kwargs["pk"]
        ).first()
        context["now"] = timezone.now()

        return context


class ParticipantUpdateView(LoginRequiredMixin, UpdateView):
    model = Participant
    form = ParticipantForm
    template_name = "cold_apply/participant_update.html"
    fields = ParticipantForm.Meta.fields
    context_object_name = "participant"

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


# Organizations
class OrganizationCreateView(HtmxViewMixin, LoginRequiredMixin, CreateView):
    model = Organization
    template_name = "cold_apply/company_add.html"
    htmx_template = "cold_apply/modals/company_add_modal.html"
    empty_response_on_save = True
    refresh_on_save = True
    fields = ["name", "website", "org_type"]

    # TODO OrganizationDetail view for success_url
    success_url = reverse_lazy("cold_apply:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user

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
class TitleCreateView(HtmxViewMixin, LoginRequiredMixin, CreateView):
    model = Position
    fields = ["title"]
    template_name = "cold_apply/title_create.html"
    htmx_template = "cold_apply/modals/title_create_modal.html"
    empty_response_on_save = True
    refresh_on_save = True
    success_url = reverse_lazy("cold_apply:index")
    # TODO TitleDetail view for success_url


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
        "location",
    ]

    def get_success_url(self) -> str:
        return reverse("cold_apply:participant_detail", args=[self.kwargs["pk"]])

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "participant": Participant.objects.get(id=self.kwargs["pk"]),
            "now": timezone.now(),
        }

    def form_valid(self, form):
        form.instance.participant = Participant.objects.get(id=self.kwargs["pk"])
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
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


@require_http_methods(["POST"])
def job_status_update_modal_view(request, job_id):
    status_form_class = model_forms.modelform_factory(Job, fields=["status"])
    status_form = status_form_class(request.POST)

    job = get_object_or_404(Job, pk=job_id)
    if status_form.is_valid():
        job.status = status_form.cleaned_data["status"]

    form_class = model_forms.modelform_factory(Job, fields=JobUpdateView.fields)
    form = form_class(instance=job)

    return render(
        request,
        "cold_apply/modals/job_status_update_modal.html",
        context={"form": form},
    )


class JobUpdateView(HtmxViewMixin, LoginRequiredMixin, UpdateView):
    model = Job
    template_name = "cold_apply/job_update.html"
    empty_response_on_save = True
    refresh_on_save = True

    fields = [
        "title",
        "company",
        "application_link",
        "description",
        "status",
        "status_reason",
        "location",
    ]

    def get_success_url(self) -> str:
        from_url = self.request.GET.get("from")
        try:
            resolve(from_url)
        except Resolver404:
            from_url = reverse(
                "cold_apply:participant_detail", args=[self.object.participant.id]
            )
        return from_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["success_url"] = self.get_success_url()
        context["now"] = timezone.now()

        return context


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
            "now": timezone.now(),
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
    template_name = "cold_apply/education_update.html"
    fields = ["degree", "concentration", "org"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["participant"] = self.object.participant

        return context

    def form_valid(self, form):
        education = form.save(commit=False)
        education.save()
        return redirect(reverse("cold_apply:confirm_update_education"))


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
    if "Hx-Request" in request.headers:
        response = HttpResponse(status=204, headers={"Hx-Refresh": "true"})
        return response
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
            request.GET or None,
            experiences=experiences,
            skills=skills,
            certifications=certifications,
        )
    # request.GET = QueryDict()
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
@require_http_methods(["GET"])
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

    experiences = Experience.objects.filter(participant=job.participant).order_by(
        "-start_date"
    )

    skills = Skill.objects.filter(
        bullet__experience__participant=job.participant
    ).distinct()
    certifications = CertProjectActivity.objects.filter(participant=job.participant)

    form = ResumeConfigForm(
        request.GET,
        skills=skills,
        experiences=experiences,
        certifications=certifications,
    )

    if form.is_valid():
        bullets_content = form.cleaned_data["bullets_content"]

        # delete existing weightings
        WeightedBullet.objects.filter(participant=job.participant).delete()

        bullets = Bullet.objects.filter(
            experience__participant=job.participant
        ).order_by("-experience__start_date")

        keywords = job.keywordanalysis_set.all()
        overview = Overview.objects.filter(
            participant=job.participant, title=job.title
        ).first()
        education = Education.objects.filter(participant=job.participant)
        certifications = form.cleaned_data["certifications"]

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
                weighted_bullets.select_related("bullet__experience").prefetch_related(
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

        cert_varities = list(
            certifications.values_list("variety", flat=True).distinct()
        )

        if cert_varities:
            cert_varities = [
                "Activities" if cert == "Activity" else f"{cert}s"
                for cert in sorted(cert_varities)
            ]
            if len(cert_varities) == 1:
                cert_section_title = cert_varities[0]
            else:
                cert_section_title = (
                    ", ".join(cert_varities[:-1]) + " & " + cert_varities[-1]
                )
            context["cert_section_title"] = cert_section_title

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
                "skills": form.cleaned_data["extra_skills"],
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

    return redirect(reverse("cold_apply:configure_tailored_resume", args=[job.pk]))


class OverviewDetailView(HtmxViewMixin, LoginRequiredMixin, DetailView):
    model = Overview
    htmx_template = "cold_apply/partials/overview_detail.html"
    template_name = "cold_apply/overview_detail.html"
    context_object_name = "overview"


class OverviewCreateView(HtmxViewMixin, LoginRequiredMixin, CreateView):
    model = Overview
    fields = ["text"]
    template_name = "cold_apply/overview_create.html"
    htmx_template = "cold_apply/partials/overview_create_form.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        return {
            "participant": Participant.objects.get(id=self.kwargs["pk"]),
            "position": Position.objects.get(id=self.kwargs["position_pk"]),
            **super().get_context_data(**kwargs),
        }

    def form_valid(self, form):
        form.instance.participant_id = self.kwargs["pk"]
        form.instance.title_id = self.kwargs["position_pk"]
        return super().form_valid(form)


class OverviewUpdateView(HtmxViewMixin, LoginRequiredMixin, UpdateView):
    model = Overview
    fields = ["text"]
    template_name = "cold_apply/overview_update.html"
    htmx_template = "cold_apply/partials/overview_update_form.html"


class OverviewDeleteView(HtmxViewMixin, LoginRequiredMixin, DeleteView):
    model = Overview
    template_name = "cold_apply/overview_delete.html"
    refresh_on_save = True

    def get_success_url(self) -> str:
        return reverse(
            "cold_apply:configure_tailored_resume",
            args=[
                self.object.participant.job_set.filter(title=self.object.title)
                .first()
                .id
            ],
        )


class ExperienceCreateView(LoginRequiredMixin, CreateView):
    model = Experience
    template_name = "cold_apply/experience_create.html"
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
    template_name = "cold_apply/experience_update.html"
    fields = ["start_date", "end_date", "org", "position"]
    context_object_name = "experience"

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


class ParticipantBulletCreateView(HtmxViewMixin, LoginRequiredMixin, CreateView):
    """ "For creating bullets for a participant with an experience dropdown box"""

    fields = ["text", "skills", "experience"]

    def get_form(self, form_class):
        form = super().get_form(form_class)
        form.fields["experience"].queryset = Experience.objects.filter(
            participant_id=self.kwargs["pk"]
        )
        return form

    def form_valid(self, form):
        form.instance.type = "Work"
        return super().form_valid(form)


class BulletCreateView(HtmxViewMixin, LoginRequiredMixin, CreateView):
    """For creating bullets when the experience id is known"""

    model = Bullet
    template_name = "cold_apply/bullet_create.html"
    htmx_template = "cold_apply/partials/bullet_create_form.html"
    form_class = BulletForm
    refresh_on_save = True

    def get_initial(self) -> Dict[str, Any]:
        experience_id = self.request.GET.get("experience")
        skills = self.request.GET.get("skills")
        return {
            **super().get_initial(),
            "experience": experience_id,
            "skills": skills,
        }

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["experience"].queryset = Experience.objects.filter(
            participant=self.kwargs["pk"]
        )
        print(form.initial)

        return form

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        return {
            **super().get_context_data(**kwargs),
            "participant": Participant.objects.get(id=self.kwargs["pk"]),
        }

    def get_success_url(self) -> str:
        return reverse("cold_apply:bullet_detail", kwargs={"pk": self.object.id})


class BulletUpdateView(HtmxViewMixin, LoginRequiredMixin, UpdateView):
    model = Bullet
    template_name = "cold_apply/participant_update.html"
    htmx_template = "cold_apply/partials/bullet_update_form.html"
    refresh_on_save = True
    form_class = BulletForm

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["experience"].queryset = Experience.objects.filter(
            participant=self.object.experience.participant_id
        )
        return form

    def get_success_url(self) -> str:
        return reverse("cold_apply:bullet_detail", kwargs={"pk": self.object.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.kwargs.get("experience_pk"):
            experience = Experience.objects.get(id=self.kwargs["experience_pk"])
            context["experience"] = experience

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
        return Applicant.objects.all().order_by("-created_at")

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        return {**super().get_context_data(**kwargs), "now": timezone.now()}


class ApplicantDetailView(LoginRequiredMixin, DetailView):
    model = Applicant
    template_name = "cold_apply/applicant_detail.html"


def applicant_reject_view(request, pk):
    applicant = get_object_or_404(Applicant, pk=pk)
    applicant.rejected = True
    applicant.save()
    return redirect(reverse("cold_apply:applicant_list"))


class LocationCreateView(HtmxViewMixin, LoginRequiredMixin, CreateView):
    fields = ["city", "state", "country"]
    model = Location
    template_name = "cold_apply/location_create.html"
    htmx_template = "cold_apply/modals/location_create_modal.html"
    empty_response_on_save = True
    refresh_on_save = True

    def get_initial(self) -> Dict[str, Any]:
        return {"country": Country.objects.get(name="United States")}


class LocationUpdateView(LoginRequiredMixin, UpdateView):
    fields = ["city", "state", "country"]
    model = Location
    template_name = "cold_apply/location_update.html"


class LocationDetailView(LoginRequiredMixin, DetailView):
    fields = ["city", "state", "country"]
    model = Location
    template_name = "cold_apply/location_detail.html"


class LocationListView(LoginRequiredMixin, ListView):
    model = Location
    template_name = "cold_apply/location_list.html"
    context_object_name = "locations"


def find_new_jobs_view(request, participant_id):
    participant = get_object_or_404(Participant, pk=participant_id)
    applicant = participant.applicant
    job_searches = JobSearch.objects.filter(participant=participant).order_by(
        "-created_at"
    )[:10]
    last_search = job_searches.first()

    if request.method == "POST":
        form = FindNewJobsForm(request.POST)
        if form.is_valid():
            keywords = form.cleaned_data.get("keywords")
            if keywords:
                keywords = keywords.split(",")
            # get_jobs_for_participant
            task = queue_task(
                reverse('cold_apply:task_get_jobs_for_participant'),
                {
                    'user_id': request.user.id,
                    'participant_id': participant.id,
                    'search_query': form.cleaned_data["query"],
                    'keywords': keywords,
                    'date_posted': form.cleaned_data.get("date_posted"),
                }
            )
           
            request.session["task_id"] = task.id

            return redirect(
                f"{reverse('cold_apply:participant_detail', args=[participant_id])}#jobs-panel-new-jobs-heading"
            )
    else:
        if last_search:
            form = FindNewJobsForm(
                initial={
                    "query": last_search.search_query,
                    "keywords": last_search.keywords_csv,
                    "date_posted": last_search.date_posted,
                }
            )
        else:
            form = FindNewJobsForm()

    return render(
        request,
        "cold_apply/find_new_jobs.html",
        context={
            "form": form,
            "participant": participant,
            "applicant": applicant,
            "job_searches": job_searches,
        },
    )


def get_task_status_view(request):
    """task_id is appended to request.session in another view
    use that to retrieve the task status.
    If the task is finished, delete the task_id from session
    and return a Hx-Refresh trigger to refresh the current page,
    otherwise if the task is still running, return a alert with
    a loading spinner"""
    timeout = 90

    task_id = request.session.get("task_id")
    if request.session.get("task_request_time") is None:
        request.session["task_request_time"] = datetime.timestamp(timezone.now())

    is_after_timeout = (
        datetime.timestamp(timezone.now())
        > request.session["task_request_time"] + timeout
    )

    task = Task.objects.filter(id=task_id).first()
    context = {"task": task}
    if task is None or task.status == TaskStatusChoices.FAILURE:
        request.session.pop("task_id", None)
        request.session.pop("task_request_time", None)
        context['task'] = None

    elif task.status == TaskStatusChoices.SUCCESS:
        request.session.pop("task_id", None)
        request.session.pop("task_request_time", None)
        return HttpResponse(status=204, headers={"HX-Refresh": "true"})
    else:
        
        if is_after_timeout or task_id is None:
            request.session.pop("task_id", None)
            request.session.pop("task_request_time", None)
            context['task'] = None

    return render(
        request,
        "cold_apply/partials/task_job_search_status.html",
        context=context,
    )


@csrf_exempt
def task_get_jobs_for_participant(request):
    """Recieve POST from google cloud tasks"""
    
    work_task(
        request,
        get_jobs_for_participant,
    )
    return JsonResponse({"status": "success"})