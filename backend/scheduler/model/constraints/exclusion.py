"""H2 班级互斥、H3 教师互斥。"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_class_exclusion_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """H2：同一班级同一时间片至多一门课。∀c,d,p: sum_s place ≤ 1。"""
    by_cdp: dict[tuple[int, int, int], list] = defaultdict(list)
    for (c, s, d, p), pl in variables.place.items():
        by_cdp[(c, d, p)].append(pl)
    for lits in by_cdp.values():
        if len(lits) > 1:
            model.Add(sum(lits) <= 1)


def add_teacher_exclusion_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """H3：同一教师同一时间片至多一节课。∀t,d,p: sum_{c,s} busy ≤ 1。

    这是联合模型相对旧引擎的关键差异：旧引擎靠定死的 teacher_assignments 查表，
    新引擎直接约束 busy——教师是谁本身就是求解器的决策。

    额外：如果某教师被课表锁定（ScheduleLock）在本班之外的某班某时间片，则求解器
    必须保证该教师在同时间片不能再被派到其他班——即强制该教师在该时间片的
    busy 变量和为 0。
    """
    by_tdp: dict[tuple[int, int, int], list] = defaultdict(list)
    for (c, s, t, d, p), b in variables.busy.items():
        by_tdp[(t, d, p)].append(b)
    for lits in by_tdp.values():
        if len(lits) > 1:
            model.Add(sum(lits) <= 1)

    for t, slots in problem.teacher_locked_slots.items():
        for d, p in slots:
            lits = by_tdp.get((t, d, p), [])
            if lits:
                model.Add(sum(lits) == 0)
