"""H5 场地容量。"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_location_capacity_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """同一时间片使用同类（非普通教室）场地的课不超过该场地容量。

    ∀ loc_type≠NORMAL, d, p: sum_{(c,s): location_type==loc_type} place ≤ capacity
    普通教室（NORMAL）默认不限容量，跳过。
    """
    by_loc_slot: dict[tuple[str, int, int], list] = defaultdict(list)
    for (c, s, d, p), pl in variables.place.items():
        loc_type = problem.subjects[s].location_type
        if loc_type == "NORMAL":
            continue
        by_loc_slot[(loc_type, d, p)].append(pl)

    for (loc_type, d, p), lits in by_loc_slot.items():
        capacity = problem.location_capacity.get(loc_type, 1)
        if len(lits) > capacity:
            model.Add(sum(lits) <= capacity)
