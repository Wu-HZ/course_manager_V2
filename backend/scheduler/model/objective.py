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

    # S6/S7 共享 busy 索引与 teach 辅助变量
    busy_idx = _index_busy(variables)
    teach = _build_teach(model, busy_idx)
    penalties += _s6_class_switch(model, problem, teach, cfg.s6_subject_switch_weight)
    penalties += _s7_subject_switch(model, problem, busy_idx, cfg.s7_same_class_subject_switch_weight)

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

def _index_busy(variables) -> dict:
    """busy 按 (t, c, d, p) -> {subject_id: var} 索引，供 S6/S7 复用。"""
    idx: dict[tuple[int, int, int, int], dict] = defaultdict(dict)
    for (c, s, t, d, p), b in variables.busy.items():
        idx[(t, c, d, p)][s] = b
    return idx


def _build_teach(model, busy_idx) -> dict:
    """teach[(t,c,d,p)] = 教师 t 在班 c 的该片是否有课 = OR_s busy。"""
    teach: dict[tuple[int, int, int, int], object] = {}
    for key, s_map in busy_idx.items():
        vars_ = list(s_map.values())
        if len(vars_) == 1:
            teach[key] = vars_[0]  # 单科时 busy 本身即布尔
        else:
            tv = model.NewBoolVar(f"occ_t{key[0]}_c{key[1]}_d{key[2]}_p{key[3]}")
            model.AddMaxEquality(tv, vars_)
            teach[key] = tv
    return teach


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


def _s6_class_switch(model, problem, teach, w: int) -> list:
    """S6：教师连续两节在不同班级，惩罚（同班连续不罚）。"""
    if not w:
        return []
    by_tdp: dict[tuple[int, int, int], list] = defaultdict(list)
    for (t, c, d, p), v in teach.items():
        by_tdp[(t, d, p)].append((c, v))

    terms = []
    for (t, d, p), at_p in by_tdp.items():
        at_p1 = by_tdp.get((t, d, p + 1))
        if not at_p1:
            continue
        for c1, v1 in at_p:
            for c2, v2 in at_p1:
                if c1 == c2:
                    continue
                both = model.NewBoolVar(f"s6_t{t}_d{d}_p{p}_c{c1}_c{c2}")
                model.AddBoolAnd([v1, v2]).OnlyEnforceIf(both)
                model.AddBoolOr([v1.Not(), v2.Not()]).OnlyEnforceIf(both.Not())
                terms.append(both * w)
    return terms


def _s7_subject_switch(model, problem, busy_idx, w: int) -> list:
    """S7：教师连续两节在同一班级但上不同科目，惩罚（同科连堂不罚）。"""
    if not w:
        return []
    terms = []
    for (t, c, d, p), s_map in busy_idx.items():
        s_map_next = busy_idx.get((t, c, d, p + 1))
        if not s_map_next:
            continue
        for s1, v1 in s_map.items():
            for s2, v2 in s_map_next.items():
                if s1 == s2:
                    continue
                both = model.NewBoolVar(f"s7_t{t}_c{c}_d{d}_p{p}_s{s1}_s{s2}")
                model.AddBoolAnd([v1, v2]).OnlyEnforceIf(both)
                model.AddBoolOr([v1.Not(), v2.Not()]).OnlyEnforceIf(both.Not())
                terms.append(both * w)
    return terms
