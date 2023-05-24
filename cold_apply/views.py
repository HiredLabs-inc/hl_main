import datetime
from typing import Any, Dict, List

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.forms import inlineformset_factory
from django.forms import models as model_forms
from django.urls import reverse
from django.utils import timezone
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    TemplateView,
)
from hl_main.mixins import HtmxViewMixin

from resume.models import (
    Organization,
    Position,
    Experience,
    Overview,
    Bullet,
    Education,
    Concentration,
)
from .forms import (
    BulletForm,
    ParticipantForm,
    InteractionForm,
    ExperienceForm,
    ApplicantForm,
)
from .models import (
    Participant,
    Job,
    Phase,
    KeywordAnalysis,
    ParticipantExperience,
    WeightedBullet,
    BulletKeyword,
    ParticipantOverview,
    ParticipantEducation,
    Location,
    Applicant,
)
from .static.scripts.keyword_analyzer.keyword_analyzer import (
    analyze,
    hook_after_jd_analysis,
    hook_after_bullet_analysis,
)
from .static.scripts.resume_writer.bullet_weighter import weigh, hook_after_weighting
from .static.scripts.resume_writer.file_writer import write_resume


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
            Experience.objects.filter(
                participantexperience__participant_id=self.kwargs["pk"]
            )
            .order_by("-start_date")
            .first()
        )
        context["latest_experience"] = latest_experience
        context["jobs"] = jobs
        context["totals"] = totals
        context["highest_edu"] = Education.objects.filter(
            participanteducation__participant_id=self.kwargs["pk"]
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
    model = ParticipantExperience
    template_name = "cold_apply/participant_experience_list.html"
    context_object_name = "experiences"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        participant = Participant.objects.get(id=self.kwargs["pk"])
        context["participant"] = participant
        context["education"] = ParticipantEducation.objects.filter(
            participant=participant
        )
        context["bullets"] = Bullet.objects.filter(
            experience__participantexperience__participant=participant
        )
        context["now"] = timezone.now()

        return context

    def get_queryset(self):
        return Experience.objects.filter(
            participantexperience__participant_id=self.kwargs["pk"]
        ).order_by("-start_date")

class ParticipantExperienceBySkillListView(LoginRequiredMixin, ListView):
    model = Bullet
    template_name = "cold_apply/participant_experience_by_skill_list.html"
    context_object_name = "bullets"

    def get_queryset(self) -> QuerySet[Any]:

        return self.model.objects.filter(
            experience__participant__id=self.kwargs['pk']
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

    def form_valid(self, form):
        if form.is_valid():
            education = form.save(commit=False)
            education.save()
            return redirect(
                reverse(
                    "cold_apply:confirm_add_participant_education",
                    kwargs={"pk": self.kwargs["pk"], "education_pk": education.id},
                )
            )
        else:
            print(form.errors)
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


class ParticipantEducationCreateView(LoginRequiredMixin, CreateView):
    model = ParticipantEducation
    template_name = "cold_apply/participanteducation_create.html"
    fields = []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["participant"] = Participant.objects.get(id=self.kwargs["pk"])
        context["education"] = Education.objects.get(id=self.kwargs["education_pk"])
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            participant_education = form.save(commit=False)
            participant_education.participant = Participant.objects.get(
                id=self.kwargs["pk"]
            )
            participant_education.education = Education.objects.get(
                id=self.kwargs["education_pk"]
            )
            participant_education.save()
            return redirect(reverse("cold_apply:confirm_add_education"))
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


# TODO: ParticipantExperienceUpdateView
class ParticipantExperienceUpdateView(LoginRequiredMixin, UpdateView):
    model = Experience
    template_name = "cold_apply/participant_exp_update.html"
    fields = ["start_date", "end_date", "org", "position"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["experience"] = Experience.objects.get(id=self.kwargs["pk"])
        context["participant"] = Participant.objects.get(
            id=self.kwargs["participant_pk"]
        )
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


@login_required
def delete_exp(request, participant_id, pk):
    ParticipantExperience.objects.filter(participant_id=participant_id).filter(
        experience=pk
    ).delete()
    Experience.objects.get(id=pk).delete()
    return redirect(
        reverse("cold_apply:participant_experience_list", kwargs={"pk": participant_id})
    )


@login_required
def delete_education(request, participant_id, pk):
    ParticipantEducation.objects.filter(participant_id=participant_id).filter(
        education=pk
    ).delete()
    Education.objects.get(id=pk).delete()
    return redirect(
        reverse("cold_apply:participant_experience_list", kwargs={"pk": participant_id})
    )


class ParticipantBullet:
    pass


@login_required
def delete_bullet(request, pk):
    WeightedBullet.objects.filter(bullet=pk).delete()
    BulletKeyword.objects.filter(bullet=pk).delete()
    bullet = Bullet.objects.prefetch_related("experience__participant").get(id=pk)
    participant_id = bullet.experience.participant.first().id
    bullet.delete()
    return redirect(
        reverse(
            "cold_apply:participant_experience_list",
            kwargs={"pk": participant_id},
        )
    )


class TailoredResumeView(LoginRequiredMixin, ListView):
    model = ParticipantExperience
    template_name = "resume/index.html"
    context_object_name = "Experiences"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        job = Job.objects.get(id=self.kwargs["job_pk"])
        participant = Participant.objects.filter(id=self.kwargs["pk"])
        position = Position.objects.get(job=self.kwargs["job_pk"])
        # Clear existing weighted bullets
        if WeightedBullet.objects.filter(participant=self.kwargs["pk"]).exists():
            WeightedBullet.objects.filter(participant=self.kwargs["pk"]).delete()
        experiences = Experience.objects.filter(
            participantexperience__participant_id=self.kwargs["pk"]
        ).order_by("-start_date")
        weight_set = dict()
        # Get relevant bullets for each experience
        for exp in experiences:
            bullets = Bullet.objects.filter(experience=exp)
            keywords = KeywordAnalysis.objects.filter(job_id=job.id)
            # Weigh each bullet
            for bullet in bullets:
                weight = weigh(bullet=bullet, jd_keywords=keywords)
                hook_after_weighting(
                    weight,
                    participant_id=self.kwargs["pk"],
                    position_id=position.id,
                    bullet_id=bullet.id,
                )
            # Set dynamic cutoff for number of bullets
            # More recent jobs should have more bullets, older jobs should have fewer
            cutoff = 1
            five_years_ago = (timezone.now() - datetime.timedelta(weeks=260)).date()
            ten_years_ago = (timezone.now() - datetime.timedelta(weeks=520)).date()
            if exp.end_date is None:
                cutoff = 5
            elif exp.end_date > five_years_ago:
                cutoff = 5
            elif exp.end_date > ten_years_ago:
                cutoff = 3
            # Get top 3 bullets
            top_bullets = (
                WeightedBullet.objects.filter(participant=self.kwargs["pk"])
                .filter(bullet__experience=exp)
                .order_by("-weight")[:cutoff]
            )
            exp_weight = {exp.id: top_bullets}
            weight_set.update(exp_weight)
        context["participant_experiences"] = ParticipantExperience.objects.filter(
            participant=self.kwargs["pk"]
        )
        context["experiences"] = experiences
        context["job"] = job
        context["title"] = position.title
        context["weighted_set"] = weight_set
        context["weighted_bullets"] = (
            WeightedBullet.objects.filter(participant=self.kwargs["pk"])
            .filter(position=position.id)
            .order_by("-weight")
        )
        context["overview"] = Overview.objects.filter(
            participantoverview__participant_id=self.kwargs["pk"]
        ).filter(title_id=position.id)
        context["participant"] = participant
        context["education"] = ParticipantEducation.objects.filter(
            participant=self.kwargs["pk"]
        )
        context["now"] = timezone.now()
        write_resume(context)
        return context


class ParticipantExperienceCreateView(LoginRequiredMixin, CreateView):
    model = ParticipantExperience
    template_name = "cold_apply/participantexperience_create.html"
    fields = []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["participant"] = Participant.objects.get(id=self.kwargs["pk"])
        context["experience"] = Experience.objects.get(id=self.kwargs["experience_pk"])
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            participant_experience = form.save(commit=False)
            participant_experience.participant = Participant.objects.get(
                id=self.kwargs["pk"]
            )
            participant_experience.experience = Experience.objects.get(
                id=self.kwargs["experience_pk"]
            )
            participant_experience.save()
            return redirect(reverse("cold_apply:confirm_add_experience"))
        else:
            print(form.errors)
        return super().form_valid(form)


class ParticipantExperinceUpdateView(LoginRequiredMixin, UpdateView):
    model = Experience
    template_name = "cold_apply/participant_exp_update.html"
    fields = ["start_date", "end_date", "org", "position"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["experience"] = Experience.objects.get(id=self.kwargs["pk"])
        context["participant"] = Participant.objects.get(
            id=self.kwargs["participant_pk"]
        )
        context["now"] = timezone.now()

        return context


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
                    "cold_apply:create_participant_overview",
                    kwargs={"pk": self.kwargs["pk"], "overview_pk": overview.id},
                )
            )
        else:
            print(form.errors)
        return super().form_valid(form)


class ParticipantOverviewCreateView(LoginRequiredMixin, CreateView):
    model = ParticipantOverview
    template_name = "cold_apply/participantoverview_create.html"
    fields = []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["participant"] = Participant.objects.get(id=self.kwargs["pk"])
        context["overview"] = Overview.objects.get(id=self.kwargs["overview_pk"])
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            participant_overview = form.save(commit=False)
            participant_overview.participant = Participant.objects.get(
                id=self.kwargs["pk"]
            )
            participant_overview.overview = Overview.objects.get(
                id=self.kwargs["overview_pk"]
            )
            participant_overview.save()
            return redirect(reverse("cold_apply:confirm_add_overview"))
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
        if form.is_valid():
            experience = form.save(commit=False)
            experience.save()
            return redirect(
                reverse(
                    "cold_apply:confirm_add_participant_experience",
                    kwargs={"pk": self.kwargs["pk"], "experience_pk": experience.id},
                )
            )
        else:
            print(form.errors)
        return super().form_valid(form)


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


def create_bullet_view(request, experience_pk):
    experience = get_object_or_404(Experience, pk=experience_pk)

    bullet_form = BulletForm

    if request.method == "POST":
        form = bullet_form(request.POST)
        if form.is_valid():
            form.instance.experience = experience
            form.instance.type = "Work"
            bullet = form.save()
            context = {
                "bullet": bullet,
            }
            if "Hx-Request" in request.headers:
                response = HttpResponse("", headers={"Hx-Refresh": "true"})
                return response

            return redirect(
                reverse(
                    "cold_apply:participant_experience_list",
                    kwargs={"pk": bullet.experience.participant.first().id},
                ),
            )

    else:
        form = bullet_form()

    context = {"form": form, "experience": experience}
    if "Hx-Request" in request.headers:
        return render(
            request,
            "cold_apply/partials/bullet_create_form.html",
            context=context,
        )

    return render(request, "cold_apply/bullet_create.html", context=context)


class BulletCreateView(LoginRequiredMixin, CreateView):
    model = Bullet
    template_name = "cold_apply/bullet_create.html"
    fields = ["text"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        experience = Experience.objects.get(id=self.kwargs["experience_pk"])
        context["experience"] = experience
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            bullet = form.save(commit=False)
            bullet.experience = Experience.objects.get(id=self.kwargs["experience_pk"])
            bullet.type = "Work"
            bullet.save()
            return redirect(reverse("cold_apply:confirm_add_bullet"))
        else:
            print(form.errors)
        return super().form_valid(form)


class BulletUpdateView(HtmxViewMixin, LoginRequiredMixin, UpdateView):
    model = Bullet
    template_name = "cold_apply/participant_update.html"
    htmx_template = "cold_apply/partials/bullet_update_form.html"
    form_class = BulletForm

    def get_success_url(self) -> str:
        return reverse("cold_apply:bullet_detail", kwargs={"pk": self.object.id})

    def get_template_names(self) -> List[str]:
        if self.request.headers.get("Hx-Request"):
            return [self.htmx_template]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["experience"] = self.object.experience
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if "Hx-Request" in self.request.headers:
            bullet = form.save()
            return render(
                self.request,
                "cold_apply/partials/bullet_detail_li.html",
                context={"bullet": bullet},
            )
        return super().form_valid(form)


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
