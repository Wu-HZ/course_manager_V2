"""H11 教师同班单日上限。"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_teacher_class_daily_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """同一教师同一天在同一班级不超过 h11 节。∀t,c,d: sum_{s,p} busy ≤ h11。"""
    cap = problem.config.h11_teacher_class_daily_max
    by_tcd: dict[tuple[int, int, int], list] = defaultdict(list)
    for (c, s, t, d, p), b in variables.busy.items():
        by_tcd[(t, c, d)].append(b)

    for lits in by_tcd.values():
        if len(lits) > cap:
            model.Add(sum(lits) <= cap)
