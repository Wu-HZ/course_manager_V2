"""软约束目标 S1–S7，聚合为加权和 ``Maximize(Σ奖励 − Σ惩罚)``。

权重取自 :class:`~scheduler.domain.config.SchedulerConfig`，语义对齐旧引擎。
S1/S2/S3/S5 基于 ``place``（班级/课程维度）；S4/S6/S7 基于 ``busy``（教师维度）。
权重为 0 的项直接跳过，避免建无用的辅助变量。
"""
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .variables import Variables
    from ..domain import ScheduleProblem


def add_objective(model, problem: "ScheduleProblem", variables: "Variables") -> None:
    """收集全部软约束项，一次性写入模型目标。"""
    cfg = problem.config
    rewards: list = []
    penalties: list = []

    rewards += _s1_am_preference(problem, variables, cfg.s1_am_preference_weight)
    rewards += _s2_consecutive(model, problem, variables, cfg.s2_consecutive_weight)
    penalties += _s3_distribution(model, problem, variables, cfg.s3_distribution_weight)
    penalties += _s4_teacher_daily(
        model, problem, variables, cfg.s4_teacher_daily_threshold, cfg.s4_teacher_daily_weight
    )
    penalties += _s5_avoid_first(problem, variables, cfg.s5_avoid_first_weight)

    penalties += _s6_class_switch(model, problem, variables, cfg.s6_subject_switch_weight)
    penalties += _s7_subject_switch(model, problem, variables, cfg.s7_same_class_subject_switch_weight)

    if rewards or penalties:
        model.Maximize(sum(rewards) - sum(penalties))


# ---- 基于 place 的软约束 ----

def _s1_am_preference(problem, variables, w: int) -> list:
    """S1：上午优先的课排在上午，奖励。"""
    if not w:
        return []
    cal = problem.calendar
    return [
        pl * w
        for (c, s, d, p), pl in variables.place.items()
        if problem.subjects[s].is_am_preferred and cal.is_am(d, p)
    ]


def _s2_consecutive(model, problem, variables, w: int) -> list:
    """S2：允许连堂的课相邻排列，奖励（跳过禁排边界）。"""
    if not w:
        return []
    cal = problem.calendar
    forbidden = set(cal.consecutive_forbidden_pairs)
    place_of: dict[tuple[int, int], dict] = defaultdict(dict)
    for (c, s, d, p), pl in variables.place.items():
        place_of[(c, s)][(d, p)] = pl

    terms = []
    for (c, s), slots in place_of.items():
        if not problem.subjects[s].allow_consecutive:
            continue
        for d in cal.days:
            for p in range(cal.periods_per_day[d] - 1):
                if (p, p + 1) in forbidden:
                    continue
                a = slots.get((d, p))
                b = slots.get((d, p + 1))
                if a is not None and b is not None:
                    both = model.NewBoolVar(f"s2_c{c}_s{s}_d{d}_p{p}")
                    model.AddBoolAnd([a, b]).OnlyEnforceIf(both)
                    model.AddBoolOr([a.Not(), b.Not()]).OnlyEnforceIf(both.Not())
                    terms.append(both * w)
    return terms


def _s3_distribution(model, problem, variables, w: int) -> list:
    """S3：同课同班同天超过 1 节，惩罚超出部分。"""
    if not w:
        return []
    by_csd: dict[tuple[int, int, int], list] = defaultdict(list)
    for (c, s, d, p), pl in variables.place.items():
        by_csd[(c, s, d)].append(pl)

    terms = []
    for (c, s, d), lits in by_csd.items():
        if len(lits) > 1:
            excess = model.NewIntVar(0, len(lits), f"s3_c{c}_s{s}_d{d}")
            model.Add(excess >= sum(lits) - 1)
            terms.append(excess * w)
    return terms


def _s5_avoid_first(problem, variables, w: int) -> list:
    """S5：标记避免第一节的课排在第 0 节，惩罚。"""
    if not w:
        return []
    return [
        pl * w
        for (c, s, d, p), pl in variables.place.items()
        if p == 0 and problem.subjects[s].avoid_first_period
    ]


# ---- 基于 busy 的软约束 ----

def _s4_teacher_daily(model, problem, variables, threshold: int, w: int) -> list:
    """S4：教师单日课时超过阈值，惩罚超出部分。"""
    if not w:
        return []
    by_td: dict[tuple[int, int], list] = defaultdict(list)
    for (c, s, t, d, p), b in variables.busy.items():
        by_td[(t, d)].append(b)

    terms = []
    for (t, d), lits in by_td.items():
        if len(lits) > threshold:
            excess = model.NewIntVar(0, len(lits), f"s4_t{t}_d{d}")
            model.Add(excess >= sum(lits) - threshold)
            terms.append(excess * w)
    return terms


def _s6_class_switch(model, problem, variables, w: int) -> list:
    """S6：教师连续两节在不同班级则惩罚（同班连续不罚）。

    紧凑建模——利用 H3（教师每节至多 1 班）：换班 = consec（连续两节都有课）
    − stay（同班连续）。只用线性数量的辅助变量，避免枚举班级两两组合（原 O(班²)）。
    """
    if not w:
        return []
    occ_by_tdp: dict[tuple[int, int, int], list] = defaultdict(list)      # (t,d,p)->[busy]（教师该节所有课）
    teach_by_tcdp: dict[tuple[int, int, int, int], list] = defaultdict(list)  # (t,c,d,p)->[busy]（在该班该节）
    for (c, s, t, d, p), b in variables.busy.items():
        occ_by_tdp[(t, d, p)].append(b)
        teach_by_tcdp[(t, c, d, p)].append(b)
    classes_at: dict[tuple[int, int, int], set] = defaultdict(set)
    for (t, c, d, p) in teach_by_tcdp:
        classes_at[(t, d, p)].add(c)

    terms = []
    for (t, d, p), occ_p in occ_by_tdp.items():
        occ_p1 = occ_by_tdp.get((t, d, p + 1))
        if not occ_p1:
            continue
        # consec = (教师 p 有课) AND (教师 p+1 有课)；occ 是 sum，∈{0,1}（H3）
        consec = model.NewBoolVar(f"s6consec_t{t}_d{d}_p{p}")
        model.Add(consec <= sum(occ_p))
        model.Add(consec <= sum(occ_p1))
        model.Add(consec >= sum(occ_p) + sum(occ_p1) - 1)
        # stay = 连续两节在同一个班（共同候选班逐个 AND）
        stay = []
        for c in classes_at[(t, d, p)] & classes_at[(t, d, p + 1)]:
            sc = model.NewBoolVar(f"s6stay_t{t}_c{c}_d{d}_p{p}")
            tp = teach_by_tcdp[(t, c, d, p)]
            tp1 = teach_by_tcdp[(t, c, d, p + 1)]
            model.Add(sc <= sum(tp))
            model.Add(sc <= sum(tp1))
            model.Add(sc >= sum(tp) + sum(tp1) - 1)
            stay.append(sc)
        # 换班 = consec − stay ∈ {0,1}
        terms.append((consec - sum(stay)) * w)
    return terms


def _s7_subject_switch(model, problem, variables, w: int) -> list:
    """S7：教师连续两节在同一班级但上不同科目则惩罚（同科连堂不罚）。

    紧凑建模——利用 H2（每班每节至多 1 课）：换科 = consec_c（在该班连续两节都有课）
    − same（同科连续）。线性数量辅助变量，避免枚举科目两两组合（原 O(科²)）。
    """
    if not w:
        return []
    teach_by_tcdp: dict[tuple[int, int, int, int], list] = defaultdict(list)  # (t,c,d,p)->[busy]
    subj_busy: dict[tuple[int, int, int, int], dict] = defaultdict(dict)       # (t,c,d,p)->{s: busy}
    for (c, s, t, d, p), b in variables.busy.items():
        teach_by_tcdp[(t, c, d, p)].append(b)
        subj_busy[(t, c, d, p)][s] = b

    terms = []
    for (t, c, d, p), tp in teach_by_tcdp.items():
        tp1 = teach_by_tcdp.get((t, c, d, p + 1))
        if not tp1:
            continue
        # consec_c = 教师在该班连续两节都有课
        consec_c = model.NewBoolVar(f"s7consec_t{t}_c{c}_d{d}_p{p}")
        model.Add(consec_c <= sum(tp))
        model.Add(consec_c <= sum(tp1))
        model.Add(consec_c >= sum(tp) + sum(tp1) - 1)
        # same = 连续两节是同一门课（共同科目逐个 AND）
        same = []
        smap = subj_busy[(t, c, d, p)]
        smap1 = subj_busy[(t, c, d, p + 1)]
        for s in smap.keys() & smap1.keys():
            ss = model.NewBoolVar(f"s7same_t{t}_c{c}_d{d}_p{p}_s{s}")
            model.Add(ss <= smap[s])
            model.Add(ss <= smap1[s])
            model.Add(ss >= smap[s] + smap1[s] - 1)
            same.append(ss)
        # 换科 = consec_c − same ∈ {0,1}
        terms.append((consec_c - sum(same)) * w)
    return terms
