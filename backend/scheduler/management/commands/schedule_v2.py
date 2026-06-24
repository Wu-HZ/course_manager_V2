"""新联合排课引擎冒烟测试命令。

用法： ``python manage.py schedule_v2 [--time-limit 60] [--workers 8] [--show 1]``

第一阶段验收（§9）：对真实数据要么给出可行解、要么判定无解；并用解出的课表
反验 H1/H2/H3/H4 与预占片是否真的被满足。
"""
from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand

from scheduler.service import run_first_stage


class Command(BaseCommand):
    help = "运行新联合排课引擎（第一阶段：最小硬约束 H1/H2/H3/H4）并自检"

    def add_arguments(self, parser):
        parser.add_argument("--time-limit", type=int, default=60, help="求解时限（秒）")
        parser.add_argument("--workers", type=int, default=8, help="求解器线程数")
        parser.add_argument("--show", type=int, default=1, help="打印前 N 个班的课表网格")

    def handle(self, *args, **opts):
        out = run_first_stage(opts["time_limit"], opts["workers"])
        problem = out["problem"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== 规模 ==="))
        self.stdout.write(
            f"班级 {len(problem.classes)} · 课程 {len(problem.subjects)} · "
            f"教师 {len(problem.teachers)} · active 需求 {len(problem.demands)} · "
            f"周时间片 {problem.calendar.total_slots()}"
        )

        if not out["ok"]:
            self.stdout.write(self.style.ERROR("静态预检失败（求解前即可判定无解）："))
            for e in out["errors"]:
                self.stdout.write("  - " + e)
            return

        r = out["result"]
        self.stdout.write(self.style.MIGRATE_HEADING("=== 求解 ==="))
        self.stdout.write(
            f"状态 {r.status} · 变量 {r.num_vars} · 约束 {r.num_constraints} · "
            f"耗时 {r.solve_time_ms}ms · 排定课时 {len(r.lessons)}"
        )
        if r.status not in ("OPTIMAL", "FEASIBLE"):
            self.stdout.write(self.style.WARNING("无可行解 / 未知——这本身可能就是正确结论。"))
            return

        issues = self._verify(problem, r.lessons)
        if issues:
            self.stdout.write(self.style.ERROR(f"自检发现 {len(issues)} 处违反约束："))
            for msg in issues[:30]:
                self.stdout.write("  ✗ " + msg)
        else:
            self.stdout.write(self.style.SUCCESS("自检通过：H1/H2/H3/H4 与预占片全部满足。"))

        self._print_grids(problem, r.lessons, opts["show"])

    def _verify(self, problem, lessons) -> list[str]:
        """用解出的课表直接反验各硬约束，返回违反项描述。"""
        cal = problem.calendar
        issues: list[str] = []

        # H1：每 (班, 课) 排的节数 == 应排节数
        per_cs: dict = defaultdict(int)
        for lesson in lessons:
            per_cs[(lesson.class_id, lesson.subject_id)] += 1
        for d in problem.demands:
            got = per_cs.get((d.class_id, d.subject_id), 0)
            if got != d.hours_to_place:
                cname = problem.classes[d.class_id].name
                sname = problem.subjects[d.subject_id].name
                issues.append(f"H1 周课时：{cname}/{sname} 排了 {got} 节，应为 {d.hours_to_place}")

        # H2：同班同片至多一门课
        class_slot: dict = defaultdict(int)
        for lesson in lessons:
            class_slot[(lesson.class_id, lesson.day, lesson.period)] += 1
        for (c, dd, pp), n in class_slot.items():
            if n > 1:
                issues.append(f"H2 班级互斥：{problem.classes[c].name} 在 ({dd},{pp}) 有 {n} 门课")

        # H3：同师同片至多一节课
        teacher_slot: dict = defaultdict(int)
        for lesson in lessons:
            teacher_slot[(lesson.teacher_id, lesson.day, lesson.period)] += 1
        for (t, dd, pp), n in teacher_slot.items():
            if t is not None and n > 1:
                issues.append(f"H3 教师互斥：{problem.teachers[t].name} 在 ({dd},{pp}) 上 {n} 节")

        # H4：禁排日不排课
        for lesson in lessons:
            if lesson.teacher_id is None:
                continue
            doff = problem.teachers[lesson.teacher_id].day_off
            if doff is not None and lesson.day == doff:
                issues.append(
                    f"H4 禁排日：{problem.teachers[lesson.teacher_id].name} 在禁排日 {doff} 被排课"
                )

        # 预占片：班会/校本/用户锁定片不应出现普通课
        for lesson in lessons:
            if cal.is_reserved(lesson.day, lesson.period):
                issues.append(
                    f"预占片：{problem.classes[lesson.class_id].name} 排到了班会/校本片 "
                    f"({lesson.day},{lesson.period})"
                )
            if (lesson.day, lesson.period) in problem.locks_by_class.get(lesson.class_id, frozenset()):
                issues.append(
                    f"锁定片：{problem.classes[lesson.class_id].name} 排到了用户锁定片 "
                    f"({lesson.day},{lesson.period})"
                )
        return issues

    def _print_grids(self, problem, lessons, n: int) -> None:
        if n <= 0:
            return
        by_class: dict = defaultdict(dict)
        for lesson in lessons:
            by_class[lesson.class_id][(lesson.day, lesson.period)] = lesson

        cal = problem.calendar
        max_period = max(problem.calendar.periods_per_day)
        for shown, (cid, cinfo) in enumerate(problem.classes.items()):
            if shown >= n:
                break
            self.stdout.write(self.style.MIGRATE_HEADING(f"=== 课表：{cinfo.name} ==="))
            for p in range(max_period):
                cells = []
                for d in cal.days:
                    lesson = by_class[cid].get((d, p))
                    if lesson:
                        sname = problem.subjects[lesson.subject_id].name
                        tname = problem.teachers[lesson.teacher_id].name if lesson.teacher_id else "?"
                        cells.append(f"{sname}/{tname}")
                    else:
                        cells.append("·")
                self.stdout.write(f"  P{p + 1}: " + " | ".join(f"{c:<12}" for c in cells))
