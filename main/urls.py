from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('complete/', views.complete, name='complete'),
    path('complete_nokia/', views.complete_nokia, name='complete_nokia'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('update_data/', views.update_data, name='update_data'),
    path('remove_nokia/', views.remove_nokia, name='remove_nokia')
]
