from django.urls import path

from . import actions

app_name = "pipeline"

urlpatterns = [
    path("enrollments/<int:enrollment_pk>/step/", actions.move_view, name="move"),
    path("enrollments/<int:enrollment_pk>/assignee/", actions.assign_view, name="assign"),
    path("enrollments/<int:enrollment_pk>/status/", actions.status_view, name="status"),
    path("enrollments/<int:enrollment_pk>/note/", actions.note_view, name="note"),
    path("enrollments/<int:enrollment_pk>/enroll/", actions.enroll_view, name="enroll"),
    path("enrollments/<int:enrollment_pk>/triage/", actions.triage_view, name="triage"),
    path("people/<int:user_pk>/panel/", actions.panel_view, name="panel"),
    path("people/<int:user_pk>/panel/note/", actions.panel_note_view, name="panel_note"),
]
