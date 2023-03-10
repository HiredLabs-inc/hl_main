from django.urls import path

from .views import ParticipantListView, PhaseListView, ParticipantDetailView, JobDetailView, ParticipantCreateView, \
    JobCreateView, OrganizationCreateView, ParticipantUpdateView, TitleCreateView, ConfirmCreateView, JobUpdateView, \
    KeywordDeleteView

app_name = 'cold_apply'  # TODO: Organize this better
urlpatterns = [
    path('', ParticipantListView.as_view(), name='index'),
    path('process/', PhaseListView.as_view(), name='process'),
    path('add_participant/', ParticipantCreateView.as_view(), name='add_participant'),
    path('participants/<int:pk>/', ParticipantDetailView.as_view(), name='participant_detail'),
    path('jobs/<int:pk>/', JobDetailView.as_view(), name='job_detail'),
    path('participants/<int:pk>/add_job/', JobCreateView.as_view(), name='create_job'),
    path('jobs/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_job'),
    path('jobs/<int:pk>/update/', JobUpdateView.as_view(), name='update_job'),
    path('jobs/confirm_update/', ConfirmCreateView.as_view(), name='confirm_update_job'),
    path('participants/<int:pk>/update/', ParticipantUpdateView.as_view(), name='update_participant'),
    path('add_company/', OrganizationCreateView.as_view(), name='create_company'),
    path('companies/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_company'),
    path('titles/<int:pk>/add_title/', TitleCreateView.as_view(), name='create_title'),
    path('titles/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_title'),
    path('titles/keywords_refresh/<int:pk>/', KeywordDeleteView.as_view(), name='confirm_keyword_refresh'),
]
