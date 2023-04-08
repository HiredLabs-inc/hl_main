from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, reverse
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .forms import RateRequestForm

from .models import RateRequest, RateResponse

from rates.static.scripts.rate_core.main import recommend, hook_after_recommendation


class RateRequestListView(LoginRequiredMixin, ListView):
    model = RateRequest
    paginate_by = 5
    template_name = 'rates/index.html'

    def get_context_data(self, **kwargs):
        rate_estimates = self.model.objects.all().filter(user=self.request.user).values()
        context = {
            'now': timezone.now(),
            'rate_estimates': rate_estimates
        }
        return context

#
# @login_required
# def world_rates(request):
#     if request.method == 'POST':
#         form: RateRequestForm = RateRequestForm(request.POST)
#         if form.is_valid():
#             file: object = form.save(commit=False)
#             file.user = request.user
#             file.save()
#             return redirect(reverse('rates:index'))
#         else:
#             print(form.errors)
#     else:
#         form = RateRequestForm()
#     context = {'form': form}
#     return render(request, 'rates/world_rates.html', context)


class RecommendationCreateView(LoginRequiredMixin, CreateView):
    model = RateRequest
    template_name = 'rates/recommendation.html'
    fields = ['level', 'skill', 'worker_country']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Recommendation'
        context['rate_responses'] = RateResponse.objects.all().filter(rate_request__user=self.request.user)\
            .order_by('-rate_request_id')

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.instance.user = self.request.user
            form.instance.rate = form.instance.skill.base
            rec = recommend(title=form.instance.skill, level=form.instance.level, zone=form.instance.worker_country.zone,rate=form.instance.rate)
            form.save()
            hook_after_recommendation(rec, form.instance.id)
            return redirect(reverse('rates:index'))
        else:
            print(form.errors)
        return super().form_valid(form)

@login_required
def world_rates(request):
    return render(request, 'rates/world_rates.html', {'title': 'Process'})