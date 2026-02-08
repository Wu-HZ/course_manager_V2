from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .data_io import export_data, import_data

router = DefaultRouter()
router.register(r'travel-groups', views.TravelGroupViewSet)
router.register(r'subjects', views.SubjectViewSet)
router.register(r'combined-class-groups', views.CombinedClassGroupViewSet)
router.register(r'teachers', views.TeacherViewSet)
router.register(r'classes', views.SchoolClassViewSet)
router.register(r'locations', views.LocationViewSet)
router.register(r'class-subject-teachers', views.ClassSubjectTeacherViewSet)
router.register(r'teacher-qualifications', views.TeacherQualificationViewSet)
router.register(r'schedule-locks', views.ScheduleLockViewSet)

urlpatterns = [
    # 自定义路由放在前面，优先匹配
    path('subjects/<int:subject_id>/qualifications/', views.get_qualifications_by_subject),
    path('subjects/<int:subject_id>/qualifications/set/', views.set_qualifications_for_subject),
    path('class-subject-teachers/clear-all/', views.clear_all_assignments),
    path('classes/<int:class_id>/locks/', views.get_locks_by_class),
    path('schedule-locks/set/', views.set_lock),
    path('schedule-locks/delete/', views.delete_lock),
    path('schedule-locks/clear-all/', views.clear_all_locks),
    path('scheduler-settings/', views.get_scheduler_settings),
    path('scheduler-settings/update/', views.update_scheduler_settings),
    path('scheduler-settings/reset/', views.reset_scheduler_settings),
    path('data/export/', export_data),
    path('data/import/', import_data),
    # router.urls 放在最后
    path('', include(router.urls)),
]
