"""组装联合模型、求解、抽取解。不依赖 Django。"""
from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .domain import ScheduleProblem
from .model import add_all_hard_constraints, add_objective, build_variables


@dataclass(frozen=True)
class ScheduledLesson:
    """一节排定的课：班 c 的课 s 由师 t 在 (day, period) 上。"""

    class_id: int
    subject_id: int
    teacher_id: int | None
    day: int
    period: int


@dataclass
class SolveResult:
    status: str  # OPTIMAL / FEASIBLE / INFEASIBLE / MODEL_INVALID / UNKNOWN
    solve_time_ms: int
    lessons: list[ScheduledLesson]
    num_vars: int
    num_constraints: int
    objective_value: float | None = None


_STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


def build_model(problem: ScheduleProblem):
    """构造模型与变量，挂上全部硬约束与软约束目标。"""
    model = cp_model.CpModel()
    variables = build_variables(model, problem)
    add_all_hard_constraints(model, problem, variables)
    add_objective(model, problem, variables)
    return model, variables


def solve(
    problem: ScheduleProblem,
    time_limit_seconds: int = 60,
    num_workers: int = 8,
    relative_gap_limit: float = 0.05,
) -> SolveResult:
    model, variables = build_model(problem)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_workers = num_workers
    # 达到相对 gap 容限即停。排课只需"足够好"：闭合最后几个百分点的最优性证明
    # 往往耗掉绝大部分时间却无实际收益（实测 30s → 2s，解质量不变）。time_limit
    # 仍作硬上限。注意 CP-SAT 的界质量依赖 worker 数：num_workers≥8 才会启用算紧界
    # 的互补策略，过低（如 4）会导致 gap 收不拢而耗满时限。
    if relative_gap_limit:
        solver.parameters.relative_gap_limit = relative_gap_limit
    status = solver.Solve(model)

    lessons: list[ScheduledLesson] = []
    objective_value: float | None = None
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        lessons = _extract(problem, variables, solver)
        objective_value = solver.ObjectiveValue()

    proto = model.Proto()
    return SolveResult(
        status=_STATUS_NAMES.get(status, "UNKNOWN"),
        solve_time_ms=int(solver.WallTime() * 1000),
        lessons=lessons,
        num_vars=len(proto.variables),
        num_constraints=len(proto.constraints),
        objective_value=objective_value,
    )


def _extract(problem, variables, solver) -> list[ScheduledLesson]:
    """从解里读出 (c, s) 的指派教师，再与 place==1 的片组合成课表。"""
    teacher_of: dict[tuple[int, int], int] = {}
    for (c, s, t), a in variables.assign.items():
        if solver.Value(a) == 1:
            teacher_of[(c, s)] = t

    lessons: list[ScheduledLesson] = []
    for (c, s, d, p), pl in variables.place.items():
        if solver.Value(pl) == 1:
            lessons.append(
                ScheduledLesson(
                    class_id=c, subject_id=s,
                    teacher_id=teacher_of.get((c, s)),
                    day=d, period=p,
                )
            )
    return lessons
