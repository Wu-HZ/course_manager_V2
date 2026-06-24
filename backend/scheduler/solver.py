"""组装联合模型、求解、抽取解。不依赖 Django。"""
from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .domain import ScheduleProblem
from .model import add_min_hard_constraints, build_variables


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


_STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


def build_model(problem: ScheduleProblem):
    """构造模型与变量，挂上第一步的最小硬约束。"""
    model = cp_model.CpModel()
    variables = build_variables(model, problem)
    add_min_hard_constraints(model, problem, variables)
    return model, variables


def solve(problem: ScheduleProblem, time_limit_seconds: int = 60, num_workers: int = 8) -> SolveResult:
    model, variables = build_model(problem)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_workers = num_workers
    status = solver.Solve(model)

    lessons: list[ScheduledLesson] = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        lessons = _extract(problem, variables, solver)

    proto = model.Proto()
    return SolveResult(
        status=_STATUS_NAMES.get(status, "UNKNOWN"),
        solve_time_ms=int(solver.WallTime() * 1000),
        lessons=lessons,
        num_vars=len(proto.variables),
        num_constraints=len(proto.constraints),
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
