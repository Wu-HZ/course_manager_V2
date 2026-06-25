"""排课领域层：纯数据结构，不依赖 Django 或 ortools。"""
from .calendar import Calendar, Slot
from .config import SchedulerConfig
from .entities import (
    ClassInfo,
    CourseDemand,
    LockedEntry,
    ScheduleProblem,
    SubjectInfo,
    TeacherInfo,
)

__all__ = [
    "Calendar",
    "Slot",
    "SchedulerConfig",
    "ClassInfo",
    "CourseDemand",
    "LockedEntry",
    "ScheduleProblem",
    "SubjectInfo",
    "TeacherInfo",
]
