from django.test import TestCase

from core.models import (
    SchedulerSettings, SchoolClass, Subject, Teacher, TeacherQualification,
)
# 旧引擎已删除，以下导入保留以便将来为新引擎补测试时参考：
# from ortools.sat.python import cp_model
# from .constraints import (
#     add_consecutive_forbidden_constraint,
#     add_teacher_exclusion_constraint,
# )
# from .engine import ScheduleEngine
from .views import _build_precheck_payload


# ═══════════════════════════════════════════════════════════════
# 以下测试类依赖已删除的旧引擎（engine.py / constraints.py），
# 代码保留作为将来为 V2 引擎补测试时的参考。
# ═══════════════════════════════════════════════════════════════
# class ConsecutiveForbiddenConstraintTests(SimpleTestCase):
#     ...
#
# class HomeroomMainSubjectAssignmentTests(TestCase):
#     """H14: 班主任必须担任主课开关在教师自动分配阶段的行为。"""
#     ...
#
# class MainSubjectLimitAssignmentTests(TestCase):
#     """H15: 单师最多主课数，以及主课跨班受 max_teacher_classes 控制的行为。"""
#     ...
#
# class H11DiagnosticsTests(TestCase):
#     """无解诊断中的 H11 同班单日上限应使用配置值，而非写死的 2。"""
#     ...
# ═══════════════════════════════════════════════════════════════


class PrecheckTeacherCapacityTests(TestCase):
    """排课前预检中的教师供需/容量分析。"""

    def test_capacity_shortage_blocks_run(self):
        # 1 门普通课、适用 3 个班，但只有 1 位合格教师且单师最多带 1 班 → 容量不足
        subject = Subject.objects.create(name='语文', weekly_hours=1, max_teacher_classes=1)
        teacher = Teacher.objects.create(name='张老师')
        TeacherQualification.objects.create(teacher=teacher, subject=subject)
        for i in range(3):
            SchoolClass.objects.create(name=f'{i + 1}班', grade=1)

        payload = _build_precheck_payload()

        block_keys = [issue['key'] for issue in payload['blocking_issues']]
        self.assertIn('teacher_capacity_shortage', block_keys)
        self.assertFalse(payload['summary']['can_run'])
        self.assertEqual(payload['summary']['teacher_capacity_shortage_count'], 1)
        shortage = next(
            issue for issue in payload['blocking_issues']
            if issue['key'] == 'teacher_capacity_shortage'
        )
        self.assertIn('语文', shortage['detail'])

    def test_sufficient_capacity_passes(self):
        subject = Subject.objects.create(name='语文', weekly_hours=1, max_teacher_classes=1)
        teacher = Teacher.objects.create(name='张老师')
        TeacherQualification.objects.create(teacher=teacher, subject=subject)
        SchoolClass.objects.create(name='1班', grade=1)

        payload = _build_precheck_payload()

        block_keys = [issue['key'] for issue in payload['blocking_issues']]
        self.assertNotIn('teacher_capacity_shortage', block_keys)
        passed_keys = [check['key'] for check in payload['passed_checks']]
        self.assertIn('teacher_capacity', passed_keys)
        self.assertEqual(payload['summary']['normal_subject_hours'], 1)
        self.assertGreaterEqual(payload['summary']['estimated_min_teachers'], 1)
