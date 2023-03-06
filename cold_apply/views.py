from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import ParticipantForm, InteractionForm


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
