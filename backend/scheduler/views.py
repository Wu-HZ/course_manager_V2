from collections import Counter, defaultdict
import math

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import api_view, action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from core.models import (
    ClassSubjectTeacher, CombinedClassGroup, Location, ScheduleLock, SchedulerSettings,
    SchoolClass, Subject, Teacher, TeacherBlockedTime, TeacherQualification,
    TravelGroup
)
from .models import ScheduleResult, ScheduleEntry
from .serializers import (
    ScheduleResultSerializer, ScheduleResultListSerializer,
    ScheduleResultUpdateSerializer, ScheduleEntrySerializer
)
from .engine import run_scheduler  # 旧引擎，保留以便回退
from .service import run as run_engine_v2  # 新联合 CP-SAT 引擎
from .time_slots import TOTAL_SLOTS


class ScheduleResultPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@api_view(['POST'])
def run_schedule(request):
    """触发排课（联合 CP-SAT 引擎，确定性求解）。

    响应契约与旧引擎保持一致，前端零改动。``max_attempts`` /
    ``total_timeout_seconds`` 是旧引擎的随机重试参数，新引擎确定性求解、不重试，
    接受但忽略。无解时 ``diagnostics`` 返回求解器证明的最小冲突集（unsat core）。
    """
    time_limit = request.data.get('time_limit_seconds', 60)

    out = run_engine_v2(time_limit_seconds=time_limit, save=True)
    r = out['result']

    if out['ok'] and r is not None and r.status in ('OPTIMAL', 'FEASIBLE') and out['saved']:
        serializer = ScheduleResultSerializer(out['saved'])
        return Response({
            'success': True,
            'status': r.status,
            'solve_time_ms': r.solve_time_ms,
            'auto_assigned_count': len(out['problem'].demands),
            'result': serializer.data,
            'retry_stats': {},
        })

    data = {
        'success': False,
        'errors': out['errors'],
        'diagnostics': out['conflicts'],
        'status': r.status if r is not None else 'INFEASIBLE',
        'solve_time_ms': r.solve_time_ms if r is not None else 0,
        'auto_assigned_count': 0,
        'retry_stats': {},
    }
    return Response(data, status=status.HTTP_400_BAD_REQUEST)


def _preview_names(names, limit=3):
    names = [name for name in names if name]
    if not names:
        return ''
    if len(names) <= limit:
        return '、'.join(names)
    return f"{'、'.join(names[:limit])} 等{len(names)}项"


def _make_actions(*items):
    return [{'label': label, 'route': route} for label, route in items]


def _make_issue(key, title, detail, actions):
    return {
        'key': key,
        'title': title,
        'detail': detail,
        'actions': actions,
    }


def _make_step(key, title, description, status_value, detail, actions):
    return {
        'key': key,
        'title': title,
        'description': description,
        'status': status_value,
        'detail': detail,
        'actions': actions,
    }


def _build_precheck_payload():
    settings = SchedulerSettings.get_settings()
    class_meeting_name = settings.class_meeting_name

    teachers = list(Teacher.objects.all())
    classes = list(SchoolClass.objects.all())
    subjects = list(Subject.objects.all())
    locations = list(Location.objects.all())
    travel_groups = list(TravelGroup.objects.all())
    combined_groups = list(CombinedClassGroup.objects.all())
    assignments = list(
        ClassSubjectTeacher.objects.select_related('school_class', 'subject', 'teacher').all()
    )
    qualifications = list(TeacherQualification.objects.all())
    locks = list(ScheduleLock.objects.select_related('school_class', 'subject').all())

    blocked_times_count = TeacherBlockedTime.objects.count()
    successful_results_count = ScheduleResult.objects.filter(
        solve_status__in=['OPTIMAL', 'FEASIBLE']
    ).count()

    subject_by_id = {subject.id: subject for subject in subjects}
    class_by_id = {school_class.id: school_class for school_class in classes}
    location_labels = dict(Location._meta.get_field('location_type').choices)

    regular_subjects = [
        subject for subject in subjects
        if not subject.is_combined_class and subject.name != class_meeting_name
    ]
    required_subjects = [
        subject for subject in regular_subjects
        if any(subject.is_applicable_for_grade(school_class.grade) for school_class in classes)
    ]
    combined_subject = next((subject for subject in subjects if subject.is_combined_class), None)

    qualification_map = defaultdict(set)
    for qualification in qualifications:
        qualification_map[qualification.subject_id].add(qualification.teacher_id)

    applicable_pairs = []
    applicable_pair_keys = set()
    for school_class in classes:
        for subject in regular_subjects:
            if not subject.is_applicable_for_grade(school_class.grade):
                continue
            applicable_pairs.append((school_class, subject))
            applicable_pair_keys.add((school_class.id, subject.id))

    total_school_hours = 0
    for school_class in classes:
        for subject in subjects:
            if not subject.is_applicable_for_grade(school_class.grade):
                continue
            total_school_hours += subject.weekly_hours

    average_teacher_hours = None
    if teachers:
        average_teacher_hours = round(total_school_hours / len(teachers), 1)

    assignment_map = {}
    for assignment in assignments:
        key = (assignment.school_class_id, assignment.subject_id)
        if key in applicable_pair_keys:
            assignment_map[key] = assignment

    expected_assignment_pairs_count = len(applicable_pairs)
    assignment_count = len(assignment_map)
    manual_assignment_count = sum(1 for assignment in assignment_map.values() if assignment.is_manual)
    auto_assignment_count = assignment_count - manual_assignment_count

    missing_assignment_pairs = [
        (school_class, subject)
        for school_class, subject in applicable_pairs
        if (school_class.id, subject.id) not in assignment_map
    ]
    invalid_assignments = [
        assignment for assignment in assignment_map.values()
        if assignment.teacher_id not in qualification_map.get(assignment.subject_id, set())
    ]
    subjects_without_qualification = [
        subject for subject in required_subjects
        if not qualification_map.get(subject.id)
    ]

    location_capacity = defaultdict(int)
    for location in locations:
        location_capacity[location.location_type] += max(location.capacity, 0)

    missing_location_types = sorted({
        subject.location_type
        for subject in required_subjects
        if subject.location_type != 'NORMAL' and location_capacity.get(subject.location_type, 0) <= 0
    })
    missing_location_labels = [location_labels.get(code, code) for code in missing_location_types]
    required_location_types = sorted({
        subject.location_type
        for subject in required_subjects
        if subject.location_type != 'NORMAL'
    })
    required_location_labels = [location_labels.get(code, code) for code in required_location_types]

    lock_counts = Counter((lock.school_class_id, lock.subject_id) for lock in locks)
    lock_overflows = []
    for (class_id, subject_id), count in lock_counts.items():
        subject = subject_by_id.get(subject_id)
        school_class = class_by_id.get(class_id)
        if not subject or not school_class:
            continue
        if count > subject.weekly_hours:
            lock_overflows.append({
                'class_name': school_class.name,
                'subject_name': subject.name,
                'lock_count': count,
                'weekly_hours': subject.weekly_hours,
            })

    # 教师授课容量分析：合格教师数 × 每人最多带班数 是否覆盖适用班级数
    subject_demand = Counter()
    for school_class, subject in applicable_pairs:
        subject_demand[subject.id] += 1

    capacity_shortages = []
    for subject in required_subjects:
        demand = subject_demand.get(subject.id, 0)
        qualified_count = len(qualification_map.get(subject.id, set()))
        # qualified_count == 0 已由 subjects_without_qualification 单独处理，这里跳过避免重复
        if demand == 0 or qualified_count == 0:
            continue
        max_classes = max(subject.max_teacher_classes, 1)
        capacity = qualified_count * max_classes
        if capacity < demand:
            capacity_shortages.append({
                'subject_name': subject.name,
                'demand': demand,
                'qualified_count': qualified_count,
                'max_classes': max_classes,
                'capacity': capacity,
                'needed': math.ceil((demand - capacity) / max_classes),
            })

    # 总量供需下界：全校普通课程课时 vs 教师可授时段
    normal_subject_hours = sum(subject.weekly_hours for _, subject in applicable_pairs)
    per_teacher_max = max(TOTAL_SLOTS - 1, 1)  # 去掉周五班会那节后，单个教师每周可授时段上界
    estimated_min_teachers = (
        math.ceil(normal_subject_hours / per_teacher_max) if normal_subject_hours else 0
    )
    total_teacher_supply = sum(
        min(
            teacher.max_weekly_hours if teacher.max_weekly_hours is not None else per_teacher_max,
            per_teacher_max,
        )
        for teacher in teachers
    )
    supply_gap = normal_subject_hours - total_teacher_supply

    blocking_issues = []
    if not teachers:
        blocking_issues.append(_make_issue(
            'missing_teachers',
            '还没有教师数据，无法分配任课教师或班主任',
            '请先录入至少 1 位教师。班级中的班主任、授课分配和后续自动分配都会用到教师数据。',
            _make_actions(('去教师管理', '/teachers')),
        ))
    if not classes:
        blocking_issues.append(_make_issue(
            'missing_classes',
            '还没有班级数据，无法建立班级课表',
            '请先录入参与排课的班级，并在需要时设置班主任。',
            _make_actions(('去班级管理', '/classes')),
        ))
    if not subjects:
        blocking_issues.append(_make_issue(
            'missing_subjects',
            '还没有课程数据，无法计算每班周课时',
            '请先录入课程周课时、适用年级和课程属性。',
            _make_actions(('去课程管理', '/subjects')),
        ))
    if missing_location_labels:
        blocking_issues.append(_make_issue(
            'missing_locations',
            '存在课程需要专用场地，但场地容量未配置',
            f"以下场地类型还没有容量：{_preview_names(missing_location_labels)}。只有普通教室不需要在场地管理中单独配置。",
            _make_actions(('去课程管理', '/subjects'), ('去场地管理', '/locations')),
        ))
    if subjects_without_qualification:
        blocking_issues.append(_make_issue(
            'missing_qualifications',
            '仍有待排课程没有可授课教师',
            f"以下课程还没有配置教师资质：{_preview_names([subject.name for subject in subjects_without_qualification])}。系统无法为这些课程自动分配教师。",
            _make_actions(('去教师资质', '/qualifications')),
        ))
    if combined_subject and len(combined_groups) < 4:
        blocking_issues.append(_make_issue(
            'missing_combined_groups',
            '校本课程分组不足 4 组',
            f'当前校本课程使用“{combined_subject.name}”，但校本课程分组只有 {len(combined_groups)} 组。按当前实现至少需要 4 组。',
            _make_actions(('去校本课程分组', '/combined-groups')),
        ))
    if invalid_assignments:
        blocking_issues.append(_make_issue(
            'invalid_assignments',
            '存在授课分配与教师资质不一致',
            (
                '以下班级课程当前指定的教师不在该课程资质名单内：'
                f"{_preview_names([f'{item.school_class.name}-{item.subject.name}-{item.teacher.name}' for item in invalid_assignments])}。"
            ),
            _make_actions(('去授课分配', '/assignments'), ('去教师资质', '/qualifications')),
        ))
    if lock_overflows:
        lock_overflow_preview = _preview_names([
            f"{item['class_name']}-{item['subject_name']} {item['lock_count']}/{item['weekly_hours']}"
            for item in lock_overflows
        ])
        blocking_issues.append(_make_issue(
            'lock_overflow',
            '存在班级课程锁定超出课程周课时',
            f'以下锁定数量已超过课程周课时：{lock_overflow_preview}。',
            _make_actions(('去课表锁定', '/schedule-locks')),
        ))

    if capacity_shortages:
        shortage_preview = _preview_names([
            f"{item['subject_name']}（需{item['demand']}班/可供{item['capacity']}，约缺{item['needed']}位）"
            for item in capacity_shortages
        ])
        blocking_issues.append(_make_issue(
            'teacher_capacity_shortage',
            '部分课程的合格教师不足以覆盖所有班级',
            (
                f'以下课程按“合格教师数 × 每位教师最多带班数”计算，能覆盖的班级数少于需求：{shortage_preview}。'
                '请为这些课程增加合格教师、调高课程的“单师最多班数”，或减少开课班级。'
            ),
            _make_actions(('去教师资质', '/qualifications'), ('去教师管理', '/teachers')),
        ))

    warning_issues = []
    if expected_assignment_pairs_count and missing_assignment_pairs:
        warning_issues.append(_make_issue(
            'missing_assignments',
            f'仍有 {len(missing_assignment_pairs)} 个班级课程未手动指定教师',
            '这些普通课程会在排课时按教师资质自动分配。建议先手动确认班主任主课、重点班级和必须固定教师的课程。',
            _make_actions(('去授课分配', '/assignments')),
        ))
    if blocked_times_count == 0:
        warning_issues.append(_make_issue(
            'missing_blocked_times',
            '尚未设置教师禁排时段',
            '如果教师有外出、教研、跨校或固定半天/全天不能上课，请先在“教师禁排”里补充。',
            _make_actions(('去教师禁排', '/blocked-times')),
        ))
    if supply_gap > 0:
        warning_issues.append(_make_issue(
            'teacher_supply_gap',
            '教师总可授课时可能不足',
            (
                f'全校普通课程共需 {normal_subject_hours} 课时，但现有 {len(teachers)} 位教师按每人最多约 '
                f'{per_teacher_max} 节估算，合计可授约 {total_teacher_supply} 课时，缺口约 {supply_gap} 课时'
                f'（约需再增 {math.ceil(supply_gap / per_teacher_max)} 位教师）。这是粗略估算，实际还受禁排、资质和约束影响。'
            ),
            _make_actions(('去教师管理', '/teachers')),
        ))
    can_run = len(blocking_issues) == 0

    steps = []
    steps.append(_make_step(
        'teachers',
        '教师管理',
        '录入教师，并维护送教组、校本课程参与情况和教师周课时范围。',
        'completed' if teachers else 'pending',
        f"已录入 {len(teachers)} 位教师，可继续设置班主任、送教组和教师约束。" if teachers else '请先录入教师；后续授课分配、班主任和自动分配都会用到。',
        _make_actions(('去教师管理', '/teachers')),
    ))
    steps.append(_make_step(
        'classes',
        '班级管理',
        '录入班级、年级和班主任；年级会决定哪些课程适用于该班。',
        'completed' if classes else 'pending',
        f"已录入 {len(classes)} 个班级，可继续核对班主任和适用课程。" if classes else '请先录入班级；没有班级就无法生成班级课表。',
        _make_actions(('去班级管理', '/classes')),
    ))
    steps.append(_make_step(
        'subjects',
        '课程管理',
        '录入课程周课时、适用年级和课程属性；普通课程、校本课程和班会课都从这里定义。',
        'completed' if subjects else 'pending',
        f"已录入 {len(subjects)} 门课程，可继续核对周课时、适用年级和课程属性。" if subjects else '请先录入课程；没有课程就无法计算每班周课时。',
        _make_actions(('去课程管理', '/subjects')),
    ))

    if not subjects or not classes:
        location_step_status = 'pending'
        location_step_detail = '请先补齐班级和课程，再判断是否需要为专用场地课程配置容量。'
    elif missing_location_labels:
        location_step_status = 'blocked'
        location_step_detail = f"以下专用场地类型还没有容量：{_preview_names(missing_location_labels)}。"
    elif required_location_labels:
        location_step_status = 'completed'
        location_step_detail = f"专用场地容量已覆盖：{_preview_names(required_location_labels)}。"
    else:
        location_step_status = 'completed'
        location_step_detail = '当前待排课程都可使用普通教室，无需额外场地容量。'
    steps.append(_make_step(
        'locations',
        '场地管理',
        '仅在课程需要操场、实验室、家政室等专用场地时配置容量；普通教室不需要单独配置。',
        location_step_status,
        location_step_detail,
        _make_actions(('去场地管理', '/locations')),
    ))
    if not teachers:
        travel_groups_step_status = 'pending'
        travel_groups_step_detail = '请先录入教师，再按需要为跨校或送教教师配置整天禁排日。'
    elif not travel_groups:
        travel_groups_step_status = 'warning'
        travel_groups_step_detail = '当前还没有送教分组；只有存在跨校或送教教师时才需要设置。'
    else:
        travel_group_teacher_count = sum(1 for teacher in teachers if teacher.travel_group_id)
        travel_groups_step_status = 'completed'
        travel_groups_step_detail = f"已配置 {len(travel_groups)} 个送教分组，当前有 {travel_group_teacher_count} 位教师已绑定分组。"
    steps.append(_make_step(
        'travel_groups',
        '送教分组',
        '为需要整天避开某个工作日的送教教师建立分组；教师绑定分组后，该禁排日会直接进入排课约束。',
        travel_groups_step_status,
        travel_groups_step_detail,
        _make_actions(('去送教分组', '/travel-groups')),
    ))
    if not teachers:
        blocked_times_step_status = 'pending'
        blocked_times_step_detail = '请先录入教师，再按教师设置某天上午、下午或全天不可排。'
    elif blocked_times_count == 0:
        blocked_times_step_status = 'warning'
        blocked_times_step_detail = '当前还没有教师禁排；只有教师存在明确不可排时段时才需要补充。'
    else:
        blocked_times_step_status = 'completed'
        blocked_times_step_detail = f"已设置 {blocked_times_count} 条教师禁排。"
    steps.append(_make_step(
        'blocked_times',
        '教师禁排',
        '为单个教师设置某天上午、下午或全天不可排；只在确有固定不可排时段时使用。',
        blocked_times_step_status,
        blocked_times_step_detail,
        _make_actions(('去教师禁排', '/blocked-times')),
    ))
    if not subjects:
        combined_groups_step_status = 'pending'
        combined_groups_step_detail = '请先录入课程，再判断是否存在校本课程或合班课需要分组。'
    elif not combined_subject:
        combined_groups_step_status = 'completed'
        combined_groups_step_detail = '当前没有标记为校本课程/合班课的课程，无需配置校本课程分组。'
    elif len(combined_groups) < 4:
        combined_groups_step_status = 'blocked'
        combined_groups_step_detail = f'当前只有 {len(combined_groups)} 个分组；按当前实现，校本课程至少需要 4 组。'
    else:
        combined_group_teacher_count = sum(1 for teacher in teachers if teacher.combined_class_group_id and not teacher.exclude_from_combined)
        combined_groups_step_status = 'completed'
        combined_groups_step_detail = f"已配置 {len(combined_groups)} 个校本课程分组，当前有 {combined_group_teacher_count} 位教师手动绑定到分组。"
    steps.append(_make_step(
        'combined_groups',
        '校本课程分组',
        '仅在存在校本课程/合班课时使用；当前实现要求先建立至少 4 个分组，再由教师手动绑定或系统自动补分组。',
        combined_groups_step_status,
        combined_groups_step_detail,
        _make_actions(('去校本课程分组', '/combined-groups')),
    ))

    if not subjects or not classes:
        qualification_step_status = 'pending'
        qualification_step_detail = '请先录入班级和课程，再设置可授课教师。'
    elif subjects_without_qualification:
        qualification_step_status = 'blocked'
        qualification_step_detail = f"仍有 {len(subjects_without_qualification)} 门普通课程没有可授课教师。"
    else:
        qualification_step_status = 'completed'
        qualification_step_detail = '所有需要进入常规排课的课程都已配置可授课教师。'
    steps.append(_make_step(
        'qualifications',
        '教师资质',
        '为每门普通课程勾选可授课教师，自动分配和校验都会按这里的名单执行。',
        qualification_step_status,
        qualification_step_detail,
        _make_actions(('去教师资质', '/qualifications')),
    ))

    if invalid_assignments:
        assignment_step_status = 'blocked'
        assignment_step_detail = f"有 {len(invalid_assignments)} 条授课分配与教师资质不一致。"
    elif not expected_assignment_pairs_count:
        assignment_step_status = 'pending'
        assignment_step_detail = '当前还没有需要进入常规排课的班级课程。'
    elif not missing_assignment_pairs:
        assignment_step_status = 'completed'
        assignment_step_detail = f"已为全部 {expected_assignment_pairs_count} 个班级课程设置任课教师。"
    elif assignment_count == 0:
        assignment_step_status = 'warning'
        assignment_step_detail = '当前还没有手动指定教师；系统会在排课时按资质自动分配普通课程。'
    else:
        assignment_step_status = 'warning'
        assignment_step_detail = (
            f"已设置 {assignment_count}/{expected_assignment_pairs_count} 个班级课程的任课教师，"
            '其余会在排课时按资质自动分配。'
        )
    steps.append(_make_step(
        'assignments',
        '授课分配',
        '为班级的普通课程指定任课教师；手动指定会保留，未指定的部分可在排课时自动分配。',
        assignment_step_status,
        assignment_step_detail,
        _make_actions(('去授课分配', '/assignments')),
    ))
    if not classes or not subjects:
        locks_step_detail = '请先补齐班级和课程；如果后续需要把某节已分配课程固定到具体时段，可再使用课表锁定。'
    elif manual_assignment_count == 0:
        locks_step_detail = '当前还没有手动指定教师的班级课程；只有需要固定某节已分配课程时，才需要使用课表锁定。'
    elif len(locks) == 0:
        locks_step_detail = '当前还没有班级课程锁定；如需把某节已分配课程固定到具体时段，可按需使用。'
    else:
        locks_step_detail = f"已设置 {len(locks)} 条班级课程锁定；该功能仅在需要固定具体时段时使用。"
    steps.append(_make_step(
        'locks',
        '课表锁定',
        '把某个班里已手动分配教师的课程固定到具体时段；这是可选功能，不设置也不会影响排课。',
        'optional',
        locks_step_detail,
        _make_actions(('去课表锁定', '/schedule-locks')),
    ))
    if successful_results_count > 0:
        run_step_status = 'completed'
        run_step_detail = f"已执行过试排，当前已有 {successful_results_count} 个可用排课结果。"
        run_actions = _make_actions(('去执行排课', '/schedule-run'))
    elif can_run:
        run_step_status = 'ready'
        run_step_detail = '阻塞项已清除，可以开始执行一次试排。'
        run_actions = _make_actions(('去执行排课', '/schedule-run'))
    else:
        run_step_status = 'blocked'
        run_step_detail = f"仍有 {len(blocking_issues)} 个阻塞项未处理，暂时不能开始试排。"
        run_actions = _make_actions(('查看排课检查', '/schedule-run'))
    steps.append(_make_step(
        'run',
        '执行排课',
        '按本次运行参数发起一次求解，生成新的排课结果。',
        run_step_status,
        run_step_detail,
        run_actions,
    ))
    if successful_results_count > 0:
        schedule_view_step_status = 'completed'
        schedule_view_step_detail = f"已有 {successful_results_count} 个可用结果，可按班级或教师查看并导出。"
    elif can_run:
        schedule_view_step_status = 'pending'
        schedule_view_step_detail = '请先完成至少一次试排，再到课表查看中核对班级表、教师表和导出结果。'
    else:
        schedule_view_step_status = 'pending'
        schedule_view_step_detail = '先处理前置阻塞项并完成试排，之后才能查看课表结果。'
    steps.append(_make_step(
        'schedule_view',
        '课表查看',
        '按班级或教师查看排课结果，并导出 Excel / JSON。',
        schedule_view_step_status,
        schedule_view_step_detail,
        _make_actions(('去课表查看', '/schedule-view')),
    ))

    passed_checks = []
    if teachers:
        passed_checks.append({
            'key': 'teachers',
            'title': '教师数据已录入',
            'detail': f'当前共有 {len(teachers)} 位教师，可用于班主任、授课分配和自动分配。',
        })
    if classes:
        passed_checks.append({
            'key': 'classes',
            'title': '班级数据已录入',
            'detail': f'当前共有 {len(classes)} 个班级。',
        })
    if subjects:
        passed_checks.append({
            'key': 'subjects',
            'title': '课程数据已录入',
            'detail': f'当前共有 {len(subjects)} 门课程。',
        })
    if required_subjects and not subjects_without_qualification:
        passed_checks.append({
            'key': 'qualifications',
            'title': '待排普通课程资质已覆盖',
            'detail': '所有需要进入常规排课的课程都已配置可授课教师。',
        })
    if expected_assignment_pairs_count and not invalid_assignments:
        passed_checks.append({
            'key': 'assignments',
            'title': '现有授课分配与教师资质一致',
            'detail': '当前没有发现“已分配教师但无该课程资质”的冲突。',
        })
    if locks and not lock_overflows:
        passed_checks.append({
            'key': 'locks',
            'title': '班级课程锁定未超周课时',
            'detail': '当前每个班级课程的锁定数量都没有超过该课程周课时。',
        })
    if required_subjects and not capacity_shortages and supply_gap <= 0:
        passed_checks.append({
            'key': 'teacher_capacity',
            'title': '教师授课容量充足',
            'detail': (
                f'各课程合格教师可覆盖所有班级，且教师总可授课时（约 {total_teacher_supply} 节）'
                f'不低于普通课程需求（{normal_subject_hours} 节）。'
            ),
        })

    countable_steps = [step for step in steps if step['status'] != 'optional']

    summary = {
        'teachers_count': len(teachers),
        'classes_count': len(classes),
        'subjects_count': len(subjects),
        'locations_count': len(locations),
        'assignments_count': assignment_count,
        'manual_assignments_count': manual_assignment_count,
        'auto_assignments_count': auto_assignment_count,
        'qualifications_count': len(qualifications),
        'blocked_times_count': blocked_times_count,
        'locks_count': len(locks),
        'successful_results_count': successful_results_count,
        'expected_assignment_pairs_count': expected_assignment_pairs_count,
        'missing_assignment_pairs_count': len(missing_assignment_pairs),
        'blocking_issue_count': len(blocking_issues),
        'warning_issue_count': len(warning_issues),
        'can_run': can_run,
        'completed_steps': sum(1 for step in countable_steps if step['status'] == 'completed'),
        'total_steps': len(countable_steps),
        'total_school_hours': total_school_hours,
        'average_teacher_hours': average_teacher_hours,
        'normal_subject_hours': normal_subject_hours,
        'estimated_min_teachers': estimated_min_teachers,
        'teacher_capacity_shortage_count': len(capacity_shortages),
    }

    return {
        'summary': summary,
        'steps': steps,
        'blocking_issues': blocking_issues,
        'warning_issues': warning_issues,
        'passed_checks': passed_checks,
    }


@api_view(['GET'])
def schedule_precheck(request):
    """返回首页和排课页共用的排课前检查信息"""
    return Response(_build_precheck_payload())


class ScheduleResultViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    queryset = ScheduleResult.objects.all()
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    pagination_class = ScheduleResultPagination

    def get_queryset(self):
        qs = ScheduleResult.objects.annotate(entry_count=Count('entries'))
        params = self.request.query_params

        is_favorite = params.get('is_favorite')
        if is_favorite in ('true', '1'):
            qs = qs.filter(is_favorite=True)
        elif is_favorite in ('false', '0'):
            qs = qs.filter(is_favorite=False)

        solve_status = params.get('solve_status')
        if solve_status:
            qs = qs.filter(solve_status=solve_status)

        search = params.get('search')
        if search:
            qs = qs.filter(name__icontains=search.strip())

        return qs.order_by('-is_favorite', '-created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleResultListSerializer
        if self.action in ['partial_update', 'update']:
            return ScheduleResultUpdateSerializer
        return ScheduleResultSerializer

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        save_kwargs = {}
        if 'name' in serializer.validated_data:
            save_kwargs['name'] = serializer.validated_data['name'].strip()
        if 'is_favorite' in serializer.validated_data:
            save_kwargs['is_favorite'] = serializer.validated_data['is_favorite']
        serializer.save(**save_kwargs)
        return Response(ScheduleResultListSerializer(instance).data)

    def perform_destroy(self, instance):
        with transaction.atomic():
            was_active = instance.is_active
            instance.delete()
            self._ensure_active_fallback(was_active)

    @action(detail=False, methods=['post'], url_path='bulk_delete')
    def bulk_delete(self, request):
        ids = request.data.get('ids') or []
        if not isinstance(ids, list) or not ids:
            return Response(
                {'error': '需要提供 ids 数组'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            qs = ScheduleResult.objects.filter(pk__in=ids)
            had_active = qs.filter(is_active=True).exists()
            deleted_count, _ = qs.delete()
            self._ensure_active_fallback(had_active)

        return Response({'deleted': deleted_count})

    @staticmethod
    def _ensure_active_fallback(was_active):
        if not was_active:
            return
        fallback = ScheduleResult.objects.filter(
            solve_status__in=['OPTIMAL', 'FEASIBLE']
        ).order_by('-is_favorite', '-created_at').first()
        if fallback:
            fallback.is_active = True
            fallback.save(update_fields=['is_active'])


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
        result = ScheduleResult.objects.get(pk=result_id)

        if not teacher.exclude_from_combined:
            # 从排课结果中获取分组信息
            # 格式: {"分组名": {"周二": ["教师名"], "周四": ["教师名"]}, ...}
            combined_assignments = result.combined_class_assignments or {}
            teacher_name = teacher.name

            # 查找教师在哪个分组的哪个日期
            assigned_day = None
            assigned_group = None
            for group_name, day_data in combined_assignments.items():
                if isinstance(day_data, dict):
                    if teacher_name in day_data.get("周二", []):
                        assigned_day = 1  # 周二
                        assigned_group = group_name
                        break
                    elif teacher_name in day_data.get("周四", []):
                        assigned_day = 3  # 周四
                        assigned_group = group_name
                        break

            if assigned_day is not None:
                # 获取校本课程时段
                settings = SchedulerSettings.objects.first()
                if settings:
                    combined_slots = settings.get_combined_class_slots_list()

                    # 只添加该教师分配日期的校本课程时段
                    for day, period in combined_slots:
                        if day == assigned_day:
                            data.append({
                                'id': None,
                                'day': day,
                                'period': period,
                                'subject_name': '校本课程',
                                'school_class_name': f'({assigned_group})',
                                'teacher_name': teacher_name,
                                'is_locked': True,
                            })
    except (Teacher.DoesNotExist, ScheduleResult.DoesNotExist):
        pass

    # 按 day, period 排序
    data.sort(key=lambda x: (x['day'], x['period']))
    return Response(data)
