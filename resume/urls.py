from django.urls import path

from . import views

app_name = 'resume'
urlpatterns = [
    path('resumes/<int:pk>', views.index, name='index'),
]
