import datetime
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render, redirect
from django.forms import inlineformset_factory
from django.urls import reverse
from django.utils import timezone
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    TemplateView,
)

from resume.models import (
    Organization,
    Position,
    Experience,
    Overview,
    Bullet,
    Education,
    Concentration,
)
from .forms import ParticipantForm, InteractionForm, ExperienceForm, ApplicantForm
from .models import (
    Participant,
    Job,
    Phase,
    KeywordAnalysis,
    WeightedBullet,
    BulletKeyword,
    Applicant,
)
from .static.scripts.keyword_analyzer.keyword_analyzer import (
    analyze,
    hook_after_jd_analysis,
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


class ParticipantBullet:
    pass


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


class TailoredResumeView(LoginRequiredMixin, ListView):
    model = Experience
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
            participant_id=self.kwargs["pk"]
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
            participant_id=self.kwargs["pk"]
        ).filter(title_id=position.id)
        context["participant"] = participant
        context["education"] = Education.objects.filter(participant=self.kwargs["pk"])
        context["now"] = timezone.now()
        write_resume(context)
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


class BulletCreateView(LoginRequiredMixin, CreateView):
    model = Bullet
    template_name = "cold_apply/bullet_create.html"
    fields = ["text"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["participant"] = Participant.objects.get(id=self.kwargs["pk"])
        context["experience"] = Experience.objects.get(id=self.kwargs["experience_pk"])
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


class BulletUpdateView(LoginRequiredMixin, UpdateView):
    model = Bullet
    template_name = "cold_apply/participant_update.html"
    fields = ["text"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["experience"] = Experience.objects.get(id=self.kwargs["experience_pk"])
        context["now"] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            bullet = form.save(commit=False)
            bullet.experience = Experience.objects.get(id=self.kwargs["experience_pk"])
            bullet.type = "Work"
            bullet.save()
            return redirect(reverse("cold_apply:confirm_update_bullet"))
        else:
            print(form.errors)
        return super().form_valid(form)


# TODO: BulletDetailView


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
