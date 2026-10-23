from django.urls import path

from . import views

app_name = "hlagents"

urlpatterns = [
    path("", views.index_view, name="index"),
    path("<int:config_pk>/run/", views.start_run_view, name="start_run"),
    path("runs/<int:pk>/", views.run_view, name="run"),
    path("runs/<int:pk>/status/", views.run_status_view, name="run_status"),
    path("leads/", views.leads_view, name="leads"),
    path("leads/import/", views.import_view, name="import"),
    path("leads/<int:pk>/", views.lead_view, name="lead"),
    path("leads/<int:pk>/review/", views.review_view, name="review"),
    path("leads/<int:pk>/opt-out/", views.opt_out_view, name="opt_out"),
    path("tasks/run/", views.task_run_agent, name="task_run_agent"),
]
