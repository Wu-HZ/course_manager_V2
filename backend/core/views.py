from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from .models import (
    TravelGroup, Subject, CombinedClassGroup, Teacher,
    SchoolClass, Location, ClassSubjectTeacher,
    TeacherQualification, ScheduleLock, SchedulerSettings,
    TeacherBlockedTime, get_qualification_subject_queryset,
    is_subject_qualification_managed
)
from .serializers import (
    TravelGroupSerializer, SubjectSerializer, CombinedClassGroupSerializer,
    TeacherSerializer, SchoolClassSerializer, LocationSerializer,
    ClassSubjectTeacherSerializer,
    TeacherQualificationSerializer, ScheduleLockSerializer,
    SchedulerSettingsSerializer,
    TeacherBlockedTimeSerializer
)


class TravelGroupViewSet(viewsets.ModelViewSet):
    queryset = TravelGroup.objects.all().order_by('day_off')
    serializer_class = TravelGroupSerializer


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer


class CombinedClassGroupViewSet(viewsets.ModelViewSet):
    queryset = CombinedClassGroup.objects.all()
    serializer_class = CombinedClassGroupSerializer


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.select_related(
        'travel_group', 'combined_class_group'
    ).all()
    serializer_class = TeacherSerializer


class SchoolClassViewSet(viewsets.ModelViewSet):
    queryset = SchoolClass.objects.select_related('homeroom_teacher').all()
    serializer_class = SchoolClassSerializer


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer


class ClassSubjectTeacherViewSet(viewsets.ModelViewSet):
    queryset = ClassSubjectTeacher.objects.select_related(
        'school_class', 'subject', 'teacher'
    ).all()
    serializer_class = ClassSubjectTeacherSerializer


class TeacherQualificationViewSet(viewsets.ModelViewSet):
    queryset = TeacherQualification.objects.select_related('teacher', 'subject').all()
    serializer_class = TeacherQualificationSerializer

    def get_queryset(self):
        return TeacherQualification.objects.select_related('teacher', 'subject').filter(
            subject__in=get_qualification_subject_queryset()
        )


class TeacherBlockedTimeViewSet(viewsets.ModelViewSet):
    queryset = TeacherBlockedTime.objects.select_related('teacher').all()
    serializer_class = TeacherBlockedTimeSerializer


@api_view(['GET'])
def get_qualifications_by_subject(request, subject_id):
    """获取某门课程的所有合格教师ID列表"""
    subject = Subject.objects.filter(pk=subject_id).first()
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
    subject = Subject.objects.filter(pk=subject_id).first()
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
        TeacherQualification(subject_id=subject_id, teacher_id=tid)
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
    """清空所有授课分配"""
    count = ClassSubjectTeacher.objects.count()
    ClassSubjectTeacher.objects.all().delete()
    return Response({'deleted': count})


class ScheduleLockViewSet(viewsets.ModelViewSet):
    queryset = ScheduleLock.objects.select_related(
        'school_class', 'subject', 'teacher'
    ).all()
    serializer_class = ScheduleLockSerializer


@api_view(['GET'])
def get_locks_by_class(request, class_id):
    """获取某班级的所有课表锁定"""
    locks = ScheduleLock.objects.filter(school_class_id=class_id).select_related(
        'subject', 'teacher'
    )
    serializer = ScheduleLockSerializer(locks, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def set_lock(request):
    """设置或更新课表锁定"""
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
        }
    )
    serializer = ScheduleLockSerializer(lock)
    return Response(serializer.data)


@api_view(['DELETE'])
def delete_lock(request):
    """删除课表锁定"""
    class_id = request.data.get('school_class')
    day = request.data.get('day')
    period = request.data.get('period')

    deleted, _ = ScheduleLock.objects.filter(
        school_class_id=class_id,
        day=day,
        period=period
    ).delete()

    return Response({'deleted': deleted})


@api_view(['DELETE'])
def clear_all_locks(request):
    """清空所有课表锁定"""
    count = ScheduleLock.objects.count()
    ScheduleLock.objects.all().delete()
    return Response({'deleted': count})


@api_view(['GET'])
def get_scheduler_settings(request):
    """获取排课参数设置"""
    settings = SchedulerSettings.get_settings()
    serializer = SchedulerSettingsSerializer(settings)
    return Response(serializer.data)


@api_view(['PUT', 'PATCH'])
def update_scheduler_settings(request):
    """更新排课参数设置"""
    settings = SchedulerSettings.get_settings()
    serializer = SchedulerSettingsSerializer(settings, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
def reset_scheduler_settings(request):
    """重置排课参数为默认值"""
    SchedulerSettings.objects.filter(pk=1).delete()
    settings = SchedulerSettings.get_settings()  # 创建默认值
    serializer = SchedulerSettingsSerializer(settings)
    return Response(serializer.data)
