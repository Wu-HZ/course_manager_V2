"""派课层约束（基于 assign）：H14 班主任主课、H15 单师主课数、单师带班数。

旧引擎把这些塞在贪心 ``auto_assign`` 里；联合模型里它们是 ``assign`` 上的线性约束。
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def _main_subject_ids(problem) -> set:
    return {sid for sid, s in problem.subjects.items() if s.is_main_subject}


def add_homeroom_main_subject_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """H14（开关）：每班班主任至少在本班担任一门主课。

    ∀班 c（班主任 t）: sum_{s∈main} assign[c,s,t] ≥ 1
    """
    if not problem.config.h14_homeroom_main_subject:
        return
    main_ids = _main_subject_ids(problem)
    for c, cls in problem.classes.items():
        t = cls.homeroom_teacher_id
        if t is None:
            continue
        lits = [
            variables.assign[(c, sid, t)]
            for sid in main_ids
            if (c, sid, t) in variables.assign
        ]
        # lits 为空表示班主任在本班无法教任何主课 → 0≥1 无解，交由诊断指出。
        model.Add(sum(lits) >= 1)


def add_teacher_max_main_subjects_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """H15：单个教师最多担任 h15 门不同主课（多班同一主课只算一门）。

    teaches[s,t] = OR_c assign[c,s,t]; ∀t: sum_{s∈main} teaches[s,t] ≤ h15
    """
    cap = problem.config.h15_teacher_max_main_subjects
    main_ids = _main_subject_ids(problem)

    assign_by_st: dict[tuple[int, int], list] = defaultdict(list)
    for (c, s, t), a in variables.assign.items():
        if s in main_ids:
            assign_by_st[(s, t)].append(a)

    teaches_by_teacher: dict[int, list] = defaultdict(list)
    for (s, t), lits in assign_by_st.items():
        teaches = model.NewBoolVar(f"teaches_s{s}_t{t}")
        model.AddMaxEquality(teaches, lits)  # teaches = OR(lits)
        teaches_by_teacher[t].append(teaches)

    for t, lits in teaches_by_teacher.items():
        if len(lits) > cap:
            model.Add(sum(lits) <= cap)


def add_teacher_max_classes_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """单师最多带班数：∀(s,t): sum_c assign[c,s,t] ≤ max_teacher_classes(s)。"""
    assign_by_st: dict[tuple[int, int], list] = defaultdict(list)
    for (c, s, t), a in variables.assign.items():
        assign_by_st[(s, t)].append(a)

    for (s, t), lits in assign_by_st.items():
        cap = problem.subjects[s].max_teacher_classes
        if len(lits) > cap:
            model.Add(sum(lits) <= cap)
