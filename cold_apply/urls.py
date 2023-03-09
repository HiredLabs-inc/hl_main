from django.urls import path

from .views import ParticipantListView, PhaseListView, ParticipantDetailView, JobDetailView, ParticipantCreateView

app_name = 'cold_apply'
urlpatterns = [
    path('', ParticipantListView.as_view(), name='index'),
    path('process/', PhaseListView.as_view(), name='process'),
    path('add_participant/', ParticipantCreateView.as_view(), name='add_participant'),
    path('<int:pk>/', ParticipantDetailView.as_view(), name='participant_detail'),
    path('jobs/<int:pk>/', JobDetailView.as_view(), name='job_detail'),
]
