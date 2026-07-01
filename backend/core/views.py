from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from .models import (
    TravelGroup, Subject, CombinedClassGroup, Teacher,
    SchoolClass, Location, ClassSubjectTeacher,
    TeacherQualification, ScheduleLock, SchedulerSettings,
    TeacherBlockedTime, School, get_qualification_subject_queryset,
    is_subject_qualification_managed
)
from .serializers import (
    TravelGroupSerializer, SubjectSerializer, CombinedClassGroupSerializer,
    TeacherSerializer, SchoolClassSerializer, LocationSerializer,
    ClassSubjectTeacherSerializer,
    TeacherQualificationSerializer, ScheduleLockSerializer,
    SchedulerSettingsSerializer,
    TeacherBlockedTimeSerializer, SchoolSerializer
)
from .school_utils import get_request_school


# ── School ──────────────────────────────────────────────────────────────

class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer


# ── Scoped ViewSets ─────────────────────────────────────────────────────

class _SchooledMixin:
    """为 ViewSet 自动注入 school 的 perform_create。"""

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school)


class TravelGroupViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = TravelGroupSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return TravelGroup.objects.filter(school=school)


class SubjectViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = SubjectSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return Subject.objects.filter(school=school)


class CombinedClassGroupViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = CombinedClassGroupSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return CombinedClassGroup.objects.filter(school=school)


class TeacherViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = TeacherSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return Teacher.objects.select_related(
            'travel_group', 'combined_class_group'
        ).filter(school=school)


class SchoolClassViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = SchoolClassSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return SchoolClass.objects.select_related('homeroom_teacher').filter(school=school)


class LocationViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = LocationSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return Location.objects.filter(school=school)


class ClassSubjectTeacherViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = ClassSubjectTeacherSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return ClassSubjectTeacher.objects.select_related(
            'school_class', 'subject', 'teacher'
        ).filter(school=school)


class TeacherQualificationViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = TeacherQualificationSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return TeacherQualification.objects.select_related('teacher', 'subject').filter(
            subject__in=get_qualification_subject_queryset(school)
        )


class TeacherBlockedTimeViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = TeacherBlockedTimeSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return TeacherBlockedTime.objects.select_related('teacher').filter(school=school)


class ScheduleLockViewSet(_SchooledMixin, viewsets.ModelViewSet):
    serializer_class = ScheduleLockSerializer

    def get_queryset(self):
        school = get_request_school(self.request)
        return ScheduleLock.objects.select_related(
            'school_class', 'subject', 'teacher'
        ).filter(school=school)


@api_view(['GET'])
def get_qualifications_by_subject(request, subject_id):
    """获取某门课程的所有合格教师ID列表"""
    school = get_request_school(request)
    subject = Subject.objects.filter(pk=subject_id, school=school).first()
    if not subject:
        return Response({'detail': '课程不存在。'}, status=status.HTTP_404_NOT_FOUND)
    if not is_subject_qualification_managed(subject):
        return Response(
            {'detail': '班会和校本课程不通过教师资质管理。'},
            status=status.HTTP_400_BAD_REQUEST
        )

    teacher_ids = list(
        TeacherQualification.objects.filter(subject_id=subject_id)
        .values_list('teacher_id', flat=True)
    )
    return Response({'subject_id': subject_id, 'teacher_ids': teacher_ids})


@api_view(['POST'])
def set_qualifications_for_subject(request, subject_id):
    """批量设置某门课程的合格教师"""
    school = get_request_school(request)
    subject = Subject.objects.filter(pk=subject_id, school=school).first()
    if not subject:
        return Response({'detail': '课程不存在。'}, status=status.HTTP_404_NOT_FOUND)
    if not is_subject_qualification_managed(subject):
        return Response(
            {'detail': '班会和校本课程不通过教师资质管理。'},
            status=status.HTTP_400_BAD_REQUEST
        )

    teacher_ids = request.data.get('teacher_ids', [])

    # 删除该课程的所有现有资质
    TeacherQualification.objects.filter(subject_id=subject_id).delete()

    # 批量创建新资质
    qualifications = [
        TeacherQualification(school=school, subject_id=subject_id, teacher_id=tid)
        for tid in teacher_ids
    ]
    TeacherQualification.objects.bulk_create(qualifications)

    return Response({
        'subject_id': subject_id,
        'teacher_ids': teacher_ids,
        'count': len(teacher_ids)
    })


@api_view(['DELETE'])
def clear_all_assignments(request):
    """清空当前学校的授课分配"""
    school = get_request_school(request)
    count = ClassSubjectTeacher.objects.filter(school=school).count()
    ClassSubjectTeacher.objects.filter(school=school).delete()
    return Response({'deleted': count})


@api_view(['GET'])
def get_locks_by_class(request, class_id):
    """获取某班级的所有课表锁定"""
    school = get_request_school(request)
    locks = ScheduleLock.objects.filter(
        school_class_id=class_id, school=school
    ).select_related('subject', 'teacher')
    serializer = ScheduleLockSerializer(locks, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def set_lock(request):
    """设置或更新课表锁定"""
    school = get_request_school(request)
    class_id = request.data.get('school_class')
    day = request.data.get('day')
    period = request.data.get('period')
    subject_id = request.data.get('subject')
    teacher_id = request.data.get('teacher')  # 可选

    if not all([class_id, day is not None, period is not None, subject_id]):
        return Response({'error': '缺少必要参数'}, status=400)

    lock, created = ScheduleLock.objects.update_or_create(
        school_class_id=class_id,
        day=day,
        period=period,
        defaults={
            'subject_id': subject_id,
            'teacher_id': teacher_id,
            'school': school,
        }
    )
    serializer = ScheduleLockSerializer(lock)
    return Response(serializer.data)


@api_view(['DELETE'])
def delete_lock(request):
    """删除课表锁定"""
    school = get_request_school(request)
    class_id = request.data.get('school_class')
    day = request.data.get('day')
    period = request.data.get('period')

    deleted, _ = ScheduleLock.objects.filter(
        school_class_id=class_id,
        day=day,
        period=period,
        school=school,
    ).delete()

    return Response({'deleted': deleted})


@api_view(['DELETE'])
def clear_all_locks(request):
    """清空当前学校的课表锁定"""
    school = get_request_school(request)
    count = ScheduleLock.objects.filter(school=school).count()
    ScheduleLock.objects.filter(school=school).delete()
    return Response({'deleted': count})


@api_view(['GET'])
def get_scheduler_settings(request):
    """获取当前学校的排课参数设置"""
    school = get_request_school(request)
    settings = SchedulerSettings.get_settings(school)
    serializer = SchedulerSettingsSerializer(settings)
    return Response(serializer.data)


@api_view(['PUT', 'PATCH'])
def update_scheduler_settings(request):
    """更新当前学校的排课参数设置"""
    school = get_request_school(request)
    settings = SchedulerSettings.get_settings(school)
    serializer = SchedulerSettingsSerializer(settings, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
def reset_scheduler_settings(request):
    """重置当前学校的排课参数为默认值"""
    school = get_request_school(request)
    SchedulerSettings.objects.filter(school=school).delete()
    settings = SchedulerSettings.get_settings(school)  # 创建默认值
    serializer = SchedulerSettingsSerializer(settings)
    return Response(serializer.data)


@api_view(['GET'])
def calendar_config(request):
    """返回当前学校的日历配置，供前端统一消费。"""
    school = get_request_school(request)
    settings = SchedulerSettings.get_settings(school)
    ppd = settings.get_periods_per_day()
    day_count = len(ppd)
    return Response({
        'day_labels': settings.get_day_labels(),
        'day_count': day_count,
        'periods_per_day': ppd,
        'am_period_count': settings.am_period_count,
        'class_meeting_slot': settings.get_class_meeting_slot(),
        'combined_slots': settings.get_combined_class_slots_list(),
        'total_slots': sum(ppd.values()),
    })
