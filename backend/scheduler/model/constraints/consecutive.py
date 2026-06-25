"""H9 教师连续禁排（跨指定节次边界，如课间操/午休）。"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_consecutive_forbidden_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """同一教师不得跨禁排节次对连续上课（不分班级、不分是否允许连堂）。

    ∀ t, d, (p1,p2)∈forbidden: sum_{c,s} busy[c,s,t,d,p1] + sum_{c,s} busy[c,s,t,d,p2] ≤ 1
    """
    pairs = problem.calendar.consecutive_forbidden_pairs
    if not pairs:
        return

    by_tdp: dict[tuple[int, int, int], list] = defaultdict(list)
    for (c, s, t, d, p), b in variables.busy.items():
        by_tdp[(t, d, p)].append(b)

    teacher_days = {(t, d) for (t, d, _p) in by_tdp}
    for t, d in teacher_days:
        for p1, p2 in pairs:
            lits = by_tdp.get((t, d, p1), []) + by_tdp.get((t, d, p2), [])
            if len(lits) > 1:
                model.Add(sum(lits) <= 1)
