"""排课参数与软约束权重（从 ``SchedulerSettings`` 单例快照而来）。

把分散在 Django settings 里的标量参数收成一个不可变值对象，让 model 层无需碰 ORM。
连堂禁排的节次对放在 :class:`~scheduler.domain.calendar.Calendar`，不在这里。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerConfig:
    # 硬约束参数
    h11_teacher_class_daily_max: int  # 教师同班单日上限
    h14_homeroom_main_subject: bool  # 班主任必须担任主课（开关）
    h15_teacher_max_main_subjects: int  # 单师最多主课门数

    # 软约束权重（S1–S7），语义对齐旧 SchedulerSettings
    s1_am_preference_weight: int
    s2_consecutive_weight: int
    s3_distribution_weight: int
    s4_teacher_daily_threshold: int
    s4_teacher_daily_weight: int
    s5_avoid_first_weight: int
    s6_subject_switch_weight: int  # 换班（连续两节不同班）
    s7_same_class_subject_switch_weight: int  # 同班换科
