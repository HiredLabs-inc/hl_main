from django.urls import path

from .views import ParticipantListView, PhaseListView, ParticipantDetailView, JobDetailView, ParticipantCreateView, \
    JobCreateView, OrganizationCreateView, ParticipantUpdateView, TitleCreateView

app_name = 'cold_apply'
urlpatterns = [
    path('', ParticipantListView.as_view(), name='index'),
    path('process/', PhaseListView.as_view(), name='process'),
    path('add_participant/', ParticipantCreateView.as_view(), name='add_participant'),
    path('<int:pk>/', ParticipantDetailView.as_view(), name='participant_detail'),
    path('jobs/<int:pk>/', JobDetailView.as_view(), name='job_detail'),
    path('participants/<int:pk>/add_job/', JobCreateView.as_view(), name='create_job'),
    path('participants/<int:pk>/update/', ParticipantUpdateView.as_view(), name='update_participant'),
    path('participants/<int:pk>/add_company/', OrganizationCreateView.as_view(), name='create_company'),
    path('participants/<int:pk>/add_title/', TitleCreateView.as_view(), name='create_title'),
]
