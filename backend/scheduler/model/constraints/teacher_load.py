"""H10 教师周课时上下限。"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_teacher_hours_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """教师周总课时（实际排课 busy 之和 + 已锁定）落在 [min, max]，各自可空。

    用 busy 求和而非 assign·h(s)，这样含 user_lock 占用、与旧引擎 ``sum(place)+locked``
    口径一致。
    """
    busy_by_teacher: dict[int, list] = defaultdict(list)
    for (c, s, t, d, p), b in variables.busy.items():
        busy_by_teacher[t].append(b)

    for t, teacher in problem.teachers.items():
        lits = busy_by_teacher.get(t, [])
        locked = problem.teacher_locked_hours.get(t, 0)
        if teacher.max_weekly_hours is not None:
            # 即使 lits 为空也加：max-locked<0 时正确判为无解
            model.Add(sum(lits) <= teacher.max_weekly_hours - locked)
        if teacher.min_weekly_hours is not None:
            remaining = teacher.min_weekly_hours - locked
            if remaining > 0 and lits:
                model.Add(sum(lits) >= remaining)
