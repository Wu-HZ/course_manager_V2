"""硬约束族。每族一文件，签名统一为 ``add_xxx(model, problem, variables)``。"""
from .assignment import add_assignment_constraints
from .blocked_time import add_blocked_time_constraints
from .consecutive import add_consecutive_forbidden_constraints
from .daily_limit import add_max_daily_limit_constraints
from .dayoff import add_day_off_constraints
from .exclusion import (
    add_class_exclusion_constraints,
    add_teacher_exclusion_constraints,
)
from .hours import add_weekly_hours_constraints
from .location import add_location_capacity_constraints
from .main_subject import (
    add_homeroom_main_subject_constraints,
    add_teacher_max_classes_constraints,
    add_teacher_max_main_subjects_constraints,
)
from .teacher_daily import add_teacher_class_daily_constraints
from .teacher_load import add_teacher_hours_constraints

__all__ = [
    "add_assignment_constraints",
    "add_weekly_hours_constraints",
    "add_class_exclusion_constraints",
    "add_teacher_exclusion_constraints",
    "add_day_off_constraints",
    "add_location_capacity_constraints",
    "add_max_daily_limit_constraints",
    "add_consecutive_forbidden_constraints",
    "add_teacher_hours_constraints",
    "add_teacher_class_daily_constraints",
    "add_blocked_time_constraints",
    "add_homeroom_main_subject_constraints",
    "add_teacher_max_main_subjects_constraints",
    "add_teacher_max_classes_constraints",
    "add_min_hard_constraints",
    "add_all_hard_constraints",
]


def add_min_hard_constraints(model, problem, variables) -> None:
    """最小硬约束集：派课基数/联结 + H1/H2/H3/H4。"""
    add_assignment_constraints(model, problem, variables)
    add_weekly_hours_constraints(model, problem, variables)
    add_class_exclusion_constraints(model, problem, variables)
    add_teacher_exclusion_constraints(model, problem, variables)
    add_day_off_constraints(model, problem, variables)


def add_all_hard_constraints(model, problem, variables) -> None:
    """全部硬约束：最小集 + H5/H8/H9/H10/H11/H13/H14/H15/带班数。"""
    add_min_hard_constraints(model, problem, variables)
    add_location_capacity_constraints(model, problem, variables)
    add_max_daily_limit_constraints(model, problem, variables)
    add_consecutive_forbidden_constraints(model, problem, variables)
    add_teacher_hours_constraints(model, problem, variables)
    add_teacher_class_daily_constraints(model, problem, variables)
    add_blocked_time_constraints(model, problem, variables)
    add_homeroom_main_subject_constraints(model, problem, variables)
    add_teacher_max_main_subjects_constraints(model, problem, variables)
    add_teacher_max_classes_constraints(model, problem, variables)
