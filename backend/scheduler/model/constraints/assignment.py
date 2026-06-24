"""派课基数与 place↔assign 联结约束。

虽不在旧引擎的「H 编号」里，但它们是联合模型成立的前提：保证每门课恰好一位老师，
且被排进时间表的每一片都由其指派教师承担。
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_assignment_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    # 每个 active(c, s) 恰好一位老师：sum_t assign[c, s, t] == 1
    for demand in problem.demands:
        c, s = demand.class_id, demand.subject_id
        lits = [
            variables.assign[(c, s, t)]
            for t in problem.candidate_teachers(c, s)
            if (c, s, t) in variables.assign
        ]
        if lits:
            model.AddExactlyOne(lits)

    # 联结：∀(c, s, d, p)  sum_t busy[c, s, t, d, p] == place[c, s, d, p]
    # 即被排的片恰由其指派教师上；与 sum_t assign==1 一起保证派课/排时一致。
    busy_by_place: dict[tuple[int, int, int, int], list] = defaultdict(list)
    for (c, s, t, d, p), b in variables.busy.items():
        busy_by_place[(c, s, d, p)].append(b)
    for (c, s, d, p), pl in variables.place.items():
        model.Add(sum(busy_by_place.get((c, s, d, p), [])) == pl)
