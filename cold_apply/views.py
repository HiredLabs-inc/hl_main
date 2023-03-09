from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, DetailView

from .forms import ParticipantForm, InteractionForm
from .models import Participant, Job, Phase


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
    template_name = 'cold_apply/participant_list.html'
    context_object_name = 'phases'

    def get_queryset(self):
        return Phase.objects.all().order_by('order')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

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


# TODO View Job details using generic DetailView
class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = 'cold_apply/job_detail.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

# TODO Create Job using generic CreateView

# TODO Create Participant using generic CreateView

# TODO Create Interaction using generic CreateView

# TODO View interactions using generic ListView

# TODO View interaction details using generic DetailView
