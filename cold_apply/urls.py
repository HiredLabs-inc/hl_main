from django.urls import path

from .views import PhaseListView, ParticipantDetailView, JobDetailView

app_name = 'cold_apply'
urlpatterns = [
    path('', PhaseListView.as_view(), name='index'),
    path('<int:pk>/', ParticipantDetailView.as_view(), name='participant_detail'),
    path('jobs/<int:pk>/', JobDetailView.as_view(), name='job_detail'),
]
