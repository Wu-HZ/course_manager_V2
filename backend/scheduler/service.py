"""排课编排：load → build → solve →（无解则）diagnose。

第二步：全硬约束 + 软约束目标 + 无解时 unsat core 诊断。仍不落库（待 persistence.py）。
替代旧 ``engine.run()`` 的角色。
"""
from __future__ import annotations

from .repository import load_problem
from .solver import SolveResult, solve


def run(
    time_limit_seconds: int = 60,
    num_workers: int = 8,
    save: bool = False,
    result_name: str = "",
) -> dict:
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
        return {"ok": False, "errors": errors, "problem": problem, "result": None, "conflicts": [], "saved": None}

    result: SolveResult = solve(
        problem, time_limit_seconds=time_limit_seconds, num_workers=num_workers
    )

    conflicts: list[str] = []
    if result.status in ("INFEASIBLE", "UNKNOWN"):
        from .diagnostics import diagnose, diagnose_shortfall

        # 短缺诊断对 UNKNOWN(满载难证的无解)也有效，优先用它告诉用户"哪几节排不下"。
        # 短缺诊断须跑到最优才能报准"最少缺几节"，给独立的充足时限(不跟随主求解的
        # time_limit，否则 time_limit 小时会得到次优解、高估短缺节数)。
        conflicts = diagnose_shortfall(
            problem, time_limit_seconds=40, num_workers=num_workers
        )
        # INFEASIBLE 且短缺诊断没给出内容时，回退到 unsat core(指出冲突的规则)。
        if not conflicts and result.status == "INFEASIBLE":
            conflicts = diagnose(
                problem, time_limit_seconds=min(time_limit_seconds, 30), num_workers=num_workers
            )

    saved = None
    if save and result.status in ("OPTIMAL", "FEASIBLE"):
        from .persistence import persist

        saved = persist(problem, result, name=result_name)

    return {
        "ok": True,
        "errors": [],
        "problem": problem,
        "result": result,
        "conflicts": conflicts,
        "saved": saved,
    }
