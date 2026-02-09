"""
OR-Tools CP-SAT 排课引擎
支持自动分配教师
"""
import time
import random
from collections import defaultdict
from ortools.sat.python import cp_model

from core.models import (
    SchoolClass, Subject, Teacher, Location,
    ClassSubjectTeacher, TeacherQualification, ScheduleLock,
    SchedulerSettings
)
from .models import ScheduleResult, ScheduleEntry
from .time_slots import (
    PERIODS_PER_DAY, get_all_slots, DAYS,
    is_friday_class_meeting,
    FRIDAY_CLASS_MEETING, TOTAL_SLOTS
)
from .constraints import (
    add_weekly_hours_constraint,
    add_class_exclusion_constraint,
    add_teacher_exclusion_constraint,
    add_day_off_constraint,
    add_location_capacity_constraint,
    add_max_daily_limit_constraint,
    add_consecutive_forbidden_constraint,
    add_teacher_max_hours_constraint,
    add_teacher_class_daily_limit_constraint,
    add_combined_class_teacher_constraint,
    add_am_preference_objective,
    add_consecutive_preference_objective,
    add_distribution_penalty,
    add_teacher_daily_load_penalty,
    add_avoid_first_period_penalty,
    add_teacher_class_switch_penalty,
    add_teacher_same_class_subject_switch_penalty,
)


class ScheduleEngine:
    """排课引擎主类"""

    def __init__(self):
        self.model = cp_model.CpModel()
        self.schedule_vars = {}  # {(class_id, subject_id): {(day, period): BoolVar}}
        self.teacher_choice_vars = {}  # {(class_id, subject_id): {teacher_id: BoolVar}}
        self.locked_entries = []  # 预锁定条目
        self.errors = []
        self.warnings = []  # 警告信息
        self.diagnostics = []  # 诊断信息
        self.auto_assigned = []  # 自动分配的记录
        self.combined_subject = None  # 校本课程Subject
        self.settings = SchedulerSettings.get_settings()  # 加载排课参数设置

        # 从设置中解析可配置参数
        self.class_meeting_name = self.settings.class_meeting_name
        self.combined_slots = self.settings.get_combined_class_slots_list()
        self.combined_slots_set = set(self.combined_slots)

    def load_data(self):
        """加载所有需要的数据"""
        self.classes = {c.id: c for c in SchoolClass.objects.all()}
        self.subjects = {s.id: s for s in Subject.objects.all()}
        self.teachers = {t.id: t for t in Teacher.objects.select_related('travel_group').all()}
        self.locations = {loc.location_type: loc.capacity for loc in Location.objects.all()}

        # 教师资质: {subject_id: [teacher_id, ...]}
        self.qualifications = defaultdict(list)
        for q in TeacherQualification.objects.all():
            self.qualifications[q.subject_id].append(q.teacher_id)

        # 手动指定的班级-课程-教师分配
        self.manual_assignments = {}  # {(class_id, subject_id): teacher_id}
        for cst in ClassSubjectTeacher.objects.filter(is_manual=True):
            self.manual_assignments[(cst.school_class_id, cst.subject_id)] = cst.teacher_id

        # 最终的班级-课程-教师分配 (手动 + 自动)
        self.class_subject_teacher = {}
        self.teacher_assignments = defaultdict(list)

        # 教师禁排日
        self.teacher_day_off = {}
        for teacher_id, teacher in self.teachers.items():
            if teacher.travel_group:
                self.teacher_day_off[teacher_id] = teacher.travel_group.day_off

        # 找到校本课程
        self.combined_subject = None
        for s in self.subjects.values():
            if s.is_combined_class:
                self.combined_subject = s
                break

        # 用户课表锁定: {(class_id, day, period): {subject_id, teacher_id}}
        self.user_locks = {}
        # 锁定计数: {(class_id, subject_id): count}
        self.user_lock_counts = defaultdict(int)
        # 教师锁定计数: {teacher_id: count}
        self.teacher_lock_counts = defaultdict(int)
        for lock in ScheduleLock.objects.select_related('teacher').all():
            self.user_locks[(lock.school_class_id, lock.day, lock.period)] = {
                'subject_id': lock.subject_id,
                'teacher_id': lock.teacher_id,
            }
            self.user_lock_counts[(lock.school_class_id, lock.subject_id)] += 1
            if lock.teacher_id:
                self.teacher_lock_counts[lock.teacher_id] += 1

    def auto_assign_teachers(self):
        """自动分配教师到班级-课程 (跳过班会和校本课程)"""
        # 需要分配的: 所有班级 × 所有非班会课程, 排除已手动指定的
        class_meeting_id = None
        for s in self.subjects.values():
            if s.name == self.class_meeting_name:
                class_meeting_id = s.id
                break

        needs_assignment = []
        for class_id in self.classes:
            school_class = self.classes[class_id]
            for subject_id, subject in self.subjects.items():
                if subject_id == class_meeting_id:
                    continue  # 班会由班主任自动处理
                if subject.is_combined_class:
                    continue  # 校本课程时段固定锁定，不指定教师
                if not subject.is_applicable_for_grade(school_class.grade):
                    continue  # 该课程不适用于此年级
                key = (class_id, subject_id)
                if key in self.manual_assignments:
                    # 已手动指定
                    self.class_subject_teacher[key] = self.manual_assignments[key]
                else:
                    # 需要自动分配
                    needs_assignment.append(key)

        # 检查是否有资质覆盖
        for class_id, subject_id in needs_assignment:
            qualified = self.qualifications.get(subject_id, [])
            if not qualified:
                subject_name = self.subjects[subject_id].name
                self.errors.append(f"课程 '{subject_name}' 没有设置可授课教师资质")

        if self.errors:
            return False

        # 贪心分配: 优先满足有下限要求的教师，然后选负载最小的
        # 打乱分配顺序以增加多样性
        teacher_load = defaultdict(int)  # 统计每个教师被分配的课时数
        teacher_subject_count = defaultdict(lambda: defaultdict(int))  # teacher_id -> subject_id -> 已分配班数
        teacher_main_subjects = defaultdict(set)  # teacher_id -> {subject_ids} (已分配的主课集合)
        teacher_class_subjects = defaultdict(lambda: defaultdict(set))  # teacher_id -> class_id -> {subject_ids}

        # 先把手动分配的课时和主课记录计入
        # 注意：锁定的课时是手动分配课程的一部分，不需要单独计算
        for (class_id, subject_id), teacher_id in self.class_subject_teacher.items():
            subject = self.subjects[subject_id]
            teacher_load[teacher_id] += subject.weekly_hours
            teacher_subject_count[teacher_id][subject_id] += 1
            teacher_class_subjects[teacher_id][class_id].add(subject_id)
            if subject.is_main_subject:
                teacher_main_subjects[teacher_id].add(subject_id)

        # 校验手动分配：同一教师不应有两门不同主课
        for teacher_id, main_subs in teacher_main_subjects.items():
            if len(main_subs) > 1:
                teacher_name = self.teachers[teacher_id].name
                sub_names = [self.subjects[sid].name for sid in main_subs]
                self.warnings.append(
                    f"教师 '{teacher_name}' 手动分配了多门主课: {', '.join(sub_names)}"
                )

        # === 优先处理班主任的主课分配 ===
        # 收集需要分配主课的班主任
        homeroom_needs_main = []  # [(class_id, teacher_id)]
        for class_id, school_class in self.classes.items():
            hr_teacher_id = school_class.homeroom_teacher_id
            if not hr_teacher_id:
                continue
            # 检查该班主任是否已在该班有主课分配
            has_main = False
            for sid in teacher_class_subjects[hr_teacher_id][class_id]:
                if sid in self.subjects and self.subjects[sid].is_main_subject:
                    has_main = True
                    break
            if not has_main:
                homeroom_needs_main.append((class_id, hr_teacher_id))

        # 优先为班主任分配主课
        for class_id, hr_teacher_id in homeroom_needs_main:
            # 找到该班需要分配的主课
            available_main_subjects = []
            for (c_id, s_id) in needs_assignment:
                if c_id != class_id:
                    continue
                subject = self.subjects[s_id]
                if not subject.is_main_subject:
                    continue
                # 检查班主任是否有该课的资质
                if hr_teacher_id not in self.qualifications.get(s_id, []):
                    continue
                # 检查是否已有其他主课分配给该教师
                if teacher_main_subjects[hr_teacher_id]:
                    continue
                # 检查课时上限
                teacher = self.teachers[hr_teacher_id]
                new_load = teacher_load[hr_teacher_id] + subject.weekly_hours
                if teacher.max_weekly_hours is not None and new_load > teacher.max_weekly_hours:
                    continue
                # 检查单科多班限制
                if teacher_subject_count[hr_teacher_id][s_id] >= subject.max_teacher_classes:
                    continue
                available_main_subjects.append(s_id)

            if available_main_subjects:
                # 随机选一门主课分配给班主任
                chosen_subject_id = random.choice(available_main_subjects)
                subject = self.subjects[chosen_subject_id]
                key = (class_id, chosen_subject_id)

                self.class_subject_teacher[key] = hr_teacher_id
                teacher_load[hr_teacher_id] += subject.weekly_hours
                teacher_subject_count[hr_teacher_id][chosen_subject_id] += 1
                teacher_class_subjects[hr_teacher_id][class_id].add(chosen_subject_id)
                teacher_main_subjects[hr_teacher_id].add(chosen_subject_id)
                self.auto_assigned.append({
                    'class_id': class_id,
                    'subject_id': chosen_subject_id,
                    'teacher_id': hr_teacher_id
                })
                # 从待分配列表移除
                needs_assignment.remove(key)

        random.shuffle(needs_assignment)

        for class_id, subject_id in needs_assignment:
            qualified = self.qualifications.get(subject_id, [])
            subject = self.subjects[subject_id]

            # 分三类候选教师:
            # 1. 有下限要求且还未达标的教师 (优先分配)
            # 2. 普通教师且不会造成同班多科 (次优先)
            # 3. 普通教师但会造成同班多科 (最后考虑)
            min_hours_candidates = []  # [(teacher_id, current_load, remaining_to_min, has_other_subject_in_class)]
            normal_candidates = []  # [(teacher_id, current_load, has_other_subject_in_class)]

            for teacher_id in qualified:
                teacher = self.teachers[teacher_id]
                current_load = teacher_load[teacher_id]
                new_load = current_load + subject.weekly_hours

                # 检查是否会超过课时上限
                if teacher.max_weekly_hours is not None:
                    if new_load > teacher.max_weekly_hours:
                        continue  # 跳过，分配后会超过上限

                # 主课互斥：该教师已有任何主课分配，不再分配主课
                if subject.is_main_subject and teacher_main_subjects[teacher_id]:
                    continue

                # 单科多班限制：检查该教师教这门课的班数是否已达上限
                if teacher_subject_count[teacher_id][subject_id] >= subject.max_teacher_classes:
                    continue

                # 检查是否已在该班教其他科目
                existing_subjects = teacher_class_subjects[teacher_id][class_id]
                has_other_subject = len(existing_subjects) > 0 and subject_id not in existing_subjects

                # 分类
                if teacher.min_weekly_hours is not None:
                    remaining = teacher.min_weekly_hours - current_load
                    if remaining > 0:
                        # 还未达到下限
                        min_hours_candidates.append((teacher_id, current_load, remaining, has_other_subject))
                    else:
                        # 已达标，按普通教师处理
                        normal_candidates.append((teacher_id, current_load, has_other_subject))
                else:
                    normal_candidates.append((teacher_id, current_load, has_other_subject))

            # 优先选择有下限要求且未达标的教师
            best_teacher = None
            if min_hours_candidates:
                # 先按是否有同班其他科目分组，优先选择没有的
                no_conflict = [c for c in min_hours_candidates if not c[3]]
                has_conflict = [c for c in min_hours_candidates if c[3]]
                candidates_pool = no_conflict if no_conflict else has_conflict

                # 按剩余需求量降序
                candidates_pool.sort(key=lambda x: -x[2])
                top_remaining = candidates_pool[0][2]
                top_group = [c for c in candidates_pool if c[2] == top_remaining]
                best_teacher = random.choice(top_group)[0]
            elif normal_candidates:
                # 先按是否有同班其他科目分组
                no_conflict = [c for c in normal_candidates if not c[2]]
                has_conflict = [c for c in normal_candidates if c[2]]
                candidates_pool = no_conflict if no_conflict else has_conflict

                # 从负载最低的一组中随机选择
                candidates_pool.sort(key=lambda x: x[1])
                min_load = candidates_pool[0][1]
                low_group = [c for c in candidates_pool if c[1] == min_load]
                best_teacher = random.choice(low_group)[0]

            if best_teacher:
                key = (class_id, subject_id)
                self.class_subject_teacher[key] = best_teacher
                teacher_load[best_teacher] += subject.weekly_hours
                teacher_subject_count[best_teacher][subject_id] += 1
                teacher_class_subjects[best_teacher][class_id].add(subject_id)
                if subject.is_main_subject:
                    teacher_main_subjects[best_teacher].add(subject_id)
                self.auto_assigned.append({
                    'class_id': class_id,
                    'subject_id': subject_id,
                    'teacher_id': best_teacher
                })
            else:
                # 没有合适的教师
                class_name = self.classes[class_id].name
                subject_name = subject.name
                self.errors.append(
                    f"无法为 {class_name} 的 {subject_name} 分配教师（所有有资质的教师都已达到课时上限或主课冲突）"
                )

        # 构建 teacher_assignments
        for (class_id, subject_id), teacher_id in self.class_subject_teacher.items():
            self.teacher_assignments[teacher_id].append((class_id, subject_id))

        # 检查有下限要求的教师是否达标
        for teacher_id, teacher in self.teachers.items():
            if teacher.min_weekly_hours is not None:
                actual_hours = teacher_load.get(teacher_id, 0)
                if actual_hours < teacher.min_weekly_hours:
                    self.errors.append(
                        f"教师 '{teacher.name}' 要求至少 {teacher.min_weekly_hours} 节课时，"
                        f"但只能分配 {actual_hours} 节（请检查该教师的资质设置或增加可授课程）"
                    )

        # 检查班主任是否在其班级担任主课
        for class_id, school_class in self.classes.items():
            hr_teacher_id = school_class.homeroom_teacher_id
            if not hr_teacher_id:
                continue
            # 检查该班主任是否在该班有主课
            has_main = False
            for (c_id, s_id), t_id in self.class_subject_teacher.items():
                if c_id == class_id and t_id == hr_teacher_id:
                    if self.subjects[s_id].is_main_subject:
                        has_main = True
                        break
            if not has_main:
                teacher_name = self.teachers[hr_teacher_id].name
                self.errors.append(
                    f"班主任 '{teacher_name}' 必须在 {school_class.name} 担任至少一门主课"
                    f"（请为该教师添加主课资质或手动分配）"
                )

        # 检查是否有分配失败
        if self.errors:
            return False

        return True

    def validate_data(self):
        """验证数据完整性"""
        if not self.classes:
            self.errors.append("没有班级数据")
        if not self.subjects:
            self.errors.append("没有课程数据")

        # 检查班主任分配
        class_meeting_subject = None
        for s in self.subjects.values():
            if s.name == self.class_meeting_name:
                class_meeting_subject = s
                break

        if class_meeting_subject:
            for class_id, school_class in self.classes.items():
                if not school_class.homeroom_teacher_id:
                    self.errors.append(f"班级 {school_class.name} 没有指定班主任")

        return len(self.errors) == 0

    def create_variables(self):
        """创建决策变量"""
        all_slots = get_all_slots()

        for (class_id, subject_id) in self.class_subject_teacher.keys():
            subject = self.subjects[subject_id]

            # 跳过班会课 (会预锁定)
            if subject.name == self.class_meeting_name:
                continue

            # 普通课程 (合班课不在 class_subject_teacher 中，已跳过)
            self.schedule_vars[(class_id, subject_id)] = {}
            for day, period in all_slots:
                if is_friday_class_meeting(day, period):
                    continue
                if (day, period) in self.combined_slots_set:
                    continue
                # 跳过用户锁定的时间片
                if (class_id, day, period) in self.user_locks:
                    continue

                var_name = f'c{class_id}_s{subject_id}_d{day}_p{period}'
                self.schedule_vars[(class_id, subject_id)][(day, period)] = \
                    self.model.NewBoolVar(var_name)

    def assign_combined_class_teachers(self):
        """分配校本课程教师到4个分组，并进一步分为周二组和周四组

        规则：
        1. 使用手动指定的教师（Teacher.combined_class_group）
        2. 排除标记为"不参与"的教师（Teacher.exclude_from_combined）
        3. 将未指定的教师随机分配到需要更多人的组
        4. 全局平衡周二和周四的教师人数

        Returns:
            dict: {
                group_id: {
                    "tuesday": [teacher_id, ...],
                    "thursday": [teacher_id, ...]
                }
            }
        """
        if not self.combined_subject:
            return {}

        from core.models import CombinedClassGroup
        import random

        # 获取所有分组
        groups = list(CombinedClassGroup.objects.all().order_by('id'))
        if len(groups) < 4:
            self.errors.append(f"校本课程分组不足: 需要4个, 当前{len(groups)}个")
            return {}

        # 初始化每组的教师列表
        group_teachers = {g.id: [] for g in groups}

        # 1. 处理手动指定的教师
        for tid, teacher in self.teachers.items():
            if teacher.exclude_from_combined:
                continue  # 跳过排除的教师
            if teacher.combined_class_group_id:
                gid = teacher.combined_class_group_id
                if gid in group_teachers:
                    group_teachers[gid].append(tid)

        # 2. 收集未指定且未排除的教师
        unassigned = []
        for tid, teacher in self.teachers.items():
            if teacher.exclude_from_combined:
                continue
            if teacher.combined_class_group_id:
                continue  # 已手动指定
            unassigned.append(tid)

        # 3. 随机分配未指定的教师到需要人的组
        random.shuffle(unassigned)
        for tid in unassigned:
            # 找到教师最少的组
            min_group = min(group_teachers.keys(), key=lambda g: len(group_teachers[g]))
            group_teachers[min_group].append(tid)

        # 4. 检查每组是否至少有一位教师
        for g in groups:
            if not group_teachers[g.id]:
                self.errors.append(f"校本课程分组 '{g.name}' 没有可用教师")

        # 5. 全局分配周二/周四，确保人数平衡
        # 先收集所有教师及其分组和可用日期
        all_teachers_info = []  # [(tid, group_id, can_tuesday, can_thursday)]
        for group_id, teacher_ids in group_teachers.items():
            for tid in teacher_ids:
                day_off = self.teacher_day_off.get(tid)
                can_tuesday = (day_off != 1)
                can_thursday = (day_off != 3)
                all_teachers_info.append((tid, group_id, can_tuesday, can_thursday))

        # 初始化结果
        result = {g.id: {"tuesday": [], "thursday": []} for g in groups}

        # 全局计数
        total_tuesday = 0
        total_thursday = 0

        # 先分配只能去一个日期的教师
        flexible = []
        for tid, group_id, can_tuesday, can_thursday in all_teachers_info:
            if can_tuesday and not can_thursday:
                result[group_id]["tuesday"].append(tid)
                total_tuesday += 1
            elif can_thursday and not can_tuesday:
                result[group_id]["thursday"].append(tid)
                total_thursday += 1
            elif can_tuesday and can_thursday:
                flexible.append((tid, group_id))
            # 两个都不能去的情况不应该发生

        # 随机打乱灵活教师，然后全局平衡分配
        random.shuffle(flexible)
        for tid, group_id in flexible:
            if total_tuesday <= total_thursday:
                result[group_id]["tuesday"].append(tid)
                total_tuesday += 1
            else:
                result[group_id]["thursday"].append(tid)
                total_thursday += 1

        return result

    def generate_rotation_table(self, group_teachers):
        """生成班级轮换表

        此方法保留用于兼容性，返回原始数据。

        Args:
            group_teachers: 分组数据

        Returns:
            dict: 同输入数据
        """
        return group_teachers

    def add_locked_entries(self):
        """添加预锁定条目 (班会课 + 校本课程)"""
        # 1. 班会课锁定
        class_meeting_subject = None
        for s in self.subjects.values():
            if s.name == self.class_meeting_name:
                class_meeting_subject = s
                break

        if class_meeting_subject:
            day, period = FRIDAY_CLASS_MEETING
            for class_id, school_class in self.classes.items():
                if school_class.homeroom_teacher_id:
                    self.locked_entries.append({
                        'school_class_id': class_id,
                        'subject_id': class_meeting_subject.id,
                        'teacher_id': school_class.homeroom_teacher_id,
                        'day': day,
                        'period': period,
                        'is_locked': True,
                    })

        # 2. 校本课程锁定
        # 班级视角：这些时段上"校本课程"（不指定教师）
        # 教师视角：如果在某个分组，这些时段被占用（在约束中处理）
        if self.combined_subject:
            for day, period in self.combined_slots:
                for class_id in self.classes:
                    self.locked_entries.append({
                        'school_class_id': class_id,
                        'subject_id': self.combined_subject.id,
                        'teacher_id': None,  # 不指定教师
                        'day': day,
                        'period': period,
                        'is_locked': True,
                    })

        # 3. 用户课表锁定
        for (class_id, day, period), lock_info in self.user_locks.items():
            subject_id = lock_info['subject_id']
            teacher_id = lock_info['teacher_id']

            # 如果没指定教师，从授课分配中获取
            if teacher_id is None:
                teacher_id = self.class_subject_teacher.get((class_id, subject_id))

            self.locked_entries.append({
                'school_class_id': class_id,
                'subject_id': subject_id,
                'teacher_id': teacher_id,
                'day': day,
                'period': period,
                'is_locked': True,
            })

    def add_constraints(self):
        """添加所有约束"""
        all_class_ids = list(self.classes.keys())
        all_subject_ids = list(self.subjects.keys())

        # H1: 周课时约束 (扣除已锁定的课时)
        add_weekly_hours_constraint(
            self.model, self.schedule_vars,
            self.class_subject_teacher, self.subjects,
            lock_counts=self.user_lock_counts
        )

        # H2: 班级互斥
        add_class_exclusion_constraint(
            self.model, self.schedule_vars,
            all_class_ids, all_subject_ids
        )

        # H3: 教师互斥
        add_teacher_exclusion_constraint(
            self.model, self.schedule_vars,
            self.teacher_assignments
        )

        # H3.5: 用户锁定占用教师时间片
        # 对于每个用户锁定的条目，该教师在该时间片不能再教其他课
        for (class_id, day, period), lock_info in self.user_locks.items():
            locked_teacher_id = lock_info['teacher_id']
            if locked_teacher_id is None:
                continue
            # 遍历该教师的所有其他课程
            for other_class_id, other_subject_id in self.teacher_assignments.get(locked_teacher_id, []):
                key = (other_class_id, other_subject_id)
                if key in self.schedule_vars and (day, period) in self.schedule_vars[key]:
                    # 该时间片已被锁定，其他课程不能排在这里
                    self.model.Add(self.schedule_vars[key][(day, period)] == 0)

        # H4: 禁排日
        add_day_off_constraint(
            self.model, self.schedule_vars,
            self.teacher_day_off, self.teacher_assignments
        )

        # H5: 场地容量
        add_location_capacity_constraint(
            self.model, self.schedule_vars,
            self.subjects, self.locations
        )

        # H8: 单日上限
        add_max_daily_limit_constraint(
            self.model, self.schedule_vars, self.subjects
        )

        # H9: 连堂课禁止跨越指定节次对
        # 解析设置中的禁跨节次对（格式: "1,2;3,4" -> [(1,2), (3,4)]）
        forbidden_pairs = []
        try:
            for pair_str in self.settings.h9_consecutive_forbidden.split(';'):
                pair_str = pair_str.strip()
                if not pair_str:
                    continue
                parts = pair_str.split(',')
                if len(parts) == 2:
                    forbidden_pairs.append((int(parts[0]), int(parts[1])))
        except:
            forbidden_pairs = [(1, 2), (3, 4)]  # 默认值
        add_consecutive_forbidden_constraint(
            self.model, self.schedule_vars, self.subjects,
            forbidden_pairs=forbidden_pairs
        )

        # H10: 教师周课时上限 (扣除已锁定的课时)
        add_teacher_max_hours_constraint(
            self.model, self.schedule_vars,
            self.teacher_assignments, self.teachers,
            teacher_lock_counts=self.teacher_lock_counts
        )

        # H11: 教师同班单日上限
        add_teacher_class_daily_limit_constraint(
            self.model, self.schedule_vars,
            self.teacher_assignments,
            max_per_class=self.settings.h11_teacher_class_daily_max
        )

        # H12: 校本课程教师占用约束
        # 有分组的教师在校本课程时段不能被安排其他课程
        if self.combined_subject and self.combined_slots:
            add_combined_class_teacher_constraint(
                self.model, self.schedule_vars,
                self.teacher_assignments, self.teachers,
                self.combined_slots
            )

    def add_objectives(self):
        """添加优化目标"""
        objectives = []
        penalties = []
        s = self.settings  # 缩写

        # S1: 上午优先
        objectives.extend(
            add_am_preference_objective(
                self.model, self.schedule_vars, self.subjects,
                weight=s.s1_am_preference_weight
            )
        )

        # S2: 连堂偏好
        objectives.extend(
            add_consecutive_preference_objective(
                self.model, self.schedule_vars, self.subjects,
                weight=s.s2_consecutive_weight
            )
        )

        # S3: 分布均匀 (惩罚)
        penalties.extend(
            add_distribution_penalty(
                self.model, self.schedule_vars, self.subjects,
                weight=s.s3_distribution_weight
            )
        )

        # S4: 教师单日课时均衡
        penalties.extend(
            add_teacher_daily_load_penalty(
                self.model, self.schedule_vars, self.teacher_assignments,
                threshold=s.s4_teacher_daily_threshold,
                weight=s.s4_teacher_daily_weight
            )
        )

        # S5: 避免第一节课
        penalties.extend(
            add_avoid_first_period_penalty(
                self.model, self.schedule_vars, self.subjects,
                weight=s.s5_avoid_first_weight
            )
        )

        # S6: 教师连续换班惩罚
        penalties.extend(
            add_teacher_class_switch_penalty(
                self.model, self.schedule_vars, self.teacher_assignments,
                weight=s.s6_subject_switch_weight
            )
        )

        # S7: 教师同班换科惩罚
        penalties.extend(
            add_teacher_same_class_subject_switch_penalty(
                self.model, self.schedule_vars, self.teacher_assignments,
                weight=s.s7_same_class_subject_switch_weight
            )
        )

        if objectives or penalties:
            self.model.Maximize(sum(objectives) - sum(penalties))

    def solve(self, time_limit_seconds=60):
        """求解"""
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_seconds
        solver.parameters.num_search_workers = self.settings.solver_num_workers

        start_time = time.time()
        status = solver.Solve(self.model)
        solve_time_ms = int((time.time() - start_time) * 1000)

        status_map = {
            cp_model.OPTIMAL: 'OPTIMAL',
            cp_model.FEASIBLE: 'FEASIBLE',
            cp_model.INFEASIBLE: 'INFEASIBLE',
            cp_model.MODEL_INVALID: 'MODEL_INVALID',
            cp_model.UNKNOWN: 'UNKNOWN',
        }

        return {
            'status': status_map.get(status, 'UNKNOWN'),
            'solve_time_ms': solve_time_ms,
            'solver': solver if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None,
        }

    def analyze_infeasibility(self):
        """
        分析无解原因，返回诊断信息
        """
        diagnostics = []

        # 1. 统计总课时需求
        total_hours_needed = 0
        class_hours = defaultdict(int)  # 每班总课时
        class_normal_hours = defaultdict(int)  # 每班普通课时
        teacher_hours = defaultdict(int)  # 每教师总课时

        for (class_id, subject_id), teacher_id in self.class_subject_teacher.items():
            subject = self.subjects[subject_id]
            hours = subject.weekly_hours
            total_hours_needed += hours
            class_hours[class_id] += hours
            class_normal_hours[class_id] += hours
            teacher_hours[teacher_id] += hours

        # 校本课程课时 (固定锁定，不在 class_subject_teacher 中)
        combined_hours_per_class = 0
        if self.combined_subject:
            combined_hours_per_class = len(self.combined_slots)

        # 2. 计算可用时间片
        normal_slots = TOTAL_SLOTS - 1 - len(self.combined_slots)
        combined_slots = len(self.combined_slots)
        total_available_per_class = TOTAL_SLOTS - 1  # 27

        diagnostics.append("[总体统计]")
        diagnostics.append(f"  - 班级数: {len(self.classes)}")
        diagnostics.append(f"  - 每班总可用: {total_available_per_class} (普通课位: {normal_slots}, 校本课程: {combined_slots}, 班会: 1)")
        diagnostics.append(f"  - 普通课总需求: {total_hours_needed}")
        if self.combined_subject:
            diagnostics.append(f"  - 校本课程: 每班{combined_hours_per_class}节 (固定锁定)")

        # 3. 检查每班课时是否超出
        for class_id, hours in class_hours.items():
            class_name = self.classes[class_id].name
            n_hours = class_normal_hours.get(class_id, 0)
            total_with_combined = hours + combined_hours_per_class + 1  # +1 班会

            if total_with_combined > TOTAL_SLOTS:
                diagnostics.append(f"[错误] 班级 [{class_name}] 总课时超出: 需要 {total_with_combined} 节，总时间片 {TOTAL_SLOTS} 个")
            if n_hours > normal_slots:
                diagnostics.append(f"[错误] 班级 [{class_name}] 普通课时超出: 需要 {n_hours} 节，但普通课位只有 {normal_slots} 个")

        # 4. 检查教师工作量和禁排日冲突
        diagnostics.append("")
        diagnostics.append("[教师负载分析]")
        for teacher_id, hours in sorted(teacher_hours.items(), key=lambda x: -x[1]):
            teacher = self.teachers[teacher_id]
            teacher_name = teacher.name
            day_off = self.teacher_day_off.get(teacher_id)

            # 计算教师可用时间片
            if day_off is not None:
                day_off_slots = PERIODS_PER_DAY.get(day_off, 0)
                teacher_available = TOTAL_SLOTS - day_off_slots - 1  # 去掉禁排日和班会
                day_name = DAYS[day_off]
                info = f"  - {teacher_name}: {hours} 节课 (禁排日: {day_name}, 可用: {teacher_available} 节"
            else:
                teacher_available = TOTAL_SLOTS - 1
                info = f"  - {teacher_name}: {hours} 节课 (无禁排日, 可用: {teacher_available} 节"

            # 加上课时范围信息
            min_hours = teacher.min_weekly_hours
            max_hours = teacher.max_weekly_hours
            if min_hours is not None and max_hours is not None:
                info += f", 范围: {min_hours}~{max_hours} 节)"
            elif max_hours is not None:
                info += f", 上限: {max_hours} 节)"
            elif min_hours is not None:
                info += f", 下限: {min_hours} 节)"
            else:
                info += ")"

            has_error = False
            if max_hours is not None and hours > max_hours:
                diagnostics.append(f"[错误] {info} <- 超出上限!")
                has_error = True
            if min_hours is not None and hours < min_hours:
                diagnostics.append(f"[错误] {info} <- 未达到下限!")
                has_error = True

            if not has_error:
                if hours > teacher_available:
                    diagnostics.append(f"[错误] {info} <- 超出可用时段!")
                else:
                    diagnostics.append(info)

        # 5. 检查教师时段冲突 (同时要教多个班)
        diagnostics.append("")
        diagnostics.append("[教师冲突检测]")
        teacher_class_count = defaultdict(list)  # teacher_id -> [(class_id, subject_id, hours), ...]
        for (class_id, subject_id), teacher_id in self.class_subject_teacher.items():
            subject = self.subjects[subject_id]
            teacher_class_count[teacher_id].append((class_id, subject_id, subject.weekly_hours))

        has_conflict = False
        for teacher_id, assignments in teacher_class_count.items():
            if len(assignments) <= 1:
                continue
            teacher_name = self.teachers[teacher_id].name
            day_off = self.teacher_day_off.get(teacher_id)

            # 计算这位教师每天的可用时段
            daily_available = {}
            for day in range(5):
                if day_off == day:
                    daily_available[day] = 0
                elif day == 4:  # 周五
                    daily_available[day] = PERIODS_PER_DAY[day] - 1  # 去掉班会
                else:
                    daily_available[day] = PERIODS_PER_DAY[day]

            total_available = sum(daily_available.values())
            total_needed = sum(a[2] for a in assignments)

            if total_needed > total_available:
                has_conflict = True
                class_list = ', '.join([
                    f"{self.classes[cid].name}-{self.subjects[sid].name}({h}节)"
                    for cid, sid, h in assignments
                ])
                diagnostics.append(f"[错误] {teacher_name} 要教 {len(assignments)} 个班共 {total_needed} 节，但只有 {total_available} 个可用时段")
                diagnostics.append(f"       课程: {class_list}")

        if not has_conflict:
            diagnostics.append("  无明显冲突")

        # 5.6. 教师同班单日上限分析 (H11)
        diagnostics.append("")
        diagnostics.append("[教师同班单日上限分析]")
        # 按 (教师, 班级) 分组
        teacher_class_hours = defaultdict(int)  # (teacher_id, class_id) -> total_hours
        teacher_class_subjects = defaultdict(list)  # (teacher_id, class_id) -> [(subject_name, hours), ...]
        for (class_id, subject_id), teacher_id in self.class_subject_teacher.items():
            subject = self.subjects[subject_id]
            key = (teacher_id, class_id)
            teacher_class_hours[key] += subject.weekly_hours
            teacher_class_subjects[key].append((subject.name, subject.weekly_hours))

        has_h11_issue = False
        for (teacher_id, class_id), total_hours in teacher_class_hours.items():
            teacher = self.teachers[teacher_id]
            class_obj = self.classes[class_id]
            day_off = self.teacher_day_off.get(teacher_id)

            # 计算可用天数
            available_days = 5
            if day_off is not None:
                available_days = 4

            # 每天最多2节，所以最多 available_days * 2
            max_possible = available_days * 2

            if total_hours > max_possible:
                has_h11_issue = True
                subjects_info = ', '.join([f"{name}({h}节)" for name, h in teacher_class_subjects[(teacher_id, class_id)]])
                day_off_info = f", 禁排日: {DAYS[day_off]}" if day_off is not None else ""
                diagnostics.append(
                    f"[错误] {teacher.name} 在 {class_obj.name} 需上 {total_hours} 节 ({subjects_info})"
                    f"{day_off_info}, 但每天最多2节，{available_days}天最多 {max_possible} 节"
                )

        if not has_h11_issue:
            diagnostics.append("  无冲突")

        # 5.7. 检查连堂课与同班单日上限的潜在冲突
        diagnostics.append("")
        diagnostics.append("[连堂课冲突检测]")
        has_consecutive_conflict = False
        for (teacher_id, class_id), subjects_list in teacher_class_subjects.items():
            # 检查是否有连堂课
            has_consecutive = False
            consecutive_hours = 0
            other_hours = 0
            for subject_name, hours in subjects_list:
                # 查找对应的subject对象
                for sid, subj in self.subjects.items():
                    if subj.name == subject_name:
                        if subj.allow_consecutive:
                            has_consecutive = True
                            consecutive_hours += hours
                        else:
                            other_hours += hours
                        break

            # 如果有连堂课且还有其他课程，可能冲突
            if has_consecutive and other_hours > 0:
                teacher = self.teachers[teacher_id]
                class_obj = self.classes[class_id]
                # 连堂课通常意味着某天需要2节，如果还有其他课程也要在同一天，就超过2节
                diagnostics.append(
                    f"[警告] {teacher.name} 在 {class_obj.name}: 连堂课 {consecutive_hours} 节 + 其他 {other_hours} 节"
                    f" - 可能某天需超过2节"
                )
                has_consecutive_conflict = True

        if not has_consecutive_conflict:
            diagnostics.append("  无冲突")

        # 5.5. 校本课程分析
        diagnostics.append("")
        diagnostics.append("[校本课程分析]")

        if not self.combined_subject:
            diagnostics.append("  未配置校本课程")
        else:
            from core.models import CombinedClassGroup
            groups = list(CombinedClassGroup.objects.all())

            diagnostics.append(f"  - 校本课程: {self.combined_subject.name}")
            diagnostics.append(f"  - 锁定时段: {len(self.combined_slots)}个 ({self.settings.combined_class_slots})")
            diagnostics.append(f"  - 分组数量: {len(groups)}个")

            if len(groups) < 4:
                diagnostics.append(f"[错误] 校本课程分组不足，需要4个")

            # 统计各组情况
            for group in groups:
                manual = []
                for tid, t in self.teachers.items():
                    if t.combined_class_group_id == group.id and not t.exclude_from_combined:
                        manual.append(t.name)
                diagnostics.append(f"  - {group.name}: {', '.join(manual) if manual else '(待自动分配)'}")

            # 统计可用教师
            tuesday_available = []
            thursday_available = []
            excluded = []

            for tid, t in self.teachers.items():
                if t.exclude_from_combined:
                    excluded.append(t.name)
                    continue

                day_off = self.teacher_day_off.get(tid)
                if day_off != 1:  # 可以周二
                    tuesday_available.append(t.name)
                if day_off != 3:  # 可以周四
                    thursday_available.append(t.name)

            diagnostics.append(f"  - 可上周二: {len(tuesday_available)}人")
            diagnostics.append(f"  - 可上周四: {len(thursday_available)}人")

            if excluded:
                diagnostics.append(f"  - 不参与: {', '.join(excluded)}")

            if not tuesday_available:
                diagnostics.append(f"[错误] 周二组没有可用教师")
            if not thursday_available:
                diagnostics.append(f"[错误] 周四组没有可用教师")

        # 6. 检查场地容量冲突
        diagnostics.append("")
        diagnostics.append("[场地容量分析]")
        location_demand = defaultdict(int)  # location_type -> 总课时
        for (class_id, subject_id) in self.class_subject_teacher.keys():
            subject = self.subjects[subject_id]
            if subject.location_type and subject.location_type != 'NORMAL':
                location_demand[subject.location_type] += subject.weekly_hours

        if not location_demand:
            diagnostics.append("  无特殊场地需求")
        else:
            for loc_type, demand in location_demand.items():
                capacity = self.locations.get(loc_type, 1)
                # 可用时段 = 每周时段数 * 容量
                max_capacity = (TOTAL_SLOTS - 1) * capacity  # 去掉班会时段
                if demand > max_capacity:
                    diagnostics.append(f"[错误] 场地 [{loc_type}] 容量不足: 需要 {demand} 节课，但容量只支持 {max_capacity} 节 (容量={capacity})")
                else:
                    diagnostics.append(f"  - {loc_type}: 需求 {demand} 节，容量 {max_capacity} 节 (容量={capacity})")

        # 7. 检查单日上限约束
        diagnostics.append("")
        diagnostics.append("[单日上限分析]")
        has_daily_issue = False
        for (class_id, subject_id) in self.class_subject_teacher.keys():
            subject = self.subjects[subject_id]
            class_name = self.classes[class_id].name
            max_daily = subject.max_daily_limit
            weekly_hours = subject.weekly_hours

            # 计算该班级该课程实际可用天数
            teacher_id = self.class_subject_teacher[(class_id, subject_id)]
            day_off = self.teacher_day_off.get(teacher_id)
            avail_days = 5
            if day_off is not None:
                avail_days -= 1

            if max_daily * avail_days < weekly_hours:
                has_daily_issue = True
                diagnostics.append(f"[错误] {class_name}-{subject.name}: 周课时 {weekly_hours} 节，单日上限 {max_daily}，可用 {avail_days} 天，最多排 {max_daily * avail_days} 节")

        if not has_daily_issue:
            diagnostics.append("  无单日上限冲突")

        return diagnostics

    def save_auto_assignments(self):
        """保存自动分配的教师到数据库"""
        for item in self.auto_assigned:
            ClassSubjectTeacher.objects.update_or_create(
                school_class_id=item['class_id'],
                subject_id=item['subject_id'],
                defaults={
                    'teacher_id': item['teacher_id'],
                    'is_manual': False
                }
            )

    def save_combined_class_assignments(self, group_data):
        """将校本课程分组分配结果转换为可保存的格式

        Args:
            group_data: {group_id: {"tuesday": [teacher_ids], "thursday": [teacher_ids]}}

        Returns:
            dict: {
                "分组名": {
                    "周二": ["教师名1", ...],
                    "周四": ["教师名2", ...]
                }, ...
            }
        """
        if not group_data:
            return {}

        from core.models import CombinedClassGroup

        # 获取分组名称
        groups = {g.id: g.name for g in CombinedClassGroup.objects.all()}

        result = {}
        for group_id, day_data in group_data.items():
            group_name = groups.get(group_id, f"分组{group_id}")

            tuesday_names = [self.teachers[tid].name for tid in day_data.get("tuesday", []) if tid in self.teachers]
            thursday_names = [self.teachers[tid].name for tid in day_data.get("thursday", []) if tid in self.teachers]

            result[group_name] = {
                "周二": tuesday_names,
                "周四": thursday_names
            }

        return result

    def save_result(self, solve_result, combined_assignments=None):
        """保存排课结果"""
        result = ScheduleResult.objects.create(
            solve_status=solve_result['status'],
            solve_time_ms=solve_result['solve_time_ms'],
            is_active=(solve_result['status'] in ['OPTIMAL', 'FEASIBLE']),
            combined_class_assignments=combined_assignments or {},
        )

        entries = []

        # 保存预锁定条目
        for entry_data in self.locked_entries:
            entries.append(ScheduleEntry(
                result=result,
                school_class_id=entry_data['school_class_id'],
                subject_id=entry_data['subject_id'],
                teacher_id=entry_data['teacher_id'],
                day=entry_data['day'],
                period=entry_data['period'],
                is_locked=True,
            ))

        # 保存求解结果
        if solve_result['solver']:
            solver = solve_result['solver']
            for (class_id, subject_id), slots in self.schedule_vars.items():
                teacher_id = self.class_subject_teacher[(class_id, subject_id)]
                for (day, period), var in slots.items():
                    if solver.Value(var) == 1:
                        entries.append(ScheduleEntry(
                            result=result,
                            school_class_id=class_id,
                            subject_id=subject_id,
                            teacher_id=teacher_id,
                            day=day,
                            period=period,
                            is_locked=False,
                        ))

        ScheduleEntry.objects.bulk_create(entries)
        return result

    def run(self, time_limit_seconds=60):
        """运行排课"""
        # 1. 加载数据
        self.load_data()

        # 2. 验证基础数据
        if not self.validate_data():
            return {
                'success': False,
                'errors': self.errors,
                'diagnostics': [],
                'result': None,
            }

        # 3. 自动分配教师 (普通课程，跳过校本课程)
        if not self.auto_assign_teachers():
            return {
                'success': False,
                'errors': self.errors,
                'diagnostics': [],
                'result': None,
            }

        # 3.5 分配校本课程教师到分组
        self.combined_group_teachers = self.assign_combined_class_teachers()
        if self.errors:
            return {
                'success': False,
                'errors': self.errors,
                'diagnostics': [],
                'result': None,
            }

        # 4. 检查是否有课程需要排
        if not self.class_subject_teacher and not self.combined_subject:
            self.errors.append("没有课程需要排课 (请设置教师资质或手动分配)")
            return {
                'success': False,
                'errors': self.errors,
                'diagnostics': [],
                'result': None,
            }

        # 5. 创建变量
        self.create_variables()

        # 6. 添加预锁定 (班会 + 校本课程)
        self.add_locked_entries()

        # 7. 添加约束
        self.add_constraints()

        # 8. 添加目标
        self.add_objectives()

        # 9. 求解
        solve_result = self.solve(time_limit_seconds)

        # 10. 如果无解，进行诊断分析
        diagnostics = []
        if solve_result['status'] == 'INFEASIBLE':
            diagnostics = self.analyze_infeasibility()
            self.errors.append("排课无解，请查看诊断信息")

        # 11. 如果成功，保存自动分配
        combined_assignments = {}
        if solve_result['status'] in ['OPTIMAL', 'FEASIBLE']:
            self.save_auto_assignments()
            # 生成校本课程分组分配结果（不保存到Teacher，保存到ScheduleResult）
            if self.combined_group_teachers:
                combined_assignments = self.save_combined_class_assignments(self.combined_group_teachers)

        # 12. 保存结果（包含校本课程分配）
        result = self.save_result(solve_result, combined_assignments)

        return {
            'success': solve_result['status'] in ['OPTIMAL', 'FEASIBLE'],
            'errors': self.errors,
            'diagnostics': diagnostics,
            'result': result,
            'status': solve_result['status'],
            'solve_time_ms': solve_result['solve_time_ms'],
            'auto_assigned_count': len(self.auto_assigned),
        }


def run_scheduler(time_limit_seconds=60, max_attempts=10, total_timeout_seconds=120):
    """
    便捷函数: 运行排课

    Args:
        time_limit_seconds: 每次求解的时间限制
        max_attempts: 最大尝试次数
        total_timeout_seconds: 总超时时间（秒）

    Returns:
        dict: 包含排课结果和重试统计信息
    """
    import time as time_module

    start_time = time_module.time()
    attempts = 0
    failures = []  # 记录每次失败的原因
    result = None  # 保存最后一次尝试的结果
    saved_diagnostics = []  # 保存第一次"排课无解"的诊断信息

    while attempts < max_attempts:
        elapsed = time_module.time() - start_time
        if elapsed >= total_timeout_seconds:
            break

        attempts += 1
        remaining_time = total_timeout_seconds - elapsed
        solve_time = min(time_limit_seconds, remaining_time)

        if solve_time <= 0:
            break

        engine = ScheduleEngine()
        result = engine.run(time_limit_seconds=solve_time)

        if result['success']:
            # 成功，返回结果加上统计信息
            result['retry_stats'] = {
                'attempts': attempts,
                'failures': len(failures),
                'success_rate': 1 / attempts * 100,
                'total_time_ms': int((time_module.time() - start_time) * 1000),
                'failure_reasons': failures[-5:],  # 只返回最近5次失败原因
            }
            return result
        else:
            # 记录失败原因
            failure_reason = result['errors'][0] if result['errors'] else 'Unknown'
            failures.append({
                'attempt': attempts,
                'reason': failure_reason[:100],  # 截断过长的错误信息
            })
            # 保存第一次"排课无解"的诊断信息
            if not saved_diagnostics and result.get('diagnostics'):
                saved_diagnostics = result['diagnostics']

    # 所有尝试都失败了，返回最后一次的结果
    total_time = int((time_module.time() - start_time) * 1000)

    # 使用保存的诊断信息（如果有的话）
    final_diagnostics = saved_diagnostics or (result.get('diagnostics', []) if result else [])

    # 创建一个汇总结果
    final_result = {
        'success': False,
        'errors': [f"尝试 {attempts} 次后仍然失败"],
        'diagnostics': final_diagnostics,
        'result': result.get('result') if result else None,
        'status': 'FAILED_ALL_ATTEMPTS',
        'solve_time_ms': total_time,
        'auto_assigned_count': 0,
        'retry_stats': {
            'attempts': attempts,
            'failures': len(failures),
            'success_rate': 0,
            'total_time_ms': total_time,
            'failure_reasons': failures[-10:],  # 返回更多失败原因用于诊断
        }
    }

    return final_result
