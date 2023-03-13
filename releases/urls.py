from django.urls import path

from .views import AppCreateView, ReleasesListView, ReleaseDetailView, ReleaseCreateView, NoteCreateView

app_name = 'releases'
urlpatterns = [
    path('', ReleasesListView.as_view(), name='index'),
    path('release/<int:pk>', ReleaseDetailView.as_view(), name='release_detail'),
    path('release/new', ReleaseCreateView.as_view(), name='release_create'),
    path('app/new', AppCreateView.as_view(), name='app_create'),
    path('release/<int:pk>/add_note', NoteCreateView.as_view(), name='note_create'),

]
