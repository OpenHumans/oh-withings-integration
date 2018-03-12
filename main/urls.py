from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete_oh', views.complete_oh, name='complete_oh'),
    path('complete_nokiahealth', views.complete_nokiahealth,
         name='complete_nokiahealth'),
]
