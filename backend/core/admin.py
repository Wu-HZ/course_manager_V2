from django.contrib import admin
from .models import (
    TravelGroup, Subject, CombinedClassGroup, Teacher,
    SchoolClass, Location, ClassSubjectTeacher,
    TeacherQualification, ScheduleLock, SchedulerSettings,
    TeacherBlockedTime
)


@admin.register(TravelGroup)
class TravelGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'day_off')
    list_filter = ('day_off',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'weekly_hours', 'is_main_subject', 'max_teacher_classes', 'is_am_preferred',
        'allow_consecutive', 'max_daily_limit', 'location_type', 'is_combined_class',
        'applicable_grades', 'avoid_first_period'
    )
    list_filter = ('is_main_subject', 'is_am_preferred', 'allow_consecutive', 'location_type', 'is_combined_class')
    search_fields = ('name',)


@admin.register(CombinedClassGroup)
class CombinedClassGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_teacher_count')
    search_fields = ('name',)

    def get_teacher_count(self, obj):
        return obj.teacher_set.count()
    get_teacher_count.short_description = '教师数'


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('name', 'travel_group', 'combined_class_group', 'exclude_from_combined', 'min_weekly_hours', 'max_weekly_hours', 'get_homeroom_class')
    list_filter = ('travel_group', 'combined_class_group', 'exclude_from_combined')
    search_fields = ('name',)

    def get_homeroom_class(self, obj):
        if hasattr(obj, 'homeroom_class') and obj.homeroom_class:
            return obj.homeroom_class.name
        return '-'
    get_homeroom_class.short_description = '班主任'


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'grade', 'homeroom_teacher')
    list_filter = ('grade',)
    search_fields = ('name',)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type', 'capacity')
    list_filter = ('location_type',)


@admin.register(TeacherQualification)
class TeacherQualificationAdmin(admin.ModelAdmin):
    list_display = ('subject', 'teacher')
    list_filter = ('subject', 'teacher')
    search_fields = ('teacher__name', 'subject__name')
    ordering = ('subject', 'teacher')


@admin.register(ClassSubjectTeacher)
class ClassSubjectTeacherAdmin(admin.ModelAdmin):
    list_display = ('school_class', 'subject', 'teacher', 'is_manual')
    list_filter = ('school_class', 'subject', 'teacher', 'is_manual')
    search_fields = ('school_class__name', 'subject__name', 'teacher__name')


@admin.register(ScheduleLock)
class ScheduleLockAdmin(admin.ModelAdmin):
    list_display = ('school_class', 'day', 'period', 'subject', 'teacher')
    list_filter = ('school_class', 'day', 'subject')
    ordering = ('school_class', 'day', 'period')


@admin.register(SchedulerSettings)
class SchedulerSettingsAdmin(admin.ModelAdmin):
    list_display = (
        's1_am_preference_weight', 's2_consecutive_weight', 's3_distribution_weight',
        's4_teacher_daily_threshold', 's4_teacher_daily_weight',
        's5_avoid_first_weight', 's6_subject_switch_weight', 's7_same_class_subject_switch_weight',
        'h11_teacher_class_daily_max'
    )

    def has_add_permission(self, request):
        # 单例模式，只允许存在一条记录
        return not SchedulerSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TeacherBlockedTime)
class TeacherBlockedTimeAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'day', 'period_type')
    list_filter = ('day', 'period_type', 'teacher')
    search_fields = ('teacher__name',)
