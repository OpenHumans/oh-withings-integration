from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete', views.complete, name='complete'),
    path('complete_nokia', views.complete_nokia, name='complete_nokia'),
]
