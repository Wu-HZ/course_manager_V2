"""第一阶段编排：load → build → solve。

替代旧 ``engine.run()`` 的角色，但第一步只验证可行性，不落库（落库待 persistence.py）。
"""
from __future__ import annotations

from .repository import load_problem
from .solver import SolveResult, solve


def run_first_stage(time_limit_seconds: int = 60, num_workers: int = 8) -> dict:
    """跑通最小硬约束模型。

    返回 dict：
    - ``ok``：静态预检是否通过（False 时 ``errors`` 非空，未求解）
    - ``errors``：求解前即可判定的死结（如某课无合格教师）
    - ``problem``：装配出的领域问题（用于打印规模/自检）
    - ``result``：:class:`SolveResult`，预检失败时为 None
    """
    problem, errors = load_problem()
    if errors:
        return {"ok": False, "errors": errors, "problem": problem, "result": None}

    result: SolveResult = solve(
        problem, time_limit_seconds=time_limit_seconds, num_workers=num_workers
    )
    return {"ok": True, "errors": [], "problem": problem, "result": result}
