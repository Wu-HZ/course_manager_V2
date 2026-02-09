from django.db import models


DAY_CHOICES = [
    (0, '周一'),
    (1, '周二'),
    (2, '周三'),
    (3, '周四'),
    (4, '周五'),
]

LOCATION_TYPES = [
    ('NORMAL', '普通教室'),
    ('PLAYGROUND', '操场'),
    ('LAB', '实验室'),
    ('HOME_EC', '家政室'),
]


class TravelGroup(models.Model):
    """出差分组 - 关联一个禁排日"""
    name = models.CharField('分组名称', max_length=50)
    day_off = models.IntegerField('禁排日', choices=DAY_CHOICES)

    class Meta:
        verbose_name = '出差分组'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} (禁排: {self.get_day_off_display()})"


class Subject(models.Model):
    """课程"""
    name = models.CharField('课程名称', max_length=50)
    weekly_hours = models.IntegerField('周课时数', default=1)
    is_am_preferred = models.BooleanField('上午优先', default=False)
    allow_consecutive = models.BooleanField('允许连堂', default=False)
    max_daily_limit = models.IntegerField('单日上限', default=1)
    location_type = models.CharField(
        '场地类型', max_length=20, choices=LOCATION_TYPES, default='NORMAL'
    )
    is_combined_class = models.BooleanField('合班课', default=False)
    applicable_grades = models.CharField(
        '适用年级', max_length=50, blank=True, default='',
        help_text='逗号分隔的年级列表，如"1,2,3"。留空表示所有年级'
    )
    avoid_first_period = models.BooleanField(
        '避免第一节', default=False,
        help_text='勾选后尽量不安排在每天第一节课'
    )
    is_main_subject = models.BooleanField(
        '主课', default=False,
        help_text='主课(如语文数学英语)，同一教师只能教一门主课'
    )
    max_teacher_classes = models.IntegerField(
        '单师最多班数', default=1,
        help_text='同一教师最多可教几个班的该课程(1~5)'
    )

    class Meta:
        verbose_name = '课程'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

    def get_applicable_grades_list(self):
        """返回适用年级列表，空列表表示所有年级"""
        if not self.applicable_grades:
            return []
        return [int(g.strip()) for g in self.applicable_grades.split(',') if g.strip()]

    def is_applicable_for_grade(self, grade):
        """检查课程是否适用于指定年级"""
        grades = self.get_applicable_grades_list()
        return not grades or grade in grades


class CombinedClassGroup(models.Model):
    """校本课程分组 - 4个教师小组"""
    name = models.CharField('分组名称', max_length=50)

    class Meta:
        verbose_name = '校本课程分组'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Teacher(models.Model):
    """教师"""
    COMBINED_DAY_CHOICES = [
        (1, '周二'),
        (3, '周四'),
    ]

    name = models.CharField('姓名', max_length=50)
    travel_group = models.ForeignKey(
        TravelGroup, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='出差分组'
    )
    combined_class_group = models.ForeignKey(
        CombinedClassGroup, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='校本课程分组',
        help_text='手动指定该教师属于哪个校本课程组，留空则自动分配'
    )
    combined_class_day = models.IntegerField(
        '校本课程日期', choices=COMBINED_DAY_CHOICES,
        null=True, blank=True,
        help_text='手动指定该教师上校本课程的日期，留空则自动分配'
    )
    exclude_from_combined = models.BooleanField(
        '不参与校本课程', default=False,
        help_text='勾选后该教师不会被分配到校本课程'
    )
    min_weekly_hours = models.IntegerField(
        '周课时下限', null=True, blank=True,
        help_text='至少安排多少节课，留空表示不限制'
    )
    max_weekly_hours = models.IntegerField(
        '周课时上限', null=True, blank=True,
        help_text='至多安排多少节课，留空表示不限制'
    )

    class Meta:
        verbose_name = '教师'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    """班级"""
    name = models.CharField('班级名称', max_length=50)
    grade = models.IntegerField('年级', default=1)
    homeroom_teacher = models.OneToOneField(
        Teacher, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='homeroom_class',
        verbose_name='班主任'
    )

    class Meta:
        verbose_name = '班级'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Location(models.Model):
    """场地"""
    name = models.CharField('场地名称', max_length=50)
    location_type = models.CharField(
        '场地类型', max_length=20, choices=LOCATION_TYPES
    )
    capacity = models.IntegerField('同时容纳班数', default=1)

    class Meta:
        verbose_name = '场地'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} ({self.get_location_type_display()}, 容量:{self.capacity})"


class TeacherQualification(models.Model):
    """教师资质 - 老师可以教哪些课程"""
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, verbose_name='教师',
        related_name='qualifications'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, verbose_name='课程',
        related_name='qualified_teachers'
    )

    class Meta:
        verbose_name = '教师资质'
        verbose_name_plural = verbose_name
        unique_together = ('teacher', 'subject')

    def __str__(self):
        return f"{self.teacher.name} - {self.subject.name}"


class ClassSubjectTeacher(models.Model):
    """班级-课程-教师 三元关联 (手动指定，可选)"""
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, verbose_name='班级',
        related_name='subject_assignments'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, verbose_name='课程'
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, verbose_name='教师'
    )
    is_manual = models.BooleanField('手动指定', default=True,
        help_text='手动指定的分配不会被自动分配覆盖')

    class Meta:
        verbose_name = '授课分配'
        verbose_name_plural = verbose_name
        unique_together = ('school_class', 'subject')

    def __str__(self):
        return f"{self.school_class.name} - {self.subject.name} - {self.teacher.name}"


class ScheduleLock(models.Model):
    """课表锁定 - 直接指定某节课的具体时间"""
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, verbose_name='班级',
        related_name='schedule_locks'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, verbose_name='课程'
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, verbose_name='教师',
        null=True, blank=True,
        help_text='留空则使用授课分配中的教师'
    )
    day = models.IntegerField('星期', choices=DAY_CHOICES)
    period = models.IntegerField('节次')

    class Meta:
        verbose_name = '课表锁定'
        verbose_name_plural = verbose_name
        unique_together = ('school_class', 'day', 'period')  # 同班同时间只能锁定一门课

    def __str__(self):
        return f"{self.school_class.name} 周{self.day+1}第{self.period+1}节 {self.subject.name}"


class SchedulerSettings(models.Model):
    """排课参数设置（单例模式，只有一条记录）"""

    # 基础配置
    class_meeting_name = models.CharField(
        '班会课程名', max_length=50, default='班会',
        help_text='班会课的课程名称，如"班会"、"班队会"、"主题班会"等'
    )
    combined_class_slots = models.CharField(
        '合班课时段', max_length=100, default='1,4;1,5;3,4;3,5',
        help_text='校本课程/合班课的时段，格式"星期,节次"用分号分隔，如"1,4;1,5;3,4;3,5"表示周二下午和周四下午'
    )
    solver_num_workers = models.IntegerField(
        '求解器线程数', default=4,
        help_text='并行计算的线程数，建议设为CPU核心数'
    )

    # 硬约束参数
    h9_consecutive_forbidden = models.CharField(
        '连堂禁跨节次对', max_length=50, default='1,2;3,4',
        help_text='禁止连堂跨越的节次对，格式如"1,2;3,4"表示第2-3节和第4-5节之间不能连堂（0起始）'
    )
    h11_teacher_class_daily_max = models.IntegerField(
        '教师同班单日上限', default=2,
        help_text='同一教师同一天在同一班级最多上几节课'
    )

    # 软约束权重
    s1_am_preference_weight = models.IntegerField(
        '上午优先权重', default=10,
        help_text='标记"上午优先"的课程排在上午的奖励分'
    )
    s2_consecutive_weight = models.IntegerField(
        '连堂偏好权重', default=5,
        help_text='允许连堂的课程连续排列的奖励分'
    )
    s3_distribution_weight = models.IntegerField(
        '分布均匀权重', default=2,
        help_text='同课同班同天超过1节的惩罚分'
    )
    s4_teacher_daily_threshold = models.IntegerField(
        '教师日负载阈值', default=3,
        help_text='教师单日课时超过此值开始惩罚'
    )
    s4_teacher_daily_weight = models.IntegerField(
        '教师日负载权重', default=8,
        help_text='教师单日课时超出阈值的惩罚分'
    )
    s5_avoid_first_weight = models.IntegerField(
        '避免第一节权重', default=6,
        help_text='标记"避免第一节"的课程排在第一节的惩罚分'
    )
    s6_subject_switch_weight = models.IntegerField(
        '换班惩罚权重', default=5,
        help_text='教师连续两节在不同班级上课的惩罚分'
    )
    s7_same_class_subject_switch_weight = models.IntegerField(
        '同班换科惩罚权重', default=3,
        help_text='教师连续两节在同一班级但上不同科目的惩罚分'
    )

    class Meta:
        verbose_name = '排课参数设置'
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        # 单例模式：强制只有一条记录
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """获取设置（如果不存在则创建默认值）"""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_combined_class_slots_list(self):
        """解析合班课时段字符串，返回 [(day, period), ...] 列表"""
        slots = []
        try:
            for slot_str in self.combined_class_slots.split(';'):
                slot_str = slot_str.strip()
                if not slot_str:
                    continue
                parts = slot_str.split(',')
                if len(parts) == 2:
                    day = int(parts[0].strip())
                    period = int(parts[1].strip())
                    slots.append((day, period))
        except (ValueError, AttributeError):
            # 解析失败，返回默认值
            slots = [(1, 4), (1, 5), (3, 4), (3, 5)]
        return slots
