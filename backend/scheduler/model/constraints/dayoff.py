"""H4 禁排日。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..variables import Variables
    from ...domain import ScheduleProblem


def add_day_off_constraints(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """教师在其 ``day_off``（经 travel_group 解析）当天不排课。

    做法：把该教师当天的所有 busy 置 0。由联结约束 ``sum_t busy == place`` 自动传导——
    若某片所有合格教师都禁排该天，则该片 place 必为 0；若仅部分禁排，则该片只能由
    未禁排的教师承担。
    """
    for (c, s, t, d, p), b in variables.busy.items():
        day_off = problem.teachers[t].day_off
        if day_off is not None and d == day_off:
            model.Add(b == 0)
