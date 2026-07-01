"""新联合排课引擎冒烟测试命令（第二阶段：全硬约束 + 软约束目标 + 诊断）。

用法： ``python manage.py schedule_v2 [--time-limit 60] [--workers 8] [--show 1]``

对真实数据：要么给出可行解（并打印目标值、自检全部硬约束），要么判定无解
并给出**最小冲突集**（求解器证明的原因）。
"""
from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand

from scheduler.service import run


class Command(BaseCommand):
    help = "运行新联合排课引擎（第二阶段：全硬约束 + 软约束 + unsat core 诊断）并自检"

    def add_arguments(self, parser):
        parser.add_argument("--time-limit", type=int, default=60, help="求解时限（秒）")
        parser.add_argument("--workers", type=int, default=8, help="求解器线程数")
        parser.add_argument("--show", type=int, default=1, help="打印前 N 个班的课表网格")
        parser.add_argument("--save", action="store_true", help="把结果落库到 ScheduleResult")

    def handle(self, *args, **opts):
        from core.models import School
        school = School.objects.first()
        if not school:
            self.stderr.write("没有学校数据，请先创建学校。")
            return
        out = run(
            school,
            time_limit_seconds=opts["time_limit"],
            num_workers=opts["workers"],
            save=opts["save"],
        )
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
        obj = "—" if r.objective_value is None else f"{r.objective_value:.0f}"
        self.stdout.write(
            f"状态 {r.status} · 变量 {r.num_vars} · 约束 {r.num_constraints} · "
            f"耗时 {r.solve_time_ms}ms · 目标值 {obj} · 排定课时 {len(r.lessons)}"
        )

        if r.status not in ("OPTIMAL", "FEASIBLE"):
            self.stdout.write(self.style.WARNING("无可行解 / 未知。"))
            if out["conflicts"]:
                self.stdout.write(self.style.ERROR("诊断："))
                for msg in out["conflicts"]:
                    self.stdout.write("  " + msg)
            else:
                self.stdout.write("（未能定位到可放松的约束，可能是结构性时间冲突或超时。）")
            return

        issues = self._verify(problem, r.lessons)
        if issues:
            self.stdout.write(self.style.ERROR(f"自检发现 {len(issues)} 处违反约束："))
            for msg in issues[:40]:
                self.stdout.write("  ✗ " + msg)
        else:
            self.stdout.write(self.style.SUCCESS("自检通过：全部硬约束(H1–H15/带班数/预占片)满足。"))

        if out.get("saved"):
            sr = out["saved"]
            self.stdout.write(self.style.SUCCESS(
                f"已落库：ScheduleResult #{sr.id} · 条目 {sr.entries.count()} 条（预锁定 + 求解）"
            ))

        self._print_grids(problem, r.lessons, opts["show"])

    # ------------------------------------------------------------------ #
    def _verify(self, problem, lessons) -> list[str]:
        """用解出的课表直接反验全部硬约束。"""
        cal = problem.calendar
        cfg = problem.config
        issues: list[str] = []

        def cname(c):
            return problem.classes[c].name

        def sname(s):
            return problem.subjects[s].name

        def tname(t):
            return problem.teachers[t].name if t is not None else "?"

        # H1 周课时
        per_cs: dict = defaultdict(int)
        for L in lessons:
            per_cs[(L.class_id, L.subject_id)] += 1
        for d in problem.demands:
            got = per_cs.get((d.class_id, d.subject_id), 0)
            if got != d.hours_to_place:
                issues.append(f"H1 周课时：{cname(d.class_id)}/{sname(d.subject_id)} 排 {got} 应 {d.hours_to_place}")

        # H2 班级互斥 / H8 单日 / 预占片
        class_slot: dict = defaultdict(int)
        cs_day: dict = defaultdict(int)
        for L in lessons:
            class_slot[(L.class_id, L.day, L.period)] += 1
            cs_day[(L.class_id, L.subject_id, L.day)] += 1
            if cal.is_reserved(L.day, L.period):
                issues.append(f"预占片：{cname(L.class_id)} 排到班会/校本片 ({L.day},{L.period})")
            if (L.day, L.period) in problem.locks_by_class.get(L.class_id, frozenset()):
                issues.append(f"锁定片：{cname(L.class_id)} 排到用户锁定片 ({L.day},{L.period})")
        for (c, dd, pp), n in class_slot.items():
            if n > 1:
                issues.append(f"H2 班级互斥：{cname(c)} 在 ({dd},{pp}) 有 {n} 门课")
        for (c, s, dd), n in cs_day.items():
            limit = problem.subjects[s].max_daily_limit
            if n > limit:
                issues.append(f"H8 单日上限：{cname(c)}/{sname(s)} 第{dd}天 {n} 节 > {limit}")

        # H3 教师互斥 / H11 同班单日 / H10 课时 / 带班数 / H15 主课数
        teacher_slot: dict = defaultdict(int)
        tcd: dict = defaultdict(int)
        teacher_hours: dict = defaultdict(int)
        st_classes: dict = defaultdict(set)
        t_main: dict = defaultdict(set)
        # 锁定条目也占用教师时间片（H3 互斥检查须计入）
        for le in problem.locked_entries:
            if le.teacher_id is not None:
                teacher_slot[(le.teacher_id, le.day, le.period)] += 1
                tcd[(le.teacher_id, le.class_id, le.day)] += 1
                teacher_hours[le.teacher_id] += 1
        for L in lessons:
            if L.teacher_id is None:
                continue
            teacher_slot[(L.teacher_id, L.day, L.period)] += 1
            tcd[(L.teacher_id, L.class_id, L.day)] += 1
            teacher_hours[L.teacher_id] += 1
            st_classes[(L.subject_id, L.teacher_id)].add(L.class_id)
            if problem.subjects[L.subject_id].is_main_subject:
                t_main[L.teacher_id].add(L.subject_id)
        for (t, dd, pp), n in teacher_slot.items():
            if n > 1:
                issues.append(f"H3 教师互斥：{tname(t)} 在 ({dd},{pp}) 上 {n} 节")
        for (t, c, dd), n in tcd.items():
            if n > cfg.h11_teacher_class_daily_max:
                issues.append(f"H11 同班单日：{tname(t)}→{cname(c)} 第{dd}天 {n} > {cfg.h11_teacher_class_daily_max}")
        for t, teacher in problem.teachers.items():
            total = teacher_hours.get(t, 0) + problem.teacher_locked_hours.get(t, 0)
            if teacher.max_weekly_hours is not None and total > teacher.max_weekly_hours:
                issues.append(f"H10 课时上限：{teacher.name} {total} > {teacher.max_weekly_hours}")
            if teacher.min_weekly_hours is not None and total < teacher.min_weekly_hours:
                issues.append(f"H10 课时下限：{teacher.name} {total} < {teacher.min_weekly_hours}")
        for (s, t), classes in st_classes.items():
            cap = problem.subjects[s].max_teacher_classes
            if len(classes) > cap:
                issues.append(f"带班数：{tname(t)} 教「{sname(s)}」{len(classes)} 个班 > {cap}")
        for t, mains in t_main.items():
            if len(mains) > cfg.h15_teacher_max_main_subjects:
                issues.append(f"H15 主课数：{tname(t)} {len(mains)} 门主课 > {cfg.h15_teacher_max_main_subjects}")

        # H4 禁排日 / H13 禁排时段
        for L in lessons:
            if L.teacher_id is None:
                continue
            teacher = problem.teachers[L.teacher_id]
            if teacher.day_off is not None and L.day == teacher.day_off:
                issues.append(f"H4 禁排日：{teacher.name} 在禁排日 {L.day} 被排课")
            for bday, ptype in teacher.blocked_times:
                if bday != L.day:
                    continue
                in_am = L.period < cal.am_periods
                if ptype == "all" or (ptype == "am" and in_am) or (ptype == "pm" and not in_am):
                    issues.append(f"H13 禁排时段：{teacher.name} 第{L.day}天{ptype} 被排课")

        # H5 场地容量
        loc_slot: dict = defaultdict(int)
        for L in lessons:
            lt = problem.subjects[L.subject_id].location_type
            if lt != "NORMAL":
                loc_slot[(lt, L.day, L.period)] += 1
        for (lt, dd, pp), n in loc_slot.items():
            cap = problem.location_capacity.get(lt, 1)
            if n > cap:
                issues.append(f"H5 场地容量：{lt} 在 ({dd},{pp}) {n} > {cap}")

        # H9 连堂禁排（教师跨边界连续）
        occupied = set()  # (t, d, p)
        for L in lessons:
            if L.teacher_id is not None:
                occupied.add((L.teacher_id, L.day, L.period))
        for t in problem.teachers:
            for d in cal.days:
                for p1, p2 in cal.consecutive_forbidden_pairs:
                    if (t, d, p1) in occupied and (t, d, p2) in occupied:
                        issues.append(f"H9 连堂禁排：{tname(t)} 第{d}天跨({p1},{p2})连续上课")

        # H14 班主任主课
        if cfg.h14_homeroom_main_subject:
            main_by_class_teacher = defaultdict(int)
            for L in lessons:
                if L.teacher_id is not None and problem.subjects[L.subject_id].is_main_subject:
                    main_by_class_teacher[(L.class_id, L.teacher_id)] += 1
            for c, cls in problem.classes.items():
                t = cls.homeroom_teacher_id
                if t is None:
                    continue
                if main_by_class_teacher.get((c, t), 0) < 1:
                    issues.append(f"H14 班主任主课：{cls.name} 班主任未担任任何主课")

        return issues

    # ------------------------------------------------------------------ #
    def _print_grids(self, problem, lessons, n: int) -> None:
        if n <= 0:
            return
        cal = problem.calendar
        by_class: dict = defaultdict(dict)
        # 预锁定(班会/校本/用户锁定)用 [] 标记——这些时段并非空闲。
        for le in problem.locked_entries:
            sname = problem.subjects[le.subject_id].name
            tname = problem.teachers[le.teacher_id].name if le.teacher_id is not None else "—"
            by_class[le.class_id][(le.day, le.period)] = f"[{sname}/{tname}]"
        # 求解出的普通课
        for L in lessons:
            sname = problem.subjects[L.subject_id].name
            tname = problem.teachers[L.teacher_id].name if L.teacher_id is not None else "?"
            by_class[L.class_id][(L.day, L.period)] = f"{sname}/{tname}"

        max_period = max(problem.calendar.periods_per_day)
        for shown, (cid, cinfo) in enumerate(problem.classes.items()):
            if shown >= n:
                break
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"=== 课表：{cinfo.name}（[]=班会/校本预锁定，·=真空位，✕=该天无此节） ==="
                )
            )
            for p in range(max_period):
                cells = []
                for d in cal.days:
                    if p >= cal.periods_per_day[d]:
                        cells.append("✕")
                    else:
                        cells.append(by_class[cid].get((d, p), "·"))
                self.stdout.write(f"  P{p + 1}: " + " | ".join(f"{c:<14}" for c in cells))
