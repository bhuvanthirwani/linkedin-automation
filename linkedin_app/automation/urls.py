from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('start-task/', views.start_task, name='start_task'),
    path('logs/', views.get_logs, name='get_logs'),
    path('profiles/', views.profiles_view, name='profiles'),
    path('stop-task/<int:job_id>/', views.stop_task, name='stop_task'),
]
