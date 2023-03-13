from django.views.generic import ListView

from .models import Release


# Create your views here.
class ReleasesListView(ListView):
    model = Release
    template_name = 'releases/releases_list.html'
    context_object_name = 'releases'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Releases'
        return context
