from django.urls import path

from .views import ParticipantListView

app_name = 'cold_apply'
urlpatterns = [
    path('', ParticipantListView.as_view(), name='index'),

]
