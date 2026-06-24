"""时间结构（参数化，纯 Python，不依赖 Django）。

对应旧 ``scheduler/time_slots.py`` 里写死的常量。第一期保留与旧引擎完全相同的
默认取值（周一~周四 6 节、周五 4 节、上午 4 节、周五第 4 节班会、校本占周二/周四
下午），但全部收敛为一个可注入的 :class:`Calendar` 值对象，消除散落各处的写死量。
"""
from __future__ import annotations

from dataclasses import dataclass

# (day, period)，day 0~4 对应周一~周五，period 自 0 起。
Slot = tuple[int, int]


@dataclass(frozen=True)
class Calendar:
    """一周的时间骨架。所有约束/变量的时间维度都从这里取，不再读全局常量。"""

    periods_per_day: tuple[int, ...]  # 每天节数，下标即 day，如 (6, 6, 6, 6, 4)
    am_periods: int  # 上午节数：period < am_periods 即上午
    class_meeting_slot: Slot | None  # 班会固定占用片（旧：周五第 4 节），None 表示无
    combined_slots: frozenset[Slot]  # 校本/合班课固定占用片（旧：周二/周四下午）
    consecutive_forbidden_pairs: tuple[tuple[int, int], ...]  # 连堂禁止跨越的相邻 period 对

    @property
    def days(self) -> tuple[int, ...]:
        return tuple(range(len(self.periods_per_day)))

    def all_slots(self) -> list[Slot]:
        """全周所有合法时间片（按 day、period 升序）。"""
        return [(d, p) for d in self.days for p in range(self.periods_per_day[d])]

    def total_slots(self) -> int:
        return sum(self.periods_per_day)

    def is_am(self, day: int, period: int) -> bool:
        return period < self.am_periods

    def is_reserved(self, day: int, period: int) -> bool:
        """该片是否被班会/校本全局预占——普通课不可排在此。

        注意这是「对所有班级一致」的预占；某个班自己的用户锁定片不在这里，
        而是放在 :attr:`ScheduleProblem.locks_by_class`。
        """
        if self.class_meeting_slot is not None and (day, period) == self.class_meeting_slot:
            return True
        return (day, period) in self.combined_slots
