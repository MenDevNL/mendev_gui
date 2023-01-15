from django.urls import path

from . import views
from django.contrib.auth import views as auth_views


app_name = 'system'
urlpatterns = [
    path('', views.index, name='index'),
    path('profile/', views.profile, name='profile'),
    path('system/script/', views.script, name='script'),
    path('system/tasks/', views.tasks, name='tasks'),
    path('system/tasks/task/new/', views.task_new, name='task_new'),
    path('system/tasks/task/new/<copy_task_id>/', views.task_new, name='task_copy'),
    path('system/tasks/task/<task_id>/', views.task, name='task'),
    path('login/', auth_views.LoginView.as_view(template_name='system/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='system/logout.html'), name='logout'),
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='system/password_reset.html'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='system/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='system/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='system/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]