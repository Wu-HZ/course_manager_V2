from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .export_word import export_word

router = DefaultRouter()
router.register(r'results', views.ScheduleResultViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('precheck/', views.schedule_precheck, name='schedule-precheck'),
    path('run/', views.run_schedule, name='run-schedule'),
    path('results/<int:pk>/activate/', views.activate_result, name='activate-result'),
    path('active/', views.active_schedule, name='active-schedule'),
    path('results/<int:result_id>/class/<int:class_id>/', views.class_timetable, name='class-timetable'),
    path('results/<int:result_id>/teacher/<int:teacher_id>/', views.teacher_timetable, name='teacher-timetable'),
    path('export-word/', export_word, name='export-word'),
]
