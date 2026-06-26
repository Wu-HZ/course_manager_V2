"""无解诊断：用 assumptions 求最小冲突集(unsat core)。

替代旧 ``analyze_infeasibility`` 的约 390 行启发式猜测。思路：
- **结构性约束**(派课基数/联结、H2 班级互斥、H3 教师互斥，以及 H5/H8/H9/H13)
  硬性加入，复现主模型的无解；
- **可调约束**(H1 周课时、H4 禁排日、H10 教师课时上下限、H11、H14、H15、带班数)
  各挂一个 assumption literal；
- 无解时 ``SufficientAssumptionsForInfeasibility()`` 给出最小冲突集，映射成中文——
  这是求解器**证明**的原因，而非猜测。

仅在主模型 INFEASIBLE 时调用。
"""
from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from .domain import ScheduleProblem
from .model import build_variables
from .model.constraints import (
    add_assignment_constraints,
    add_blocked_time_constraints,
    add_class_exclusion_constraints,
    add_consecutive_forbidden_constraints,
    add_day_off_constraints,
    add_homeroom_main_subject_constraints,
    add_location_capacity_constraints,
    add_max_daily_limit_constraints,
    add_teacher_class_daily_constraints,
    add_teacher_exclusion_constraints,
    add_teacher_hours_constraints,
    add_teacher_max_classes_constraints,
    add_teacher_max_main_subjects_constraints,
)


def diagnose(problem: ScheduleProblem, time_limit_seconds: int = 30, num_workers: int = 8) -> list[str]:
    """返回导致无解的最小冲突集（中文描述）。空列表表示未能定位到可调约束。"""
    model = cp_model.CpModel()
    variables = build_variables(model, problem)

    # 结构性 / 不挂 gate 的硬约束（复现无解）
    add_assignment_constraints(model, problem, variables)
    add_class_exclusion_constraints(model, problem, variables)
    add_teacher_exclusion_constraints(model, problem, variables)
    add_location_capacity_constraints(model, problem, variables)
    add_max_daily_limit_constraints(model, problem, variables)
    add_consecutive_forbidden_constraints(model, problem, variables)
    add_blocked_time_constraints(model, problem, variables)

    desc: dict[int, str] = {}
    assumptions: list = []

    def gate(label: str):
        lit = model.NewBoolVar(f"assume_{len(assumptions)}")
        desc[lit.Index()] = label
        assumptions.append(lit)
        return lit

    main_ids = {sid for sid, s in problem.subjects.items() if s.is_main_subject}

    # 预聚合 busy
    busy_by_teacher: dict[int, list] = defaultdict(list)
    busy_by_t_dayoff: dict[int, list] = defaultdict(list)
    busy_by_tcd: dict[tuple[int, int, int], list] = defaultdict(list)
    for (c, s, t, d, p), b in variables.busy.items():
        busy_by_teacher[t].append(b)
        busy_by_tcd[(t, c, d)].append(b)
        doff = problem.teachers[t].day_off
        if doff is not None and d == doff:
            busy_by_t_dayoff[t].append(b)

    # H1 周课时（按 班-课）
    place_by_demand: dict[tuple[int, int], list] = defaultdict(list)
    for (c, s, d, p), pl in variables.place.items():
        place_by_demand[(c, s)].append(pl)
    for demand in problem.demands:
        rem = demand.hours_to_place
        if rem <= 0:
            continue
        pls = place_by_demand.get((demand.class_id, demand.subject_id), [])
        cname = problem.classes[demand.class_id].name
        sname = problem.subjects[demand.subject_id].name
        g = gate(f"周课时：{cname} 的「{sname}」需排 {rem} 节")
        model.Add(sum(pls) == rem).OnlyEnforceIf(g)

    # H4 禁排日（按教师）
    for t, blist in busy_by_t_dayoff.items():
        doff = problem.teachers[t].day_off
        g = gate(f"禁排日：{problem.teachers[t].name} 周{doff + 1}不排课")
        for b in blist:
            model.Add(b == 0).OnlyEnforceIf(g)

    # H10 教师周课时上下限（按教师）
    for t, teacher in problem.teachers.items():
        lits = busy_by_teacher.get(t, [])
        locked = problem.teacher_locked_hours.get(t, 0)
        if teacher.max_weekly_hours is not None:
            g = gate(f"教师课时上限：{teacher.name} ≤ {teacher.max_weekly_hours} 节")
            model.Add(sum(lits) <= teacher.max_weekly_hours - locked).OnlyEnforceIf(g)
        if teacher.min_weekly_hours is not None:
            rem = teacher.min_weekly_hours - locked
            if rem > 0 and lits:
                g = gate(f"教师课时下限：{teacher.name} ≥ {teacher.min_weekly_hours} 节")
                model.Add(sum(lits) >= rem).OnlyEnforceIf(g)

    # H11 教师同班单日上限（按教师）
    cap11 = problem.config.h11_teacher_class_daily_max
    gates_h11: dict[int, object] = {}
    for (t, c, d), lits in busy_by_tcd.items():
        if len(lits) <= cap11:
            continue
        if t not in gates_h11:
            gates_h11[t] = gate(
                f"教师同班单日上限：{problem.teachers[t].name} 每班每天 ≤ {cap11} 节"
            )
        model.Add(sum(lits) <= cap11).OnlyEnforceIf(gates_h11[t])

    # H14 班主任主课（按班）
    if problem.config.h14_homeroom_main_subject:
        for c, cls in problem.classes.items():
            t = cls.homeroom_teacher_id
            if t is None:
                continue
            alits = [
                variables.assign[(c, sid, t)]
                for sid in main_ids
                if (c, sid, t) in variables.assign
            ]
            g = gate(f"班主任主课：{cls.name} 班主任须任至少 1 门主课")
            model.Add(sum(alits) >= 1).OnlyEnforceIf(g)

    # assign 索引（H15 / 带班数共用）
    assign_by_st: dict[tuple[int, int], list] = defaultdict(list)
    for (c, s, t), a in variables.assign.items():
        assign_by_st[(s, t)].append(a)

    # H15 单师最多主课数（按教师）
    cap15 = problem.config.h15_teacher_max_main_subjects
    teaches_by_teacher: dict[int, list] = defaultdict(list)
    for (s, t), alits in assign_by_st.items():
        if s not in main_ids:
            continue
        teaches = model.NewBoolVar(f"dbg_teaches_s{s}_t{t}")
        model.AddMaxEquality(teaches, alits)
        teaches_by_teacher[t].append(teaches)
    for t, tlits in teaches_by_teacher.items():
        if len(tlits) <= cap15:
            continue
        g = gate(f"单师主课数：{problem.teachers[t].name} ≤ {cap15} 门主课")
        model.Add(sum(tlits) <= cap15).OnlyEnforceIf(g)

    # 单师带班数（按课程）
    gates_classes: dict[int, object] = {}
    for (s, t), alits in assign_by_st.items():
        cap = problem.subjects[s].max_teacher_classes
        if len(alits) <= cap:
            continue
        if s not in gates_classes:
            gates_classes[s] = gate(
                f"单师带班数：「{problem.subjects[s].name}」每位教师 ≤ {cap} 个班"
            )
        model.Add(sum(alits) <= cap).OnlyEnforceIf(gates_classes[s])

    if not assumptions:
        return []

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = num_workers
    # 每次子集求解给较小预算；最小化要反复求解，无解判定通常很快。
    solver.parameters.max_time_in_seconds = max(3, min(time_limit_seconds, 10))

    def solve_with(lits) -> int:
        model.ClearAssumptions()
        model.AddAssumptions(lits)
        return solver.Solve(model)

    if solve_with(assumptions) != cp_model.INFEASIBLE:
        # 放松可调约束后即可行，或超时；返回空表示未精确定位。
        return []

    # 从求解器给的充分集出发，deletion filter 最小化为不可约冲突集(IIS)：
    # 逐条尝试移除，仍无解则该条非必需、永久删去；只有明确 INFEASIBLE 才移除
    # （UNKNOWN/超时保守保留）。
    core_idx = set(solver.SufficientAssumptionsForInfeasibility())
    minimized = [lit for lit in assumptions if lit.Index() in core_idx]
    i = 0
    while i < len(minimized):
        candidate = minimized[:i] + minimized[i + 1:]
        if candidate and solve_with(candidate) == cp_model.INFEASIBLE:
            minimized = candidate
        else:
            i += 1
    return [desc[lit.Index()] for lit in minimized]


def diagnose_shortfall(problem: ScheduleProblem, time_limit_seconds: int = 40, num_workers: int = 8) -> list[str]:
    """松弛周课时(允许少排)、最小化少排节数，定位排不下的课。

    对"无解但难证"(满载 + 大规模 → 主模型 UNKNOWN)尤其有效：松弛后存在平凡可行
    起点(全不排)，求解器能快速给出最少短缺与分布。短缺为 0 表示原问题其实接近可行、
    只是搜索未在时限内命中。返回面向用户的中文诊断。
    """
    model = cp_model.CpModel()
    variables = build_variables(model, problem)

    # 除 H1 周课时外的全部硬约束
    add_assignment_constraints(model, problem, variables)
    add_class_exclusion_constraints(model, problem, variables)
    add_teacher_exclusion_constraints(model, problem, variables)
    add_day_off_constraints(model, problem, variables)
    add_blocked_time_constraints(model, problem, variables)
    add_max_daily_limit_constraints(model, problem, variables)
    add_consecutive_forbidden_constraints(model, problem, variables)
    add_location_capacity_constraints(model, problem, variables)
    add_teacher_hours_constraints(model, problem, variables)
    add_teacher_class_daily_constraints(model, problem, variables)
    add_homeroom_main_subject_constraints(model, problem, variables)
    add_teacher_max_main_subjects_constraints(model, problem, variables)
    add_teacher_max_classes_constraints(model, problem, variables)

    # H1 松弛：sum place + short == hours，short>=0 为少排节数
    place_by_demand: dict[tuple[int, int], list] = defaultdict(list)
    for (c, s, d, p), pl in variables.place.items():
        place_by_demand[(c, s)].append(pl)
    shorts: dict[tuple[int, int], object] = {}
    for demand in problem.demands:
        hours = demand.hours_to_place
        if hours <= 0:
            continue
        pls = place_by_demand.get((demand.class_id, demand.subject_id), [])
        short = model.NewIntVar(0, hours, f"short_c{demand.class_id}_s{demand.subject_id}")
        model.Add(sum(pls) + short == hours)
        shorts[(demand.class_id, demand.subject_id)] = short

    if not shorts:
        return []

    model.Minimize(sum(shorts.values()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_workers = num_workers
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []

    total = int(round(solver.ObjectiveValue()))
    if total == 0:
        return ["放宽『排满』要求后所有课都能排下，说明问题接近可行、只是求解器未在时限内找到解；可增大求解时限后重试。"]

    msgs = [f"当前规则下共有 {total} 节课排不进去："]
    for (c, sid), short in shorts.items():
        val = solver.Value(short)
        if val > 0:
            msgs.append(f"  · {problem.classes[c].name} / {problem.subjects[sid].name} 少排 {val} 节")
    msgs.append("建议：为相关课程增加合格教师，或放宽教师课时上限 / 单师带班数 / 禁排日等限制。")
    return msgs
