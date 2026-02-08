from django.db import models
from core.models import SchoolClass, Subject, Teacher


class ScheduleResult(models.Model):
    """排课结果集"""
    SOLVE_STATUS_CHOICES = [
        ('OPTIMAL', '最优解'),
        ('FEASIBLE', '可行解'),
        ('INFEASIBLE', '无可行解'),
        ('MODEL_INVALID', '模型无效'),
        ('UNKNOWN', '未知'),
    ]

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    is_active = models.BooleanField('当前使用', default=False)
    solve_status = models.CharField(
        '求解状态', max_length=20, choices=SOLVE_STATUS_CHOICES, default='UNKNOWN'
    )
    solve_time_ms = models.IntegerField('求解耗时(ms)', default=0)
    notes = models.TextField('备注', blank=True)
    combined_class_assignments = models.JSONField(
        '校本课程分组分配', default=dict, blank=True,
        help_text='格式: {"分组名": ["教师名1", "教师名2", ...]}'
    )

    class Meta:
        verbose_name = '排课结果'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"排课结果 #{self.id} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    def save(self, *args, **kwargs):
        # 如果设为当前使用, 取消其他结果的激活状态
        if self.is_active:
            ScheduleResult.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class ScheduleEntry(models.Model):
    """排课结果单条记录"""
    result = models.ForeignKey(
        ScheduleResult, on_delete=models.CASCADE,
        related_name='entries', verbose_name='排课结果'
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, verbose_name='班级'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, verbose_name='课程'
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, verbose_name='教师',
        null=True, blank=True  # 校本课程不指定具体教师
    )
    day = models.IntegerField('星期')  # 0-4
    period = models.IntegerField('节次')  # 0-5
    is_locked = models.BooleanField('锁定', default=False)  # 班会/合班预锁定

    class Meta:
        verbose_name = '课表条目'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['result', 'school_class']),
            models.Index(fields=['result', 'teacher']),
            models.Index(fields=['result', 'day', 'period']),
        ]

    def __str__(self):
        from .time_slots import slot_to_str
        return f"{self.school_class.name} {slot_to_str(self.day, self.period)} {self.subject.name}"
