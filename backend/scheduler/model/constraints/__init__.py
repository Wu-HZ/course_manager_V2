"""硬约束族。每族一文件，签名统一为 ``add_xxx(model, problem, variables)``。"""
from .assignment import add_assignment_constraints
from .dayoff import add_day_off_constraints
from .exclusion import (
    add_class_exclusion_constraints,
    add_teacher_exclusion_constraints,
)
from .hours import add_weekly_hours_constraints

__all__ = [
    "add_assignment_constraints",
    "add_day_off_constraints",
    "add_class_exclusion_constraints",
    "add_teacher_exclusion_constraints",
    "add_weekly_hours_constraints",
    "add_min_hard_constraints",
]


def add_min_hard_constraints(model, problem, variables) -> None:
    """第一步（§9）的最小硬约束集：派课基数/联结 + H1/H2/H3/H4。

    逐族加入，后续 H5/H8/H9/H10/H11/H14/H15 各自追加文件并在此挂载。
    """
    add_assignment_constraints(model, problem, variables)
    add_weekly_hours_constraints(model, problem, variables)
    add_class_exclusion_constraints(model, problem, variables)
    add_teacher_exclusion_constraints(model, problem, variables)
    add_day_off_constraints(model, problem, variables)
