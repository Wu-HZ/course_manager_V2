"""解 → ScheduleResult/ScheduleEntry 落库。

与 ``repository.py`` 并列，是仅有的两个直接碰 Django ORM 的模块之一。落库契约
与旧 ``engine.save_result`` 完全一致：预锁定条目写 ``is_locked=True``，求解课时写
``is_locked=False``，前端/导出零改动。
"""
from __future__ import annotations

from django.db import transaction

from .domain import ScheduleProblem
from .models import ScheduleEntry, ScheduleResult
from .solver import SolveResult


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
    schedule = ScheduleResult.objects.create(
        name=name,
        solve_status=result.status,
        solve_time_ms=result.solve_time_ms,
        is_active=activate and result.status in ("OPTIMAL", "FEASIBLE"),
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
