"""H13 教师禁排时段（am / pm / all）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_blocked_time_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """教师在禁排时段不排课：相关 busy 置 0。

    period_type：am -> [0, am_periods)，pm -> [am_periods, 当天节数)，all -> 全天。
    """
    cal = problem.calendar

    blocked: dict[int, set] = {}
    for t, teacher in problem.teachers.items():
        if not teacher.blocked_times:
            continue
        slots: set[tuple[int, int]] = set()
        for day, period_type in teacher.blocked_times:
            day_periods = cal.periods_per_day[day] if day < len(cal.periods_per_day) else 0
            if period_type == "am":
                rng = range(0, cal.am_periods)
            elif period_type == "pm":
                rng = range(cal.am_periods, day_periods)
            else:  # all
                rng = range(0, day_periods)
            for p in rng:
                slots.add((day, p))
        if slots:
            blocked[t] = slots

    if not blocked:
        return

    for (c, s, t, d, p), b in variables.busy.items():
        if t in blocked and (d, p) in blocked[t]:
            model.Add(b == 0)
