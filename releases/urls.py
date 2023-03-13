from django.urls import path

from .views import ReleasesListView

app_name = 'releases'
urlpatterns = [
    path('', ReleasesListView.as_view(), name='index'),
]
