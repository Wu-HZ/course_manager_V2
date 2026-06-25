"""H8 课程单日上限。"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_max_daily_limit_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """同一 (班, 课) 一天不超过 max_daily_limit 节。∀(c,s),d: sum_p place ≤ max_daily(s)。"""
    by_csd: dict[tuple[int, int, int], list] = defaultdict(list)
    for (c, s, d, p), pl in variables.place.items():
        by_csd[(c, s, d)].append(pl)

    for (c, s, d), lits in by_csd.items():
        max_daily = problem.subjects[s].max_daily_limit
        if len(lits) > max_daily:
            model.Add(sum(lits) <= max_daily)
