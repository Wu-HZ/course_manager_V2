from django.test import SimpleTestCase, TestCase
from ortools.sat.python import cp_model

from core.models import (
    SchedulerSettings, SchoolClass, Subject, Teacher, TeacherQualification,
)

from .constraints import (
    add_consecutive_forbidden_constraint,
    add_teacher_exclusion_constraint,
)
from .engine import ScheduleEngine
from .views import _build_precheck_payload


class ConsecutiveForbiddenConstraintTests(SimpleTestCase):
    def find_linear_constraints(self, model, vars_set):
        matched = []
        for constraint in model.Proto().constraints:
            if not constraint.has_linear():
                continue
            linear = constraint.linear
            if set(linear.vars) != vars_set:
                continue
            if any(coeff != 1 for coeff in linear.coeffs):
                continue
            matched.append(linear)
        return matched

    def test_h9_blocks_teacher_consecutive_classes_across_forbidden_boundary(self):
        model = cp_model.CpModel()
        class_a_period_2 = model.NewBoolVar('class_a_period_2')
        class_b_period_3 = model.NewBoolVar('class_b_period_3')

        schedule_vars = {
            (1, 101): {(0, 1): class_a_period_2},
            (2, 102): {(0, 2): class_b_period_3},
        }
        teacher_assignments = {
            10: [(1, 101), (2, 102)],
        }

        add_teacher_exclusion_constraint(model, schedule_vars, teacher_assignments)
        add_consecutive_forbidden_constraint(
            model,
            schedule_vars,
            teacher_assignments,
            forbidden_pairs=[(1, 2)],
        )

        matched = self.find_linear_constraints(
            model,
            {class_a_period_2.Index(), class_b_period_3.Index()},
        )
        self.assertEqual(len(matched), 1)

    def test_h9_does_not_block_non_forbidden_adjacent_periods(self):
        model = cp_model.CpModel()
        class_a_period_1 = model.NewBoolVar('class_a_period_1')
        class_b_period_2 = model.NewBoolVar('class_b_period_2')

        schedule_vars = {
            (1, 101): {(0, 0): class_a_period_1},
            (2, 102): {(0, 1): class_b_period_2},
        }
        teacher_assignments = {
            10: [(1, 101), (2, 102)],
        }

        add_teacher_exclusion_constraint(model, schedule_vars, teacher_assignments)
        add_consecutive_forbidden_constraint(
            model,
            schedule_vars,
            teacher_assignments,
            forbidden_pairs=[(1, 2)],
        )

        matched = self.find_linear_constraints(
            model,
            {class_a_period_1.Index(), class_b_period_2.Index()},
        )
        self.assertEqual(matched, [])


class HomeroomMainSubjectAssignmentTests(TestCase):
    """H14: 班主任必须担任主课开关在教师自动分配阶段的行为。"""

    def setUp(self):
        self.settings = SchedulerSettings.get_settings()
        # 一门主课 + 一门副课
        self.chinese = Subject.objects.create(
            name='语文', weekly_hours=1, is_main_subject=True
        )
        self.pe = Subject.objects.create(
            name='体育', weekly_hours=1, max_teacher_classes=5
        )
        # 班主任只有副课资质，另一位教师才有主课资质
        self.homeroom = Teacher.objects.create(name='班主任')
        self.other = Teacher.objects.create(name='主课老师')
        self.klass = SchoolClass.objects.create(
            name='一年级1班', grade=1, homeroom_teacher=self.homeroom
        )
        TeacherQualification.objects.create(teacher=self.homeroom, subject=self.pe)
        TeacherQualification.objects.create(teacher=self.other, subject=self.chinese)

    def _assign(self):
        engine = ScheduleEngine()
        engine.load_data()
        ok = engine.auto_assign_teachers()
        return engine, ok

    def test_enabled_blocks_homeroom_without_main_subject(self):
        self.settings.h14_homeroom_main_subject = True
        self.settings.save()

        engine, ok = self._assign()

        self.assertFalse(ok)
        self.assertTrue(
            any('必须' in e and '主课' in e for e in engine.errors),
            engine.errors,
        )

    def test_disabled_allows_homeroom_without_main_subject(self):
        self.settings.h14_homeroom_main_subject = False
        self.settings.save()

        engine, ok = self._assign()

        self.assertTrue(ok, engine.errors)
        self.assertFalse(any('主课' in e for e in engine.errors), engine.errors)

    def test_enabled_assigns_main_subject_to_qualified_homeroom(self):
        # 班主任同时具备主课资质时，应被优先分配主课
        TeacherQualification.objects.create(teacher=self.homeroom, subject=self.chinese)
        self.settings.h14_homeroom_main_subject = True
        self.settings.save()

        engine, ok = self._assign()

        self.assertTrue(ok, engine.errors)
        self.assertEqual(
            engine.class_subject_teacher[(self.klass.id, self.chinese.id)],
            self.homeroom.id,
        )


class MainSubjectLimitAssignmentTests(TestCase):
    """H15: 单师最多主课数，以及主课跨班受 max_teacher_classes 控制的行为。"""

    def setUp(self):
        self.settings = SchedulerSettings.get_settings()
        # 唯一候选教师，便于断言分配结果是确定的
        self.teacher = Teacher.objects.create(name='全能老师')

    def _main_subject(self, name, max_classes=1):
        return Subject.objects.create(
            name=name, weekly_hours=1, is_main_subject=True,
            max_teacher_classes=max_classes,
        )

    def _qualify(self, *subjects):
        for subject in subjects:
            TeacherQualification.objects.create(teacher=self.teacher, subject=subject)

    def _set_limit(self, value):
        self.settings.h15_teacher_max_main_subjects = value
        self.settings.save()

    def _assign(self):
        engine = ScheduleEngine()
        engine.load_data()
        ok = engine.auto_assign_teachers()
        return engine, ok

    def test_limit_one_blocks_second_main_subject(self):
        chinese = self._main_subject('语文')
        math = self._main_subject('数学')
        self._qualify(chinese, math)
        SchoolClass.objects.create(name='一班', grade=1)  # 无班主任，绕开 H14
        self._set_limit(1)

        engine, ok = self._assign()

        self.assertFalse(ok)
        self.assertTrue(any('分配教师' in e for e in engine.errors), engine.errors)

    def test_higher_limit_allows_multiple_main_subjects(self):
        chinese = self._main_subject('语文')
        math = self._main_subject('数学')
        self._qualify(chinese, math)
        klass = SchoolClass.objects.create(name='一班', grade=1)
        self._set_limit(2)

        engine, ok = self._assign()

        self.assertTrue(ok, engine.errors)
        self.assertEqual(
            engine.class_subject_teacher[(klass.id, chinese.id)], self.teacher.id
        )
        self.assertEqual(
            engine.class_subject_teacher[(klass.id, math.id)], self.teacher.id
        )

    def test_same_main_subject_across_classes_within_class_limit(self):
        # 副作用修正：同一门主课可带多个班（受 max_teacher_classes 控制），限额仍为 1
        chinese = self._main_subject('语文', max_classes=2)
        self._qualify(chinese)
        c1 = SchoolClass.objects.create(name='一班', grade=1)
        c2 = SchoolClass.objects.create(name='二班', grade=1)
        self._set_limit(1)

        engine, ok = self._assign()

        self.assertTrue(ok, engine.errors)
        self.assertEqual(
            engine.class_subject_teacher[(c1.id, chinese.id)], self.teacher.id
        )
        self.assertEqual(
            engine.class_subject_teacher[(c2.id, chinese.id)], self.teacher.id
        )

    def test_class_limit_caps_same_main_subject(self):
        # max_teacher_classes=1 时主课老师只能带一个班，第二个班无人可分
        chinese = self._main_subject('语文', max_classes=1)
        self._qualify(chinese)
        SchoolClass.objects.create(name='一班', grade=1)
        SchoolClass.objects.create(name='二班', grade=1)
        self._set_limit(1)

        engine, ok = self._assign()

        self.assertFalse(ok)
        self.assertTrue(any('分配教师' in e for e in engine.errors), engine.errors)


class H11DiagnosticsTests(TestCase):
    """无解诊断中的 H11 同班单日上限应使用配置值，而非写死的 2。"""

    def test_diagnostic_uses_configured_daily_limit(self):
        settings = SchedulerSettings.get_settings()
        settings.h11_teacher_class_daily_max = 3
        settings.save()

        teacher = Teacher.objects.create(name='李老师')
        # 单门课课时高到必然超过 available_days * h11，触发 H11 诊断
        subject = Subject.objects.create(
            name='阅读', weekly_hours=16, max_teacher_classes=5
        )
        TeacherQualification.objects.create(teacher=teacher, subject=subject)
        SchoolClass.objects.create(name='一班', grade=1)

        engine = ScheduleEngine()
        engine.load_data()
        self.assertTrue(engine.auto_assign_teachers(), engine.errors)
        diagnostics = engine.analyze_infeasibility()

        h11_lines = [d for d in diagnostics if '每天最多' in d]
        self.assertTrue(h11_lines, diagnostics)
        self.assertTrue(any('每天最多3节' in d for d in h11_lines), h11_lines)
        self.assertFalse(any('每天最多2节' in d for d in h11_lines), h11_lines)


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
