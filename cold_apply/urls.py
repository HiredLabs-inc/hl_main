from django.urls import path

from .views import ParticipantListView, PhaseListView, ParticipantDetailView, JobDetailView, \
    JobCreateView, OrganizationCreateView, TitleCreateView, ConfirmCreateView, JobUpdateView, \
    TitleUpdateView, OrganizationUpdateView, delete_job, refresh_keywords, create_participant, update_participant, \
    ParticipantExperienceCreateView, TailoredResumeView, ExperienceCreateView, BulletCreateView, \
    OverviewCreateView, ParticipantOverviewCreateView, OverviewUpdateView, BulletUpdateView, ExperienceUpdateView, \
    ParticipantExperienceListView, delete_exp

app_name = 'cold_apply'

# Index: list of current participants and link to process overview
urlpatterns = [
    path('', ParticipantListView.as_view(), name='index'),
    path('process/', PhaseListView.as_view(), name='process'),
]

# Participants CRU (no delete)
urlpatterns += [
    path('add_participant/', create_participant, name='add_participant'),
    path('participants/<int:pk>/', ParticipantDetailView.as_view(), name='participant_detail'),
    path('participants/<int:pk>/update/', update_participant, name='update_participant'),
    path('participants/confirm_update/', ConfirmCreateView.as_view(), name='confirm_update_participant'),
]

# Companies CU (no read or delete) TODO: Add delete
urlpatterns += [
    path('add_company/', OrganizationCreateView.as_view(), name='create_company'),
    path('companies/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_company'),
    path('companiies/<int:pk>/update/', OrganizationUpdateView.as_view(), name='update_company'),
    path('companies/confirm_update/', ConfirmCreateView.as_view(), name='confirm_update_company'),
]

# Titles CU (no read or delete) TODO: Add delete
urlpatterns += [
    path('titles/add_title/', TitleCreateView.as_view(), name='create_title'),
    path('titles/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_title'),
    path('titles/<int:pk>/update/', TitleUpdateView.as_view(), name='update_title'),
    path('titles/confirm_update/', ConfirmCreateView.as_view(), name='confirm_update_title'),
    path('titles/keywords_refresh/<int:pk>/', refresh_keywords, name='refresh_keywords'),
]
# Jobs CRUD
urlpatterns += [
    path('participants/<int:pk>/add_job/', JobCreateView.as_view(), name='create_job'),
    path('jobs/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_job'),
    path('jobs/<int:pk>/', JobDetailView.as_view(), name='job_detail'),
    path('jobs/<int:pk>/update/', JobUpdateView.as_view(), name='update_job'),
    path('jobs/confirm_update/', ConfirmCreateView.as_view(), name='confirm_update_job'),
    path('jobs/delete/<int:pk>/', delete_job, name='delete_job'),
]

# Participant Experiences CRUD
urlpatterns += [
    path('participant/<int:pk>/experience/', ParticipantExperienceListView.as_view(),
         name='participant_experience_list'),
    path('participant/<int:pk>/job/<int:job_pk>', TailoredResumeView.as_view(),
         name='tailored_resume'),
    path('participants/<int:pk>/add_experience/<int:experience_pk>', ParticipantExperienceCreateView.as_view(),
         name='add_participant_experience'),
    path('experience/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_participant_experience'),
    path('participants/<int:participant_id>/exp/<int:pk>/delete/', delete_exp, name='delete_experience'),

]

# Experience CRUD
urlpatterns += [
    path('participant/<int:pk>/experience/new', ExperienceCreateView.as_view(), name='create_experience'),
    path('participant/<int:pk>/experience/<int:experience_pk>/confirm', ParticipantExperienceCreateView.as_view(),
         name='confirm_add_participant_experience'),
    path('experience/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_experience'),
    path('experience/<int:pk>/update/', ExperienceUpdateView.as_view(), name='update_experience'),
    path('experience/confirm_update/', ConfirmCreateView.as_view(), name='confirm_update_experience'),
]

# Bullets CRUD
urlpatterns += [
    path('participant/<int:pk>/experience/<int:experience_pk>/add_bullet/', BulletCreateView.as_view(),
         name='create_bullet'),
    path('bullets/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_bullet'),
    path('experience/<int:experience_pk>/bullets/<int:pk>/update/', BulletUpdateView.as_view(), name='update_bullet'),
    path('bullets/confirm_update/', ConfirmCreateView.as_view(), name='confirm_update_bullet'),
]

# Overviews CRUD
urlpatterns += [
    path('participant/<int:pk>/title/<int:position_pk>/add_overview/', OverviewCreateView.as_view(),
         name='create_overview'),
    path('participant/<int:pk>/title/<int:overview_pk>/confirm/', ParticipantOverviewCreateView.as_view(),
         name='create_participant_overview'),
    path('overviews/confirm_add/', ConfirmCreateView.as_view(), name='confirm_add_overview'),
    path('title/<int:position_pk>/overviews/<int:pk>/update/',
         OverviewUpdateView.as_view(), name='update_overview'),
    path('overviews/confirm_update/', ConfirmCreateView.as_view(), name='confirm_update_overview'),
]
