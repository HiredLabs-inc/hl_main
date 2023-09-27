from django.urls import path

from .views import AppCreateView, ReleasesListView, ReleaseDetailView, ReleaseCreateView, NoteCreateView, \
    ConfirmCreateView, FeedbackCreateView, FeedbackListView, FeedbackDetailView, FeedbackUpdateView, \
    FeedbackDashboardView

app_name = 'releases'

# Index: List of releases notes with most recent at the top.
urlpatterns = [
    path('app/<int:app_pk>/releases', ReleasesListView.as_view(), name='index'),
]

# Releases and Notes CRU (no delete)
urlpatterns += [
    path('release/new', ReleaseCreateView.as_view(), name='release_create'),
    path('release/<int:pk>/confirm', ConfirmCreateView.as_view(), name='confirm_create'),
    path('release/<int:pk>', ReleaseDetailView.as_view(), name='release_detail'),
    ]

# Notes CU (no read; no delete)
urlpatterns += [
    path('release/<int:pk>/add_note', NoteCreateView.as_view(), name='note_create'),
    path('note/confirm', ConfirmCreateView.as_view(), name='confirm_note_create'),
    ]

# app C (no read, update, delete)
urlpatterns += [
    path('app/new', AppCreateView.as_view(), name='app_create'),
    ]

# Feedback CRU (no delete) TODO: Add delete
urlpatterns += [
    path('feedback/submit', FeedbackCreateView.as_view(), name='submit_feedback'),
    path('app/feedback/confirm', ConfirmCreateView.as_view(), name='confirm_submit_feedback'),
    path('app/<int:app_pk>/feedback', FeedbackDashboardView.as_view(), name='feedback_dashboard'),
    path('app/<int:app_pk>/feedback_admin', FeedbackListView.as_view(), name='feedback_list'),
    path('feedback/<int:pk>', FeedbackDetailView.as_view(), name='feedback_detail'),
    path('<int:app_pd>/feedback/<int:pk>/update', FeedbackUpdateView.as_view(), name='feedback_update'),
    path('feedback/update/confirm', ConfirmCreateView.as_view(), name='confirm_update_feedback'),
]