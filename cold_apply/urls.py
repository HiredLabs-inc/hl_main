from django.urls import path

from .views import (
    ApplicantDetailView,
    ApplicantListView,
    BulletCreateView,
    BulletDetailView,
    BulletUpdateView,
    ConcentrationCreateView,
    ConfirmApplicationView,
    ConfirmCreateView,
    EducationCreateView,
    EducationUpdateView,
    ExperienceCreateView,
    ExperienceUpdateView,
    JobCreateView,
    JobDetailView,
    JobUpdateView,
    LocationCreateView,
    LocationDetailView,
    LocationListView,
    LocationUpdateView,
    OrganizationCreateView,
    OrganizationUpdateView,
    OverviewCreateView,
    OverviewDeleteView,
    OverviewDetailView,
    OverviewUpdateView,
    ParticipantCreateView,
    ParticipantDetailView,
    ParticipantExperienceBySkillListView,
    ParticipantExperienceListView,
    ParticipantListView,
    ParticipantUpdateView,
    PhaseListView,
    TitleCreateView,
    TitleUpdateView,
    applicant_reject_view,
    configure_tailored_resume_view,
    create_applicant,
    delete_bullet,
    delete_education,
    delete_exp,
    delete_job,
    find_new_jobs_view,
    get_task_status_view,
    job_status_update_modal_view,
    refresh_keywords,
    regenerate_bullet_view,
    tailored_resume_view,
    task_get_jobs_for_participant,
)

app_name = "cold_apply"

# Index: list of current participants and link to process overview
urlpatterns = [
    path("", ParticipantListView.as_view(), name="index"),
    path("process/", PhaseListView.as_view(), name="process"),
]

# Participants CRU (no delete)
urlpatterns += [
    path("add_participant/", ParticipantCreateView.as_view(), name="add_participant"),
    path(
        "participants/<int:pk>/",
        ParticipantDetailView.as_view(),
        name="participant_detail",
    ),
    path(
        "participants/<int:pk>/update/",
        ParticipantUpdateView.as_view(),
        name="update_participant",
    ),
    path(
        "participants/confirm_update/",
        ConfirmCreateView.as_view(),
        name="confirm_update_participant",
    ),
]

# Companies CU (no read or delete) TODO: Add delete
urlpatterns += [
    path("add_company/", OrganizationCreateView.as_view(), name="create_company"),
    path(
        "companies/confirm_add/",
        ConfirmCreateView.as_view(),
        name="confirm_add_company",
    ),
    path(
        "companiies/<int:pk>/update/",
        OrganizationUpdateView.as_view(),
        name="update_company",
    ),
    path(
        "companies/confirm_update/",
        ConfirmCreateView.as_view(),
        name="confirm_update_company",
    ),
]

# Titles CU (no read or delete) TODO: Add delete
urlpatterns += [
    path("titles/add_title/", TitleCreateView.as_view(), name="create_title"),
    path("titles/confirm_add/", ConfirmCreateView.as_view(), name="confirm_add_title"),
    path("titles/<int:pk>/update/", TitleUpdateView.as_view(), name="update_title"),
    path(
        "titles/confirm_update/",
        ConfirmCreateView.as_view(),
        name="confirm_update_title",
    ),
    path(
        "titles/keywords_refresh/<int:pk>/", refresh_keywords, name="refresh_keywords"
    ),
]
# Jobs CRUD
urlpatterns += [
    path("participants/<int:pk>/add_job/", JobCreateView.as_view(), name="create_job"),
    path("jobs/confirm_add/", ConfirmCreateView.as_view(), name="confirm_add_job"),
    path("jobs/<int:pk>/", JobDetailView.as_view(), name="job_detail"),
    path("jobs/<int:pk>/update/", JobUpdateView.as_view(), name="update_job"),
    path(
        "jobs/confirm_update/", ConfirmCreateView.as_view(), name="confirm_update_job"
    ),
    path("jobs/delete/<int:pk>/", delete_job, name="delete_job"),
    path(
        "jobs/find_new_jobs/<int:participant_id>",
        find_new_jobs_view,
        name="find_new_jobs",
    ),
    path(
        "jobs/<int:job_id>/status_update_modal",
        job_status_update_modal_view,
        name="job_status_update_modal",
    ),
]

# Participant Experiences CRUD
urlpatterns += [
    path(
        "participant/<int:pk>/experience/",
        ParticipantExperienceListView.as_view(),
        name="participant_experience_list",
    ),
    path(
        "participant/<int:pk>/experience_skills",
        ParticipantExperienceBySkillListView.as_view(),
        name="participant_experience_by_skill_list",
    ),
    path(
        "job/<int:job_pk>/configure",
        configure_tailored_resume_view,
        name="configure_tailored_resume",
    ),
    path(
        "job/<int:job_pk>/resume",
        tailored_resume_view,
        name="tailored_resume",
    ),
]

# Experience CRUD
urlpatterns += [
    path(
        "participant/<int:pk>/experience/new",
        ExperienceCreateView.as_view(),
        name="create_experience",
    ),
    path(
        "experience/confirm_add/",
        ConfirmCreateView.as_view(),
        name="confirm_add_experience",
    ),
    path(
        "experience/<int:pk>/update/",
        ExperienceUpdateView.as_view(),
        name="update_experience",
    ),
    path(
        "experience/confirm_update/",
        ConfirmCreateView.as_view(),
        name="confirm_update_experience",
    ),
    path(
        "exp/<int:pk>/delete/",
        delete_exp,
        name="delete_experience",
    ),
]

# Education CRUD
urlpatterns += [
    path(
        "participant/<int:pk>/education/new",
        EducationCreateView.as_view(),
        name="create_education",
    ),
    path(
        "education/confirm_add/",
        ConfirmCreateView.as_view(),
        name="confirm_add_education",
    ),
    path(
        "education/<int:pk>/delete/",
        delete_education,
        name="delete_education",
    ),
    path(
        "education/<int:pk>/update/",
        EducationUpdateView.as_view(),
        name="update_education",
    ),
    path(
        "education/confirm_update/",
        ConfirmCreateView.as_view(),
        name="confirm_update_education",
    ),
    path(
        "concentration/new/",
        ConcentrationCreateView.as_view(),
        name="create_concentration",
    ),
    path(
        "concentration/confirm_add/",
        ConfirmCreateView.as_view(),
        name="confirm_add_concentration",
    ),
]


# Bullets CRUD
urlpatterns += [
    path(
        "participant/<int:pk>/add_bullet/",
        BulletCreateView.as_view(),
        name="create_bullet",
    ),
    path(
        "bullets/confirm_add/", ConfirmCreateView.as_view(), name="confirm_add_bullet"
    ),
    path("bullets/<int:pk>/update/", BulletUpdateView.as_view(), name="update_bullet"),
    path(
        "bullets/<int:pk>/update/<int:job_id>",
        BulletUpdateView.as_view(),
        name="update_bullet_for_job",
    ),
    path(
        "bullets/confirm_update/",
        ConfirmCreateView.as_view(),
        name="confirm_update_bullet",
    ),
    path("bullets/<int:pk>/delete", delete_bullet, name="delete_bullet"),
    path("bullets/<int:pk>", BulletDetailView.as_view(), name="bullet_detail"),
    path(
        "bullets/<int:pk>/<int:job_id>",
        BulletDetailView.as_view(),
        name="bullet_detail_for_job",
    ),
    path(
        "bullets/<int:bullet_id>/regenerate/<int:job_id>",
        regenerate_bullet_view,
        name="regenerate_bullet",
    ),
]

# Overviews CRUD
urlpatterns += [
    path("overviews/<int:pk>/", OverviewDetailView.as_view(), name="overview_detail"),
    path(
        "participant/<int:pk>/title/<int:position_pk>/<int:job_pk>/add_overview/",
        OverviewCreateView.as_view(),
        name="create_overview",
    ),
    path(
        "overviews/confirm_add/",
        ConfirmCreateView.as_view(),
        name="confirm_add_overview",
    ),
    path(
        "overviews/<int:pk>/update/",
        OverviewUpdateView.as_view(),
        name="update_overview",
    ),
    path(
        "overviews/confirm_update/",
        ConfirmCreateView.as_view(),
        name="confirm_update_overview",
    ),
    path(
        "overviews/<int:pk>/delete/",
        OverviewDeleteView.as_view(),
        name="delete_overview",
    ),
]

# Applicant CRUD
urlpatterns += [
    path("new_applicant/", create_applicant, name="create_applicant"),
    path("applicant/<int:pk>/", ApplicantDetailView.as_view(), name="applicant_detail"),
    path("applicant/<int:pk>/reject", applicant_reject_view, name="applicant_reject"),
    path(
        "new_applicant/confirm/",
        ConfirmApplicationView.as_view(),
        name="confirm_create_applicant",
    ),
    path("applicants/", ApplicantListView.as_view(), name="applicant_list"),
]

# Locations CRUD
urlpatterns += [
    path("locations/create/", LocationCreateView.as_view(), name="create_location"),
    path(
        "locations/<int:pk>/update",
        LocationUpdateView.as_view(),
        name="update_location",
    ),
    path("locations/<int:pk>/", LocationDetailView.as_view(), name="location_detail"),
    path("locations/", LocationListView.as_view(), name="location_list"),
]


# Tasks
urlpatterns += [
    path("tasks/task_status", get_task_status_view, name="task_status"),
    path(
        "tasks/get_jobs_for_participant",
        task_get_jobs_for_participant,
        name="task_get_jobs_for_participant",
    ),
]
