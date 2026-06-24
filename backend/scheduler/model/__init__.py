"""联合 CP-SAT 模型：变量构造与硬约束装配。不依赖 Django。"""
from .constraints import add_min_hard_constraints
from .variables import Variables, build_variables

__all__ = ["Variables", "build_variables", "add_min_hard_constraints"]
