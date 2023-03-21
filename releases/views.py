from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, TemplateView, UpdateView
from django.db.models import Count, Q
from .models import Release, App, Note, Feedback


# Create your views here.
class AppCreateView(LoginRequiredMixin, CreateView):
    model = App
    template_name = 'releases/create_update.html'
    fields = ['name', 'description']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create App'
        return context

    def form_valid(self, form):
        if form.is_valid():
            app = form.save(commit=False)
            app.save()
            return redirect(reverse('staff'))
        else:
            print(form.errors)
        return super().form_valid(form)


class ReleasesListView(LoginRequiredMixin, ListView):
    model = Release
    template_name = 'releases/releases_list.html'
    context_object_name = 'releases'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Releases'
        releases = Release.objects.all().filter(app=self.kwargs['app_pk'])
        comments = Feedback.objects.filter(app=self.kwargs['app_pk'])
        totals = comments.aggregate(
            unread=Count('pk', filter=Q(status='Unread')),
            read=Count('pk', filter=Q(status='Read')),
            total=Count('pk')
        )
        app = App.objects.get(pk=self.kwargs['app_pk'])
        context['app'] = app
        context['releases'] = releases
        context['totals'] = totals
        context['now'] = timezone.now()
        return context


class ReleaseDetailView(LoginRequiredMixin, DetailView):
    model = Release
    template_name = 'releases/release_detail.html'
    context_object_name = 'release'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Release'
        return context


class ReleaseCreateView(LoginRequiredMixin, CreateView):
    model = Release
    template_name = 'releases/create_update.html'
    fields = ['app', 'major', 'minor', 'patch']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Release'
        return context

    def form_valid(self, form):
        if form.is_valid():
            release = form.save(commit=False)
            release.author = self.request.user
            release.save()
            return redirect(reverse('releases:confirm_release_create'))
        else:
            print(form.errors)
        return super().form_valid(form)


class NoteCreateView(LoginRequiredMixin, CreateView):
    model = Note
    template_name = 'releases/create_update.html'
    fields = ['release', 'text']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Note'
        return context

    def form_valid(self, form):
        if form.is_valid():
            release = form.save(commit=False)
            release.save()
            return redirect(reverse('releases:confirm_note_create'))
        else:
            print(form.errors)
        return super().form_valid(form)


class FeedbackCreateView(LoginRequiredMixin, CreateView):
    model = Feedback
    template_name = 'releases/create_update.html'
    fields = ['app', 'short_description', 'text']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Feedback'
        return context

    def form_valid(self, form):
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = self.request.user
            feedback.save()
            return redirect(reverse('releases:confirm_submit_feedback'))
        else:
            print(form.errors)
        return super().form_valid(form)

class FeedbackListView(LoginRequiredMixin, ListView):
    model = Feedback
    template_name = 'releases/feedback_list.html'
    context_object_name = 'feedback'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Feedback'
        feedback = Feedback.objects.all().filter(app=self.kwargs['app_pk'])
        app = App.objects.get(pk=self.kwargs['app_pk'])
        context['app'] = app
        context['feedback'] = feedback
        context['now'] = timezone.now()
        return context


class FeedbackDashboardView(LoginRequiredMixin, ListView):
    model = Feedback
    template_name = 'releases/feedback_dashboard.html'
    context_object_name = 'feedback'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Feedback'
        feedback = Feedback.objects.all().filter(app=self.kwargs['app_pk'])
        app = App.objects.get(pk=self.kwargs['app_pk'])
        context['app'] = app
        context['feedback'] = feedback
        context['now'] = timezone.now()
        return context

class FeedbackDetailView(LoginRequiredMixin, DetailView):
    model = Feedback
    template_name = 'releases/feedback_detail.html'
    context_object_name = 'feedback'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Feedback'
        return context

class FeedbackUpdateView(LoginRequiredMixin, UpdateView):
    model = Feedback
    template_name = 'releases/create_update.html'
    fields = ['app', 'short_description', 'text', 'status']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context

    def form_valid(self, form):
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.save()
            return redirect(reverse('releases:confirm_update_feedback'))
        else:
            print(form.errors)
        return super().form_valid(form)

class ConfirmCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'releases/confirm.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()

        return context
