"""排课编排：load → build → solve →（无解则）diagnose。

第二步：全硬约束 + 软约束目标 + 无解时 unsat core 诊断。仍不落库（待 persistence.py）。
替代旧 ``engine.run()`` 的角色。
"""
from __future__ import annotations

from .repository import load_problem
from .solver import SolveResult, solve


def run(time_limit_seconds: int = 60, num_workers: int = 8) -> dict:
    """跑完整联合模型。

    返回 dict：
    - ``ok``：静态预检是否通过（False 时 ``errors`` 非空，未求解）
    - ``errors``：求解前即可判定的静态死结（如某课无合格教师）
    - ``problem``：领域问题
    - ``result``：:class:`SolveResult`，预检失败时为 None
    - ``conflicts``：INFEASIBLE 时的最小冲突集（中文），否则空列表
    """
    problem, errors = load_problem()
    if errors:
        return {"ok": False, "errors": errors, "problem": problem, "result": None, "conflicts": []}

    result: SolveResult = solve(
        problem, time_limit_seconds=time_limit_seconds, num_workers=num_workers
    )

    conflicts: list[str] = []
    if result.status == "INFEASIBLE":
        from .diagnostics import diagnose

        conflicts = diagnose(
            problem, time_limit_seconds=min(time_limit_seconds, 30), num_workers=num_workers
        )

    return {"ok": True, "errors": [], "problem": problem, "result": result, "conflicts": conflicts}
