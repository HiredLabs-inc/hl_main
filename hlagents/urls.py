from django.urls import path

from . import views

app_name = "hlagents"

urlpatterns = [
    path("", views.index_view, name="index"),
    path("<int:config_pk>/run/", views.start_run_view, name="start_run"),
    path("runs/<int:pk>/", views.run_view, name="run"),
    path("runs/<int:pk>/status/", views.run_status_view, name="run_status"),
    path("runs/<int:pk>/follow-up/", views.follow_up_view, name="follow_up"),
    path("leads/", views.leads_view, name="leads"),
    path("leads/import/", views.import_view, name="import"),
    path("leads/<int:pk>/", views.lead_view, name="lead"),
    path("leads/<int:pk>/review/", views.review_view, name="review"),
    path("leads/<int:pk>/opt-out/", views.opt_out_view, name="opt_out"),
    path("leads/<int:pk>/stage/", views.stage_view, name="stage"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/agents/new/", views.agent_settings_view, name="new_agent"),
    path("settings/agents/<int:pk>/", views.agent_settings_view, name="agent_settings"),
    path("settings/providers/new/", views.provider_settings_view, name="new_provider"),
    path("settings/providers/<int:pk>/", views.provider_settings_view, name="provider_settings"),
    path("tasks/run/", views.task_run_agent, name="task_run_agent"),
]
