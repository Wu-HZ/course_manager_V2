"""解 → ScheduleResult/ScheduleEntry 落库。

与 ``repository.py`` 并列，是仅有的两个直接碰 Django ORM 的模块之一。落库契约
与旧 ``engine.save_result`` 完全一致：预锁定条目写 ``is_locked=True``，求解课时写
``is_locked=False``，前端/导出零改动。
"""
from __future__ import annotations

import random

from django.db import transaction

from .domain import ScheduleProblem
from .models import ScheduleEntry, ScheduleResult
from .solver import SolveResult


def _build_combined_class_assignments(problem: ScheduleProblem) -> dict:
    """校本课程教师分组分配 → 教师课表视图可消费的格式。

    提取/复刻旧 ``engine.assign_combined_class_teachers`` + ``save_combined_class_assignments``
    的核心逻辑：把教师分到 4 个 CombinedClassGroup，再拆为周二/周四组，全局平衡。
    不使用旧引擎实例（那需要 load_data 等副作用），直接从 domain 对象出发。
    """
    from core.models import CombinedClassGroup

    groups = list(CombinedClassGroup.objects.all().order_by("id"))
    if len(groups) < 4:
        return {}

    # 找出校本课程的 subject_id
    combined_subject_id: int | None = None
    for sid, s in problem.subjects.items():
        if s.name == "校本课程":  # 目前唯一 is_combined_class 课
            combined_subject_id = sid
            break
    if combined_subject_id is None:
        # 按标记找（万一改名）
        for sid, s in problem.subjects.items():
            if s.name != "班会" and s.weekly_hours == 4:
                combined_subject_id = sid
                break
    if combined_subject_id is None:
        return {}

    # 1. 收集可用教师：排除 exclude_from_combined，其余都进(禁排日只在分 Tue/Thu 时影响)
    from core.models import Teacher
    teacher_qs = Teacher.objects.exclude(exclude_from_combined=True).select_related("travel_group")
    available: dict[int, "Teacher"] = {}
    for t in teacher_qs:
        if t.id not in problem.teachers:
            continue
        available[t.id] = t

    # 2. 按组收集（手动指定优先）
    group_teachers: dict[int, list[int]] = {g.id: [] for g in groups}
    unassigned: list[int] = []
    for tid, t in available.items():
        if t.combined_class_group_id and t.combined_class_group_id in group_teachers:
            group_teachers[t.combined_class_group_id].append(tid)
        else:
            unassigned.append(tid)

    # 3. 随机分配未指定教师到人最少的组
    random.shuffle(unassigned)
    for tid in unassigned:
        min_gid = min(group_teachers, key=lambda g: len(group_teachers[g]))
        group_teachers[min_gid].append(tid)

    # 4. 每组拆 Tuesday / Thursday（按手动指定 + 禁排日 + 全局平衡）
    result: dict[int, dict] = {gid: {"tuesday": [], "thursday": []} for gid in group_teachers}
    flexible: list[tuple[int, int]] = []
    for gid, tids in group_teachers.items():
        for tid in tids:
            t = problem.teachers[tid]
            manual = available[tid].combined_class_day
            can_tue = t.day_off != 1
            can_thu = t.day_off != 3
            if manual == 1 and can_tue:
                result[gid]["tuesday"].append(tid)
            elif manual == 3 and can_thu:
                result[gid]["thursday"].append(tid)
            elif can_tue and not can_thu:
                result[gid]["tuesday"].append(tid)
            elif can_thu and not can_tue:
                result[gid]["thursday"].append(tid)
            else:
                flexible.append((tid, gid))

    random.shuffle(flexible)
    for tid, gid in flexible:
        n_tue = len(result[gid]["tuesday"])
        n_thu = len(result[gid]["thursday"])
        if n_tue < n_thu:
            result[gid]["tuesday"].append(tid)
        elif n_thu < n_tue:
            result[gid]["thursday"].append(tid)
        else:
            global_tue = sum(len(r["tuesday"]) for r in result.values())
            global_thu = sum(len(r["thursday"]) for r in result.values())
            if global_tue <= global_thu:
                result[gid]["tuesday"].append(tid)
            else:
                result[gid]["thursday"].append(tid)

    # 5. id → name
    groups_by_id = {g.id: g.name for g in groups}
    return {
        groups_by_id[gid]: {
            "周二": [problem.teachers[tid].name for tid in r["tuesday"] if tid in problem.teachers],
            "周四": [problem.teachers[tid].name for tid in r["thursday"] if tid in problem.teachers],
        }
        for gid, r in result.items()
    }


@transaction.atomic
def persist(
    problem: ScheduleProblem,
    result: SolveResult,
    name: str = "",
    activate: bool = True,
) -> ScheduleResult:
    """把求解结果写回数据库，返回创建的 :class:`ScheduleResult`。

    一个事务内完成；``activate=True`` 且有可行解时设为当前使用（其余结果自动取消激活）。
    """
    combined_assignments = _build_combined_class_assignments(problem)

    schedule = ScheduleResult.objects.create(
        name=name,
        solve_status=result.status,
        solve_time_ms=result.solve_time_ms,
        is_active=activate and result.status in ("OPTIMAL", "FEASIBLE"),
        combined_class_assignments=combined_assignments,
    )

    entries = [
        ScheduleEntry(
            result=schedule,
            school_class_id=le.class_id,
            subject_id=le.subject_id,
            teacher_id=le.teacher_id,
            day=le.day,
            period=le.period,
            is_locked=True,
        )
        for le in problem.locked_entries
    ]
    entries += [
        ScheduleEntry(
            result=schedule,
            school_class_id=lesson.class_id,
            subject_id=lesson.subject_id,
            teacher_id=lesson.teacher_id,
            day=lesson.day,
            period=lesson.period,
            is_locked=False,
        )
        for lesson in result.lessons
    ]
    ScheduleEntry.objects.bulk_create(entries)
    return schedule
