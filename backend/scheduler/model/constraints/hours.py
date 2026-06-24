"""H1 周课时约束。"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_weekly_hours_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """每班每课排进的片数 == weekly_hours − 已锁定数。

    已被用户锁定的课时不在 place 变量里（片已排除），故只需排「剩余」节数。
    """
    place_by_demand: dict[tuple[int, int], list] = defaultdict(list)
    for (c, s, d, p), pl in variables.place.items():
        place_by_demand[(c, s)].append(pl)

    for demand in problem.demands:
        pls = place_by_demand.get((demand.class_id, demand.subject_id), [])
        remaining = demand.hours_to_place
        if remaining > 0:
            model.Add(sum(pls) == remaining)
        else:
            # 课时已全部被锁定（或数据异常 remaining<0）：不再额外排片。
            for pl in pls:
                model.Add(pl == 0)
