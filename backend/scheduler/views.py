from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ScheduleResult, ScheduleEntry
from .serializers import (
    ScheduleResultSerializer, ScheduleResultListSerializer, ScheduleEntrySerializer
)
from .engine import run_scheduler


@api_view(['POST'])
def run_schedule(request):
    """触发排课（支持自动重试）"""
    time_limit = request.data.get('time_limit_seconds', 60)
    max_attempts = request.data.get('max_attempts', 10)
    total_timeout = request.data.get('total_timeout_seconds', 120)

    result = run_scheduler(
        time_limit_seconds=time_limit,
        max_attempts=max_attempts,
        total_timeout_seconds=total_timeout
    )

    retry_stats = result.get('retry_stats', {})

    if result['success']:
        serializer = ScheduleResultSerializer(result['result'])
        return Response({
            'success': True,
            'status': result['status'],
            'solve_time_ms': result['solve_time_ms'],
            'auto_assigned_count': result.get('auto_assigned_count', 0),
            'result': serializer.data,
            'retry_stats': retry_stats,
        })
    else:
        data = {
            'success': False,
            'errors': result['errors'],
            'diagnostics': result.get('diagnostics', []),
            'status': result.get('status', 'UNKNOWN'),
            'solve_time_ms': result.get('solve_time_ms', 0),
            'auto_assigned_count': result.get('auto_assigned_count', 0),
            'retry_stats': retry_stats,
        }
        if result.get('result'):
            data['result_id'] = result['result'].id
        return Response(data, status=status.HTTP_400_BAD_REQUEST)


class ScheduleResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ScheduleResult.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleResultListSerializer
        return ScheduleResultSerializer


@api_view(['POST'])
def activate_result(request, pk):
    """设置某个排课结果为当前使用"""
    try:
        result = ScheduleResult.objects.get(pk=pk)
    except ScheduleResult.DoesNotExist:
        return Response({'error': '结果不存在'}, status=status.HTTP_404_NOT_FOUND)

    result.is_active = True
    result.save()
    return Response({'success': True})


@api_view(['GET'])
def active_schedule(request):
    """获取当前激活的排课结果"""
    result = ScheduleResult.objects.filter(is_active=True).first()
    if not result:
        return Response({'error': '没有激活的排课结果'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ScheduleResultSerializer(result)
    return Response(serializer.data)


@api_view(['GET'])
def class_timetable(request, result_id, class_id):
    """获取某班级的课表"""
    entries = ScheduleEntry.objects.filter(
        result_id=result_id, school_class_id=class_id
    ).select_related('subject', 'teacher').order_by('day', 'period')
    serializer = ScheduleEntrySerializer(entries, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def teacher_timetable(request, result_id, teacher_id):
    """获取某教师的课表"""
    from core.models import Teacher, SchedulerSettings

    entries = ScheduleEntry.objects.filter(
        result_id=result_id, teacher_id=teacher_id
    ).select_related('school_class', 'subject').order_by('day', 'period')
    serializer = ScheduleEntrySerializer(entries, many=True)
    data = serializer.data

    # 检查该教师是否参与校本课程
    try:
        teacher = Teacher.objects.get(pk=teacher_id)
        if teacher.combined_class_group and not teacher.exclude_from_combined:
            # 获取校本课程时段
            settings = SchedulerSettings.objects.first()
            if settings:
                combined_slots = settings.get_combined_class_slots_list()
                group_name = teacher.combined_class_group.name

                # 添加校本课程时段到结果中
                for day, period in combined_slots:
                    data.append({
                        'id': None,
                        'day': day,
                        'period': period,
                        'subject_name': group_name,  # 显示组名
                        'school_class_name': '(校本课程)',
                        'teacher_name': teacher.name,
                        'is_locked': True,
                    })
    except Teacher.DoesNotExist:
        pass

    # 按 day, period 排序
    data.sort(key=lambda x: (x['day'], x['period']))
    return Response(data)
