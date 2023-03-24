from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView

from resume.models import Organization, Position, Experience, Overview, Bullet
from .forms import ParticipantForm, InteractionForm
from .models import Participant, Job, Phase, KeywordAnalysis, ParticipantExperience, WeightedBullet, BulletKeyword
from .static.scripts.keyword_analyzer.keyword_analyzer import analyze, hook_after_jd_analysis, \
    hook_after_bullet_analysis
from .static.scripts.resume_writer.bullet_weighter import weigh, hook_after_weighting

# Index
class ParticipantListView(LoginRequiredMixin, ListView):
    model = Phase
    template_name = 'cold_apply/participant_list.html'
    context_object_name = 'phases'
    paginate_by = 10

    def get_queryset(self):
        return Phase.objects.all().order_by('order')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['participants'] = Participant.objects.all()
        context['now'] = timezone.now()

        return context


# process/
class PhaseListView(LoginRequiredMixin, ListView):
    model = Phase
    template_name = 'cold_apply/process.html'
    context_object_name = 'phases'

    def get_queryset(self):
        return Phase.objects.all().order_by('order')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context


# General-use confirmation page for creating and updating.
# TODO: Add details about what was created to context
class ConfirmCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'cold_apply/confirm_create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context


# Participants

# Create new Participant
@login_required
def create_participant(request):
    if request.method == 'POST':
        form = ParticipantForm(request.POST, request.FILES)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.created_by = request.user
            participant.updated_by = request.user
            participant.save()
            return redirect(reverse('cold_apply:index'))
        else:
            print(form.errors)
    else:
        form = ParticipantForm()
    context = {'form': form}
    return render(request, 'cold_apply/participant_create.html', context)


# Read Participant details
class ParticipantDetailView(LoginRequiredMixin, DetailView):
    model = Participant
    template_name = 'cold_apply/participant_detail.html'
    context_object_name = 'participants'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        jobs = Job.objects.filter(participant=self.object)
        totals = jobs.aggregate(
            total=Count('pk'),
            open_jobs=Count('pk', filter=Q(status='Open')),
            closed_jobs=Count('pk', filter=Q(status='Closed')),
            rejected=Count('pk', filter=Q(status_reason='Candidate Rejected')),
        )
        latest_experience = Experience.objects.filter(participantexperience__participant_id=self.kwargs['pk']). \
            order_by('-start_date').first()
        context['latest_experience'] = latest_experience
        context['jobs'] = jobs
        context['totals'] = totals
        context['now'] = timezone.now()

        return context


# Update Participant
@login_required
def update_participant(request, pk):
    participant = Participant.objects.get(id=pk)
    if request.method == 'POST':
        form = ParticipantForm(request.POST, request.FILES, instance=participant)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.updated_by = request.user
            participant.save()
            return redirect(reverse('cold_apply:confirm_update_participant'))
        else:
            print(form.errors)
    else:
        form = ParticipantForm(instance=participant)
    context = {'form': form}
    return render(request, 'cold_apply/participant_update.html', context)


# Organizations
class OrganizationCreateView(LoginRequiredMixin, CreateView):
    model = Organization
    template_name = 'cold_apply/company_add.html'
    fields = ['name', 'website', 'org_type']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            organization = form.save(commit=False)
            organization.created_by = self.request.user
            organization.updated_by = self.request.user
            organization.save()

            return redirect(reverse('cold_apply:confirm_add_company'))
        else:
            print(form.errors)
        return super().form_valid(form)


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    template_name = 'cold_apply/company_update.html'
    fields = ['name', 'website', 'org_type']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            organization = form.save(commit=False)
            organization.save()
            return redirect(reverse('cold_apply:confirm_update_company'))
        else:
            print(form.errors)
        return super().form_valid(form)


# Titles

class TitleCreateView(LoginRequiredMixin, CreateView):
    model = Position
    template_name = 'cold_apply/title_create.html'
    fields = ['title']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            position = form.save(commit=False)
            position.save()
            return redirect(reverse('cold_apply:confirm_add_title'))
        else:
            print(form.errors)
        return super().form_valid(form)


class TitleUpdateView(LoginRequiredMixin, UpdateView):
    model = Position
    template_name = 'cold_apply/title_update.html'
    fields = ['title']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            position = form.save(commit=False)
            position.save()
            return redirect(reverse('cold_apply:confirm_update_title'))
        else:
            print(form.errors)
        return super().form_valid(form)


# Jobs
class JobCreateView(LoginRequiredMixin, CreateView):
    model = Job
    template_name = 'cold_apply/job_create.html'
    fields = ['title', 'company', 'application_link', 'description', 'status', 'status_reason']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pk'] = self.kwargs['pk']
        context['participant'] = Participant.objects.get(id=self.kwargs['pk'])
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            job = form.save(commit=False)
            job.participant = Participant.objects.get(id=self.kwargs['pk'])
            job.created_by = self.request.user
            job.updated_by = self.request.user
            job.save()
            return redirect(reverse('cold_apply:confirm_add_job'))
        else:
            print(form.errors)
        return super().form_valid(form)


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = 'cold_apply/job_detail.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if KeywordAnalysis.objects.filter(job=self.object).exists():
            context['keywords'] = KeywordAnalysis.objects.filter(job=self.object)
        else:
            analysis = analyze(self.object.description)
            hook_after_jd_analysis(analysis, self.object.id)
            context['keywords'] = KeywordAnalysis.objects.filter(job=self.object)

        context['now'] = timezone.now()

        return context


class JobUpdateView(LoginRequiredMixin, UpdateView):
    model = Job
    template_name = 'cold_apply/job_update.html'
    fields = ['title', 'company', 'application_link', 'description', 'status', 'status_reason']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            job = form.save(commit=False)
            job.updated_by = self.request.user
            job.save()
            return redirect(reverse('cold_apply:confirm_update_job'))
        else:
            print(form.errors)
        return super().form_valid(form)


@login_required
def refresh_keywords(request, pk):
    KeywordAnalysis.objects.all().filter(job=pk).delete()
    return redirect(reverse('cold_apply:job_detail', kwargs={'pk': pk}))


@login_required
def delete_job(request, pk):
    participant = Job.objects.get(id=pk).participant.id
    Job.objects.get(id=pk).delete()
    return redirect(reverse('cold_apply:participant_detail', kwargs={'pk': participant}))


class ParticipantExperienceListView(LoginRequiredMixin, ListView):
    model = ParticipantExperience
    template_name = 'resume/index.html'
    context_object_name = 'Experiences'

    def get_context_data(self, **kwargs):
            context = super().get_context_data()
            job = Job.objects.get(id=self.kwargs['job_pk'])
            position = Position.objects.get(job=self.kwargs['job_pk'])
            # Clear existing weighted bullets
            if WeightedBullet.objects.filter(participant=self.kwargs['pk']) \
                    .filter(position=position.id).exists():
                WeightedBullet.objects.filter(participant=self.kwargs['pk']) \
                    .filter(position=position.id).delete()
            experiences = Experience.objects.filter(participantexperience__participant_id=self.kwargs['pk']). \
                order_by('-start_date')
            for exp in experiences:
                bullets = Bullet.objects.filter(experience=exp)
                keywords = KeywordAnalysis.objects.filter(job_id=job.id)
                for bullet in bullets:
                    # Clear existing bullet keywords
                    if BulletKeyword.objects.filter(bullet=bullet.id).exists():
                        BulletKeyword.objects.filter(bullet=bullet.id).delete()

                    b_kwords = analyze(bullet.text)
                    hook_after_bullet_analysis(b_kwords, bullet.id)
                    bullet_keywords = BulletKeyword.objects.filter(bullet=bullet.id)
                    weight = weigh(bullet_keywords=bullet_keywords, jd_keywords=keywords)
                    hook_after_weighting(weight, participant_id=self.kwargs['pk'], position_id=position.id, bullet_id=bullet.id)
            context['participant_experiences'] = ParticipantExperience.objects.filter(participant=self.kwargs['pk'])
            context['experiences'] = experiences
            context['job'] = job
            context['title'] = position.title
            context['weighted_bullets'] = WeightedBullet.objects.filter(participant=self.kwargs['pk'])\
                .filter(position=position.id).order_by('-weight')
            context['overview'] = Overview.objects.filter(participantoverview__participant_id=self.kwargs['pk']).filter(title_id=position.id)
            context['participant'] = Participant.objects.filter(id=self.kwargs['pk'])
            context['now'] = timezone.now()
            return context


class ParticipantExperienceCreateView(LoginRequiredMixin, CreateView):
    model = ParticipantExperience
    template_name = 'cold_apply/participantexperience_create.html'
    fields = []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['participant'] = Participant.objects.get(id=self.kwargs['pk'])
        context['experience'] = Experience.objects.get(id=self.kwargs['experience_pk'])
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            participant_experience = form.save(commit=False)
            participant_experience.participant = Participant.objects.get(id=self.kwargs['pk'])
            participant_experience.experience = Experience.objects.get(id=self.kwargs['experience_pk'])
            participant_experience.save()
            return redirect(reverse('cold_apply:confirm_add_experience'))
        else:
            print(form.errors)
        return super().form_valid(form)


# TODO: ParticipantExperienceUpdateView

# TODO: ParticipantExperienceDetailView

# TODO: ParticipantOverviewCreateView

# TODO: ParticipantOverviewUpdateView

# TODO: ParticipantOverviewDeleteView

class ExperienceCreateView(LoginRequiredMixin, CreateView):
    model = Experience
    template_name = 'cold_apply/create_update.html'
    fields = ['start_date', 'end_date', 'org', 'position']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['participant'] = Participant.objects.get(id=self.kwargs['pk'])
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            experience = form.save(commit=False)
            experience.save()
            return redirect(reverse('cold_apply:confirm_add_participant_experience',
                                    kwargs={'pk': self.kwargs['pk'], 'experience_pk': experience.id}))
        else:
            print(form.errors)
        return super().form_valid(form)


# TODO: ExperienceUpdateView

# TODO: ExperienceDetailView

# TODO: BulletCreateView
class BulletCreateView(LoginRequiredMixin, CreateView):
    model = Bullet
    template_name = 'cold_apply/bullet_create.html'
    fields = ['text']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['participant'] = Participant.objects.get(id=self.kwargs['pk'])
        context['experience'] = Experience.objects.get(id=self.kwargs['experience_pk'])
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            bullet = form.save(commit=False)
            bullet.experience = Experience.objects.get(id=self.kwargs['experience_pk'])
            bullet.type = 'Work'
            bullet.save()
            return redirect(reverse('cold_apply:confirm_add_bullet'))
        else:
            print(form.errors)
        return super().form_valid(form)

# TODO: BulletUpdateView

# TODO: BulletDetailView


# TODO Create Interaction using generic CreateView
@login_required
def create_interaction(request):
    if request.method == 'POST':
        form = InteractionForm(request.POST)
        if form.is_valid():
            interaction = form.save(commit=False)
            interaction.user = request.user
            interaction.save()
            return redirect(reverse('cold_apply:index'))
        else:
            print(form.errors)
    else:
        form = InteractionForm()
    context = {'form': form}
    return render(request, 'cold_apply/create_interaction.html', context)

#
# TODO View interactions using generic ListView

# TODO View interaction details using generic DetailView
