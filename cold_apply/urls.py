from django.urls import path

from . import views

app_name = 'cold_apply'
urlpatterns = [
    path('', views.index, name='index'),
]
