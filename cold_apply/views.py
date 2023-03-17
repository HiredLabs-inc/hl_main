from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView

from resume.models import Organization, Position
from .forms import ParticipantForm, InteractionForm
from .models import Participant, Job, Phase, KeywordAnalysis
from .static.scripts.keyword_analyzer.keyword_analyzer import analyze, hook_after_analysis


@login_required
def index(request):
    context = {}
    return render(request, 'cold_apply/index.html', context)


@login_required
def create_participant(request):
    if request.method == 'POST':
        form = ParticipantForm(request.POST, request.FILES)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.user = request.user
            participant.save()
            return redirect(reverse('cold_apply:index'))
        else:
            print(form.errors)
    else:
        form = ParticipantForm()
    context = {'form': form}
    return render(request, 'cold_apply/create_participant.html', context)


@login_required
def create_Interaction(request):
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


class ParticipantDetailView(LoginRequiredMixin, DetailView):
    model = Participant
    template_name = 'cold_apply/participant_detail.html'
    context_object_name = 'participants'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['jobs'] = Job.objects.filter(participant=self.object)
        context['now'] = timezone.now()

        return context


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
            jd = self.object.description
            words = jd.split(' ')
            if len(words) < 30:
                context['keywords'] = 'Not enough words to analyze'
            else:
                analysis = analyze(jd)
                hook_after_analysis(analysis, self.object.id)
                context['keywords'] = KeywordAnalysis.objects.filter(job=self.object)

        context['now'] = timezone.now()

        return context


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


class ParticipantCreateView(LoginRequiredMixin, CreateView):
    model = Participant
    template_name = 'cold_apply/participant_create.html'
    fields = ['name', 'email', 'phone', 'veteran', 'uploaded_resume', 'uploaded_resume_title', 'current_step']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            participant = form.save(commit=False)
            participant.created_by = self.request.user
            participant.updated_by = self.request.user
            participant.save()
            return redirect(reverse('cold_apply:index'))
        else:
            print(form.errors)
        return super().form_valid(form)


class ParticipantUpdateView(LoginRequiredMixin, UpdateView):
    model = Participant
    template_name = 'cold_apply/participant_update.html'
    fields = ['name', 'email', 'phone', 'veteran', 'active', 'dnc', 'uploaded_resume', 'uploaded_resume_title',
              'current_step']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            participant = form.save(commit=False)
            participant.updated_by = self.request.user
            participant.save()
            return redirect(reverse('cold_apply:index'))
        else:
            print(form.errors)
        return super().form_valid(form)


# TODO Create Interaction using generic CreateView

# TODO View interactions using generic ListView

# TODO View interaction details using generic DetailView

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


# TODO: Add details about what was created to context
class ConfirmCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'cold_apply/confirm_create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context


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
