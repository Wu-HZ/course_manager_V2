"""联合模型的决策变量：assign / place / busy。

这是旧引擎缺失的核心——旧模型只有 place（教师维度被 ``auto_assign`` 提前定死），
新模型把派课也变成变量 ``assign``，并用联结变量 ``busy = assign ∧ place`` 把两者
绑在同一个 CP-SAT 模型里联合求解。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ortools.sat.python import cp_model

    from ..domain import ScheduleProblem


@dataclass
class Variables:
    """三族布尔变量的容器。键一律用 Django 主键，便于回落库。"""

    # (class_id, subject_id, teacher_id) -> 该课由该师上
    assign: dict[tuple[int, int, int], "cp_model.IntVar"]
    # (class_id, subject_id, day, period) -> 该课占该时间片
    place: dict[tuple[int, int, int, int], "cp_model.IntVar"]
    # (class_id, subject_id, teacher_id, day, period) -> assign ∧ place
    busy: dict[tuple[int, int, int, int, int], "cp_model.IntVar"]


def build_variables(model, problem: "ScheduleProblem") -> Variables:
    """按资质与合法时间片裁剪后创建 assign / place / busy。

    - ``assign`` 仅对 ``candidate_teachers(c, s)`` 创建（手动派课则锁定为该师）。
    - ``place`` 仅对该班合法片创建（已排除班会/校本/用户锁定片）。
    - ``busy`` 对每个 (candidate t, 合法片) 创建，并用三条线性约束实现
      ``busy == assign ∧ place``（AND 的标准线性化，等价于 reification 但更轻）。
    """
    assign: dict[tuple[int, int, int], "cp_model.IntVar"] = {}
    place: dict[tuple[int, int, int, int], "cp_model.IntVar"] = {}
    busy: dict[tuple[int, int, int, int, int], "cp_model.IntVar"] = {}

    for demand in problem.demands:
        c, s = demand.class_id, demand.subject_id
        candidates = problem.candidate_teachers(c, s)
        slots = problem.legal_slots(c)

        for t in candidates:
            assign[(c, s, t)] = model.NewBoolVar(f"assign_c{c}_s{s}_t{t}")
        for d, p in slots:
            place[(c, s, d, p)] = model.NewBoolVar(f"place_c{c}_s{s}_d{d}_p{p}")
        for t in candidates:
            a = assign[(c, s, t)]
            for d, p in slots:
                b = model.NewBoolVar(f"busy_c{c}_s{s}_t{t}_d{d}_p{p}")
                busy[(c, s, t, d, p)] = b
                pl = place[(c, s, d, p)]
                # busy == assign AND place
                model.Add(b <= a)
                model.Add(b <= pl)
                model.Add(b >= a + pl - 1)

    return Variables(assign=assign, place=place, busy=busy)
