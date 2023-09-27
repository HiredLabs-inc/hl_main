from django.urls import path

from .views import RateRequestListView, RecommendationCreateView, world_rates

app_name = 'rates'
urlpatterns = [
    path('', RateRequestListView.as_view(), name='nothingness'),
    path('world_rates/', world_rates, name='world_rates'),
    path('recommendation/', RecommendationCreateView.as_view(), name='index'),
]