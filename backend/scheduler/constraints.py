"""
约束定义函数
分为硬约束 (必须满足) 和软约束 (优化目标)
"""
from ortools.sat.python import cp_model
from .time_slots import (
    PERIODS_PER_DAY, AM_PERIODS, is_am_slot,
    is_combined_class_slot, is_friday_class_meeting, get_all_slots,
    CONSECUTIVE_FORBIDDEN_PAIRS
)


def add_weekly_hours_constraint(model, schedule_vars, class_subjects, subjects_dict, lock_counts=None):
    """
    H1: 周课时约束
    每班每课的时间片总数 = weekly_hours - 已锁定数量
    lock_counts: {(class_id, subject_id): locked_count}
    """
    if lock_counts is None:
        lock_counts = {}
    for (class_id, subject_id), slots in schedule_vars.items():
        weekly_hours = subjects_dict[subject_id].weekly_hours
        locked = lock_counts.get((class_id, subject_id), 0)
        remaining = weekly_hours - locked
        if remaining > 0:
            model.Add(sum(slots.values()) == remaining)
        elif remaining == 0:
            # 所有课时都已锁定，强制所有变量为0
            for var in slots.values():
                model.Add(var == 0)


def add_class_exclusion_constraint(model, schedule_vars, all_classes, all_subjects):
    """
    H2: 班级互斥约束
    同一班级同一时间只上一门课
    """
    for class_id in all_classes:
        for day, period in get_all_slots():
            slot_vars = []
            for subject_id in all_subjects:
                key = (class_id, subject_id)
                if key in schedule_vars and (day, period) in schedule_vars[key]:
                    slot_vars.append(schedule_vars[key][(day, period)])
            if slot_vars:
                model.Add(sum(slot_vars) <= 1)


def add_teacher_exclusion_constraint(model, schedule_vars, teacher_assignments):
    """
    H3: 教师互斥约束
    同一教师同一时间只教一个班
    teacher_assignments: {teacher_id: [(class_id, subject_id), ...]}
    """
    for teacher_id, assignments in teacher_assignments.items():
        for day, period in get_all_slots():
            slot_vars = []
            for class_id, subject_id in assignments:
                key = (class_id, subject_id)
                if key in schedule_vars and (day, period) in schedule_vars[key]:
                    slot_vars.append(schedule_vars[key][(day, period)])
            if slot_vars:
                model.Add(sum(slot_vars) <= 1)


def add_day_off_constraint(model, schedule_vars, teacher_day_off, teacher_assignments):
    """
    H4: 禁排日约束
    教师在 day_off 当天不排课
    teacher_day_off: {teacher_id: day_off}
    """
    for teacher_id, day_off in teacher_day_off.items():
        if day_off is None:
            continue
        assignments = teacher_assignments.get(teacher_id, [])
        for class_id, subject_id in assignments:
            key = (class_id, subject_id)
            if key not in schedule_vars:
                continue
            for period in range(PERIODS_PER_DAY.get(day_off, 0)):
                if (day_off, period) in schedule_vars[key]:
                    model.Add(schedule_vars[key][(day_off, period)] == 0)


def add_location_capacity_constraint(model, schedule_vars, subjects_dict, location_capacities):
    """
    H5: 场地容量约束
    同时间使用同类场地的课 <= capacity
    location_capacities: {'PLAYGROUND': 2, 'HOME_EC': 1, ...}
    """
    # 按场地类型分组
    location_subjects = {}
    for subject_id, subject in subjects_dict.items():
        loc_type = subject.location_type
        if loc_type not in ['NORMAL']:  # 普通教室不限制
            if loc_type not in location_subjects:
                location_subjects[loc_type] = []
            location_subjects[loc_type].append(subject_id)

    for loc_type, subject_ids in location_subjects.items():
        capacity = location_capacities.get(loc_type, 1)
        for day, period in get_all_slots():
            slot_vars = []
            for (class_id, subject_id), slots in schedule_vars.items():
                if subject_id in subject_ids and (day, period) in slots:
                    slot_vars.append(slots[(day, period)])
            if slot_vars:
                model.Add(sum(slot_vars) <= capacity)


def add_max_daily_limit_constraint(model, schedule_vars, subjects_dict):
    """
    H8: 单日上限约束
    同课同班一天不超过 max_daily_limit
    """
    for (class_id, subject_id), slots in schedule_vars.items():
        max_daily = subjects_dict[subject_id].max_daily_limit
        for day in range(5):
            day_slots = [
                var for (d, p), var in slots.items() if d == day
            ]
            if day_slots:
                model.Add(sum(day_slots) <= max_daily)


def add_consecutive_forbidden_constraint(model, schedule_vars, subjects_dict, forbidden_pairs=None):
    """
    H9: 连堂课禁止跨越指定节次对
    第2节和第3节之间有课间操，连堂课不能横跨这两节
    forbidden_pairs: 禁止跨越的节次对列表，如 [(1,2)]，默认使用 CONSECUTIVE_FORBIDDEN_PAIRS
    """
    if forbidden_pairs is None:
        forbidden_pairs = CONSECUTIVE_FORBIDDEN_PAIRS
    for (class_id, subject_id), slots in schedule_vars.items():
        if not subjects_dict[subject_id].allow_consecutive:
            continue
        for day in range(5):
            for p1, p2 in forbidden_pairs:
                if (day, p1) in slots and (day, p2) in slots:
                    # 禁止两节同时被选中
                    model.Add(slots[(day, p1)] + slots[(day, p2)] <= 1)


def add_teacher_max_hours_constraint(model, schedule_vars, teacher_assignments, teachers_dict, teacher_lock_counts=None):
    """
    H10: 教师周课时约束
    - 教师的总课时不超过 max_weekly_hours（如果设置了的话）
    - 教师的总课时不少于 min_weekly_hours（如果设置了的话）
    teacher_assignments: {teacher_id: [(class_id, subject_id), ...]}
    teachers_dict: {teacher_id: Teacher object}
    teacher_lock_counts: {teacher_id: locked_hours} 每个教师已锁定的课时数
    """
    if teacher_lock_counts is None:
        teacher_lock_counts = {}

    for teacher_id, assignments in teacher_assignments.items():
        teacher = teachers_dict.get(teacher_id)
        if not teacher:
            continue

        # 收集该教师所有课程的变量
        all_vars = []
        for class_id, subject_id in assignments:
            key = (class_id, subject_id)
            if key in schedule_vars:
                all_vars.extend(schedule_vars[key].values())

        # 该教师已锁定的课时数
        locked_hours = teacher_lock_counts.get(teacher_id, 0)

        # 上限约束：变量总和 + 已锁定 <= 上限
        if teacher.max_weekly_hours is not None:
            remaining = teacher.max_weekly_hours - locked_hours
            if all_vars:
                model.Add(sum(all_vars) <= remaining)

        # 下限约束：变量总和 + 已锁定 >= 下限
        if teacher.min_weekly_hours is not None:
            remaining = teacher.min_weekly_hours - locked_hours
            if remaining > 0 and all_vars:
                model.Add(sum(all_vars) >= remaining)
            # 如果 remaining <= 0，说明已锁定的课时已满足下限要求


def add_teacher_class_daily_limit_constraint(model, schedule_vars, teacher_assignments, max_per_class=2):
    """
    H11: 教师同班单日上限约束
    同一教师同一天在同一班级不超过 max_per_class 节课
    teacher_assignments: {teacher_id: [(class_id, subject_id), ...]}
    """
    # 按教师+班级分组
    teacher_class_pairs = {}
    for teacher_id, assignments in teacher_assignments.items():
        for class_id, subject_id in assignments:
            key = (teacher_id, class_id)
            if key not in teacher_class_pairs:
                teacher_class_pairs[key] = []
            teacher_class_pairs[key].append(subject_id)

    for (teacher_id, class_id), subject_ids in teacher_class_pairs.items():
        for day in range(5):
            day_vars = []
            for subject_id in subject_ids:
                cs_key = (class_id, subject_id)
                if cs_key in schedule_vars:
                    for (d, p), var in schedule_vars[cs_key].items():
                        if d == day:
                            day_vars.append(var)
            if len(day_vars) > max_per_class:
                model.Add(sum(day_vars) <= max_per_class)


def add_am_preference_objective(model, schedule_vars, subjects_dict, weight=10):
    """
    S1: 上午优先软约束
    AM优先的课程尽量排在上午
    返回目标表达式列表
    """
    objectives = []
    for (class_id, subject_id), slots in schedule_vars.items():
        if subjects_dict[subject_id].is_am_preferred:
            for (day, period), var in slots.items():
                if is_am_slot(day, period):
                    objectives.append(var * weight)
    return objectives


def add_consecutive_preference_objective(model, schedule_vars, subjects_dict, weight=5):
    """
    S2: 连堂课连续软约束
    允许连堂的课程奖励相邻时间片（跳过禁止跨越的节次对）
    """
    forbidden = set(CONSECUTIVE_FORBIDDEN_PAIRS)
    objectives = []
    for (class_id, subject_id), slots in schedule_vars.items():
        if not subjects_dict[subject_id].allow_consecutive:
            continue
        for day in range(5):
            periods = PERIODS_PER_DAY[day]
            for p in range(periods - 1):
                if (p, p + 1) in forbidden:
                    continue  # 跳过禁止连堂的节次对
                if (day, p) in slots and (day, p + 1) in slots:
                    # 创建一个辅助变量表示两节都被选中
                    both = model.NewBoolVar(f'consec_{class_id}_{subject_id}_{day}_{p}')
                    model.AddBoolAnd([slots[(day, p)], slots[(day, p + 1)]]).OnlyEnforceIf(both)
                    model.AddBoolOr([
                        slots[(day, p)].Not(),
                        slots[(day, p + 1)].Not()
                    ]).OnlyEnforceIf(both.Not())
                    objectives.append(both * weight)
    return objectives


def add_distribution_penalty(model, schedule_vars, subjects_dict, weight=2):
    """
    S3: 课程均匀分布软约束
    惩罚同一天排过多同一课程 (超过1节的部分)
    """
    penalties = []
    for (class_id, subject_id), slots in schedule_vars.items():
        for day in range(5):
            day_slots = [var for (d, p), var in slots.items() if d == day]
            if len(day_slots) > 1:
                # 惩罚超过1节的情况
                excess = model.NewIntVar(0, len(day_slots), f'excess_{class_id}_{subject_id}_{day}')
                model.Add(excess >= sum(day_slots) - 1)
                penalties.append(excess * weight)
    return penalties


def add_teacher_daily_load_penalty(model, schedule_vars, teacher_assignments, threshold=3, weight=8):
    """
    S4: 教师单日课时均衡软约束
    惩罚教师单日课时超过 threshold 的部分
    """
    penalties = []
    for teacher_id, assignments in teacher_assignments.items():
        for day in range(5):
            day_vars = []
            for class_id, subject_id in assignments:
                key = (class_id, subject_id)
                if key in schedule_vars:
                    for (d, p), var in schedule_vars[key].items():
                        if d == day:
                            day_vars.append(var)
            if len(day_vars) > threshold:
                excess = model.NewIntVar(0, len(day_vars), f'tload_{teacher_id}_{day}')
                model.Add(excess >= sum(day_vars) - threshold)
                penalties.append(excess * weight)
    return penalties


def add_avoid_first_period_penalty(model, schedule_vars, subjects_dict, weight=6):
    """
    S5: 避免第一节课软约束
    标记了avoid_first_period的课程尽量不排在每天第0节
    """
    penalties = []
    for (class_id, subject_id), slots in schedule_vars.items():
        if not subjects_dict[subject_id].avoid_first_period:
            continue
        for (day, period), var in slots.items():
            if period == 0:
                penalties.append(var * weight)
    return penalties


def add_teacher_class_switch_penalty(model, schedule_vars, teacher_assignments, weight=5):
    """
    S6: 教师连续换班惩罚
    同一教师连续两节课如果在不同班级上课，给予惩罚
    连续给同一个班上课是OK的
    """
    from .time_slots import PERIODS_PER_DAY

    penalties = []

    for teacher_id, assignments in teacher_assignments.items():
        if len(assignments) < 2:
            continue

        # 按班级分组
        class_to_vars = {}  # class_id -> [(subject_id, day, period, var), ...]
        for class_id, subject_id in assignments:
            key = (class_id, subject_id)
            if key not in schedule_vars:
                continue
            if class_id not in class_to_vars:
                class_to_vars[class_id] = []
            for (day, period), var in schedule_vars[key].items():
                class_to_vars[class_id].append((subject_id, day, period, var))

        # 如果该教师只教一个班，不需要检查
        if len(class_to_vars) < 2:
            continue

        # 对每天的每对连续节次
        for day in range(5):
            periods = PERIODS_PER_DAY.get(day, 0)
            for p in range(periods - 1):
                # 收集该教师在 (day, p) 和 (day, p+1) 的所有变量，按班级分组
                slot1_by_class = {}  # class_id -> [vars]
                slot2_by_class = {}

                for class_id, var_list in class_to_vars.items():
                    for (subj_id, d, period, var) in var_list:
                        if d != day:
                            continue
                        if period == p:
                            if class_id not in slot1_by_class:
                                slot1_by_class[class_id] = []
                            slot1_by_class[class_id].append(var)
                        elif period == p + 1:
                            if class_id not in slot2_by_class:
                                slot2_by_class[class_id] = []
                            slot2_by_class[class_id].append(var)

                # 检查不同班级之间的连续情况
                for class1, vars1 in slot1_by_class.items():
                    for class2, vars2 in slot2_by_class.items():
                        if class1 == class2:
                            continue  # 同班级连续是OK的

                        # 创建辅助变量：class1在p节有课 且 class2在p+1节有课
                        has_class1_at_p = model.NewBoolVar(
                            f'clsswitch_{teacher_id}_{day}_{p}_{class1}_{class2}_c1'
                        )
                        has_class2_at_p1 = model.NewBoolVar(
                            f'clsswitch_{teacher_id}_{day}_{p}_{class1}_{class2}_c2'
                        )

                        # has_class1_at_p = (sum(vars1) >= 1)
                        model.Add(sum(vars1) >= 1).OnlyEnforceIf(has_class1_at_p)
                        model.Add(sum(vars1) == 0).OnlyEnforceIf(has_class1_at_p.Not())

                        # has_class2_at_p1 = (sum(vars2) >= 1)
                        model.Add(sum(vars2) >= 1).OnlyEnforceIf(has_class2_at_p1)
                        model.Add(sum(vars2) == 0).OnlyEnforceIf(has_class2_at_p1.Not())

                        # 两者都为真时惩罚
                        both = model.NewBoolVar(
                            f'clsswitch_{teacher_id}_{day}_{p}_{class1}_{class2}'
                        )
                        model.AddBoolAnd([has_class1_at_p, has_class2_at_p1]).OnlyEnforceIf(both)
                        model.AddBoolOr([has_class1_at_p.Not(), has_class2_at_p1.Not()]).OnlyEnforceIf(both.Not())

                        penalties.append(both * weight)

    return penalties


def add_teacher_same_class_subject_switch_penalty(model, schedule_vars, teacher_assignments, weight=3):
    """
    S7: 教师同班换科惩罚
    同一教师连续两节课如果在同一班级但上不同科目，给予惩罚
    连续给同一个班上同一门课是OK的（如连堂课）
    """
    from .time_slots import PERIODS_PER_DAY

    penalties = []

    for teacher_id, assignments in teacher_assignments.items():
        # 按班级分组该教师的所有课程
        class_subjects = {}  # class_id -> [subject_id, ...]
        for class_id, subject_id in assignments:
            if class_id not in class_subjects:
                class_subjects[class_id] = set()
            class_subjects[class_id].add(subject_id)

        # 只检查该教师在同一班级教多门课的情况
        for class_id, subject_ids in class_subjects.items():
            if len(subject_ids) < 2:
                continue  # 只教一门课，无需检查

            # 收集该班级各科目的变量
            subject_vars = {}  # subject_id -> [(day, period, var), ...]
            for subject_id in subject_ids:
                key = (class_id, subject_id)
                if key not in schedule_vars:
                    continue
                subject_vars[subject_id] = [
                    (day, period, var)
                    for (day, period), var in schedule_vars[key].items()
                ]

            # 对每天的每对连续节次检查
            for day in range(5):
                periods = PERIODS_PER_DAY.get(day, 0)
                for p in range(periods - 1):
                    # 收集每个科目在 p 和 p+1 节的变量
                    slot1_by_subject = {}  # subject_id -> var (该科目在p节的变量)
                    slot2_by_subject = {}  # subject_id -> var (该科目在p+1节的变量)

                    for subject_id, var_list in subject_vars.items():
                        for (d, period, var) in var_list:
                            if d != day:
                                continue
                            if period == p:
                                slot1_by_subject[subject_id] = var
                            elif period == p + 1:
                                slot2_by_subject[subject_id] = var

                    # 检查不同科目之间的连续情况
                    for subj1, var1 in slot1_by_subject.items():
                        for subj2, var2 in slot2_by_subject.items():
                            if subj1 == subj2:
                                continue  # 同科目连续是OK的（连堂课）

                            # 两个不同科目在连续节次都有课，给予惩罚
                            both = model.NewBoolVar(
                                f'subjswitch_{teacher_id}_{class_id}_{day}_{p}_{subj1}_{subj2}'
                            )
                            model.AddBoolAnd([var1, var2]).OnlyEnforceIf(both)
                            model.AddBoolOr([var1.Not(), var2.Not()]).OnlyEnforceIf(both.Not())

                            penalties.append(both * weight)

    return penalties


def add_combined_class_teacher_constraint(model, schedule_vars, teacher_assignments, teachers_dict, combined_slots):
    """
    H12: 校本课程教师占用约束
    有分组的教师在校本课程时段不能被安排其他课程
    combined_slots: [(day, period), ...] 校本课程的时段
    teachers_dict: {teacher_id: Teacher object}
    """
    for teacher_id, assignments in teacher_assignments.items():
        teacher = teachers_dict.get(teacher_id)
        if not teacher:
            continue

        # 检查该教师是否有分组且未排除
        if not teacher.combined_class_group_id or teacher.exclude_from_combined:
            continue

        # 该教师在校本课程时段不能有其他课
        for class_id, subject_id in assignments:
            key = (class_id, subject_id)
            if key not in schedule_vars:
                continue
            for day, period in combined_slots:
                if (day, period) in schedule_vars[key]:
                    model.Add(schedule_vars[key][(day, period)] == 0)
