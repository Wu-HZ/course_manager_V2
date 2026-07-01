"""排课领域实体（纯 dataclass，不依赖 Django）。

仅承载求解所需的最小信息，保留 Django 主键 ``id`` 以便落库时映射回 ORM。
唯一与 ORM 耦合的转换在 ``repository.py``；本模块对 Django 一无所知。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .calendar import Calendar, Slot
from .config import SchedulerConfig


@dataclass(frozen=True)
class SubjectInfo:
    """课程。字段对应 ``core.models.Subject``。"""

    id: int
    name: str
    weekly_hours: int
    is_main_subject: bool
    location_type: str
    max_teacher_classes: int  # 单师最多带几个班的该课程
    max_daily_limit: int  # H8 单日上限（第一步未用，先读出备用）
    is_am_preferred: bool  # S1（软约束，第二期）
    allow_consecutive: bool  # S2
    avoid_first_period: bool  # S5


@dataclass(frozen=True)
class TeacherInfo:
    """教师。字段对应 ``core.models.Teacher``。"""

    id: int
    name: str
    day_off: int | None  # H4 禁排日（经 travel_group.day_off 解析而来）
    min_weekly_hours: int | None  # H10 下限（第二期）
    max_weekly_hours: int | None  # H10 上限（第二期）
    blocked_times: tuple[tuple[int, str], ...]  # H13 (day, period_type)，第二期


@dataclass(frozen=True)
class ClassInfo:
    """班级。字段对应 ``core.models.SchoolClass``。"""

    id: int
    name: str
    grade: int
    homeroom_teacher_id: int | None


@dataclass(frozen=True)
class CourseDemand:
    """一个 ``active(c, s)``：班 ``class_id`` 需开课 ``subject_id``。

    ``locked_count`` 是被用户锁定（``ScheduleLock``）钉死的课时数；真正需要排进
    时间表的节数是 :attr:`hours_to_place`。
    """

    class_id: int
    subject_id: int
    weekly_hours: int
    locked_count: int

    @property
    def hours_to_place(self) -> int:
        return self.weekly_hours - self.locked_count


@dataclass(frozen=True)
class LockedEntry:
    """预锁定课表条目（班会 / 校本 / 用户锁定），落库时写为 ``is_locked=True``。

    与 :class:`CourseDemand` 不同：这些是**已经定死**了时间片（甚至教师）的课，
    不进求解，只作为 place 的不可用片，并在落库时原样写回。
    """

    class_id: int
    subject_id: int
    teacher_id: int | None
    day: int
    period: int


@dataclass(frozen=True)
class ScheduleProblem:
    """一次排课的完整输入（联合模型的「事实」）。由 repository 装配，model 消费。"""

    calendar: Calendar
    classes: dict[int, ClassInfo]
    subjects: dict[int, SubjectInfo]
    teachers: dict[int, TeacherInfo]
    demands: tuple[CourseDemand, ...]  # 所有 active(c, s)
    qualified_teachers: dict[int, frozenset[int]]  # subject_id -> {teacher_id}（资质）
    forced_assignments: dict[tuple[int, int], int]  # (class_id, subject_id) -> teacher_id（手动派课）
    locks_by_class: dict[int, frozenset[Slot]]  # class_id -> 该班用户锁定占用片
    config: SchedulerConfig  # H11/H14/H15 参数 + S1-S7 权重
    location_capacity: dict[str, int] = field(default_factory=dict)  # 场地类型 -> 容量
    teacher_locked_hours: dict[int, int] = field(default_factory=dict)  # 教师被用户锁定占用的节数
    teacher_locked_slots: dict[int, frozenset[Slot]] = field(default_factory=dict)  # 教师被用户锁定占用的具体时间片
    locked_entries: tuple["LockedEntry", ...] = ()  # 班会/校本/用户锁定预锁条目（落库用）

    def qual(self, subject_id: int) -> frozenset[int]:
        return self.qualified_teachers.get(subject_id, frozenset())

    def candidate_teachers(self, class_id: int, subject_id: int) -> frozenset[int]:
        """(c, s) 的可派教师：有手动派课则锁定为该教师，否则为全部合格教师。"""
        forced = self.forced_assignments.get((class_id, subject_id))
        if forced is not None:
            return frozenset({forced})
        return self.qual(subject_id)

    def legal_slots(self, class_id: int) -> list[Slot]:
        """班 ``class_id`` 的普通课可用片 = 全周 − 班会/校本预占 − 本班用户锁定。"""
        reserved = self.locks_by_class.get(class_id, frozenset())
        return [
            (d, p)
            for (d, p) in self.calendar.all_slots()
            if not self.calendar.is_reserved(d, p) and (d, p) not in reserved
        ]
