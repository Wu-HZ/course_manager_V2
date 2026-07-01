"""ORM → 领域对象的唯一转换层。

镜像旧 ``engine.load_data()`` 的数据读取与 ``auto_assign_teachers()`` 里
``active(c, s)`` 的判定规则（跳过班会、校本、年级不适用），但**不做任何派课决策**
——派课交给求解器。是除 ``persistence.py`` 外唯一 import Django 的模块。
"""
from __future__ import annotations

from collections import defaultdict

from core.models import (
    ClassSubjectTeacher,
    Location,
    SchedulerSettings,
    SchoolClass,
    ScheduleLock,
    Subject,
    Teacher,
    TeacherBlockedTime,
    TeacherQualification,
)

from .domain import (
    Calendar,
    ClassInfo,
    CourseDemand,
    LockedEntry,
    ScheduleProblem,
    SchedulerConfig,
    SubjectInfo,
    TeacherInfo,
)
from .time_slots import (
    AM_PERIODS,
    CONSECUTIVE_FORBIDDEN_PAIRS,
    FRIDAY_CLASS_MEETING,
    PERIODS_PER_DAY,
)


def _parse_pairs(raw, fallback):
    """解析 ``"1,2;3,4"`` 形式的节次对配置，失败回退默认值。"""
    pairs = []
    try:
        for part in raw.split(";"):
            part = part.strip()
            if not part:
                continue
            a, b = part.split(",")
            pairs.append((int(a.strip()), int(b.strip())))
    except (ValueError, AttributeError):
        return tuple(fallback)
    return tuple(pairs) or tuple(fallback)


def build_calendar(settings: SchedulerSettings) -> Calendar:
    """把旧 ``time_slots`` 常量 + settings 收敛成一个 :class:`Calendar`。"""
    periods = tuple(PERIODS_PER_DAY[d] for d in sorted(PERIODS_PER_DAY))
    return Calendar(
        periods_per_day=periods,
        am_periods=AM_PERIODS,
        class_meeting_slot=FRIDAY_CLASS_MEETING,
        combined_slots=frozenset(settings.get_combined_class_slots_list()),
        consecutive_forbidden_pairs=_parse_pairs(
            settings.h9_consecutive_forbidden, CONSECUTIVE_FORBIDDEN_PAIRS
        ),
    )


def load_problem(school) -> tuple[ScheduleProblem, list[str]]:
    """从数据库读出一次完整排课输入（按学校过滤）。

    返回 ``(problem, errors)``；``errors`` 非空表示存在求解前即可判定的静态死结
    （目前仅：某 active 课程无任何合格教师且未手动派课）。
    """
    settings = SchedulerSettings.get_settings(school)
    calendar = build_calendar(settings)
    errors: list[str] = []

    classes = {
        c.id: ClassInfo(
            id=c.id, name=c.name, grade=c.grade,
            homeroom_teacher_id=c.homeroom_teacher_id,
        )
        for c in SchoolClass.objects.filter(school=school)
    }

    subjects: dict[int, SubjectInfo] = {}
    subject_objs: dict[int, Subject] = {}
    class_meeting_id: int | None = None
    combined_subject_id: int | None = None
    for s in Subject.objects.filter(school=school):
        subject_objs[s.id] = s
        subjects[s.id] = SubjectInfo(
            id=s.id,
            name=s.name,
            weekly_hours=s.weekly_hours,
            is_main_subject=s.is_main_subject,
            location_type=s.location_type,
            max_teacher_classes=s.max_teacher_classes,
            max_daily_limit=s.max_daily_limit,
            is_am_preferred=s.is_am_preferred,
            allow_consecutive=s.allow_consecutive,
            avoid_first_period=s.avoid_first_period,
        )
        if s.name == settings.class_meeting_name:
            class_meeting_id = s.id
        if s.is_combined_class:
            combined_subject_id = s.id

    blocked: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for bt in TeacherBlockedTime.objects.filter(school=school):
        blocked[bt.teacher_id].append((bt.day, bt.period_type))

    teachers: dict[int, TeacherInfo] = {}
    for t in Teacher.objects.select_related("travel_group").filter(school=school):
        day_off = t.travel_group.day_off if t.travel_group_id else None
        teachers[t.id] = TeacherInfo(
            id=t.id,
            name=t.name,
            day_off=day_off,
            min_weekly_hours=t.min_weekly_hours,
            max_weekly_hours=t.max_weekly_hours,
            blocked_times=tuple(blocked.get(t.id, ())),
        )

    qualified: dict[int, set[int]] = defaultdict(set)
    for q in TeacherQualification.objects.filter(school=school):
        qualified[q.subject_id].add(q.teacher_id)
    qualified_teachers = {sid: frozenset(ts) for sid, ts in qualified.items()}

    forced: dict[tuple[int, int], int] = {}
    for cst in ClassSubjectTeacher.objects.filter(school=school, is_manual=True):
        forced[(cst.school_class_id, cst.subject_id)] = cst.teacher_id

    raw_locks: dict[int, set] = defaultdict(set)
    user_lock_counts: dict[tuple[int, int], int] = defaultdict(int)
    teacher_locked_hours: dict[int, int] = defaultdict(int)
    user_lock_records: list[tuple[int, int, int | None, int, int]] = []
    for lock in ScheduleLock.objects.filter(school=school):
        raw_locks[lock.school_class_id].add((lock.day, lock.period))
        user_lock_counts[(lock.school_class_id, lock.subject_id)] += 1
        if lock.teacher_id:
            teacher_locked_hours[lock.teacher_id] += 1
        user_lock_records.append(
            (lock.school_class_id, lock.subject_id, lock.teacher_id, lock.day, lock.period)
        )
    locks_by_class = {cid: frozenset(slots) for cid, slots in raw_locks.items()}

    location_capacity = {
        loc.location_type: loc.capacity for loc in Location.objects.filter(school=school)
    }

    # 枚举 active(c, s)：普通课程才进模型（排除班会、校本、年级不适用）。
    demands: list[CourseDemand] = []
    missing_qual_reported: set[int] = set()
    for class_id, c in classes.items():
        for subject_id, s_obj in subject_objs.items():
            if subject_id == class_meeting_id:
                continue
            if s_obj.is_combined_class:
                continue
            if not s_obj.is_applicable_for_grade(c.grade):
                continue
            demands.append(
                CourseDemand(
                    class_id=class_id,
                    subject_id=subject_id,
                    weekly_hours=s_obj.weekly_hours,
                    locked_count=user_lock_counts.get((class_id, subject_id), 0),
                )
            )
            # 静态预检：非手动派课但无任何合格教师 → 必然无解。
            if (class_id, subject_id) not in forced and not qualified_teachers.get(subject_id):
                if subject_id not in missing_qual_reported:
                    missing_qual_reported.add(subject_id)
                    errors.append(f"课程「{s_obj.name}」未配置任何可授课教师（资质为空）。")

    config = SchedulerConfig(
        h11_teacher_class_daily_max=settings.h11_teacher_class_daily_max,
        h14_homeroom_main_subject=settings.h14_homeroom_main_subject,
        h15_teacher_max_main_subjects=settings.h15_teacher_max_main_subjects,
        s1_am_preference_weight=settings.s1_am_preference_weight,
        s2_consecutive_weight=settings.s2_consecutive_weight,
        s3_distribution_weight=settings.s3_distribution_weight,
        s4_teacher_daily_threshold=settings.s4_teacher_daily_threshold,
        s4_teacher_daily_weight=settings.s4_teacher_daily_weight,
        s5_avoid_first_weight=settings.s5_avoid_first_weight,
        s6_subject_switch_weight=settings.s6_subject_switch_weight,
        s7_same_class_subject_switch_weight=settings.s7_same_class_subject_switch_weight,
    )

    # 预锁定条目：班会(→班主任)、校本(→无教师)、用户锁定(教师缺省取授课分配)。
    locked_entries: list[LockedEntry] = []
    if class_meeting_id is not None and calendar.class_meeting_slot is not None:
        mday, mperiod = calendar.class_meeting_slot
        for class_id, c in classes.items():
            if c.homeroom_teacher_id is not None:
                locked_entries.append(
                    LockedEntry(class_id, class_meeting_id, c.homeroom_teacher_id, mday, mperiod)
                )
    if combined_subject_id is not None:
        for class_id in classes:
            for day, period in sorted(calendar.combined_slots):
                locked_entries.append(
                    LockedEntry(class_id, combined_subject_id, None, day, period)
                )
    for class_id, subject_id, teacher_id, day, period in user_lock_records:
        if teacher_id is None:
            teacher_id = forced.get((class_id, subject_id))
        locked_entries.append(LockedEntry(class_id, subject_id, teacher_id, day, period))

    problem = ScheduleProblem(
        calendar=calendar,
        classes=classes,
        subjects=subjects,
        teachers=teachers,
        demands=tuple(demands),
        qualified_teachers=qualified_teachers,
        forced_assignments=forced,
        locks_by_class=locks_by_class,
        config=config,
        location_capacity=location_capacity,
        teacher_locked_hours=dict(teacher_locked_hours),
        locked_entries=tuple(locked_entries),
    )
    return problem, errors
