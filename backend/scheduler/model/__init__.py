"""联合 CP-SAT 模型：变量构造、硬约束装配、软约束目标。不依赖 Django。"""
from .constraints import add_all_hard_constraints, add_min_hard_constraints
from .objective import add_objective
from .variables import Variables, build_variables

__all__ = [
    "Variables",
    "build_variables",
    "add_min_hard_constraints",
    "add_all_hard_constraints",
    "add_objective",
]
