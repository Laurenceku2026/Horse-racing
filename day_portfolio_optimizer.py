"""
赛日投资组合优化器
- 单场：独赢、位置、连赢、单T、三重彩
- 多场：孖宝（连续两场独赢）
- 在预算约束下按 EV 比例分配注额
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations, permutations
from typing import Dict, List, Optional, Tuple

from betting_strategy_engine import BettingStrategyEngine, format_horse_display


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_horse_no(horse_no) -> str:
    if horse_no is None:
        return ""
    return str(horse_no).strip()


@dataclass
class ScoredRunner:
    horse_no: str
    horse_name: str
    win_probability: float
    odds_win: float
    show_prob: float = 0.0
    place_prob: float = 0.0

    @property
    def label(self) -> str:
        return format_horse_display(self.horse_name, self.horse_no)


@dataclass
class RaceDayRace:
    race_date: str
    venue: str
    race_no: int
    runners: List[ScoredRunner]
    actual_top3: Optional[List[str]] = None

    def sorted_runners(self) -> List[ScoredRunner]:
        return sorted(self.runners, key=lambda r: r.win_probability, reverse=True)


@dataclass
class BetCandidate:
    pool: str
    description: str
    race_no: int
    race_no_2: Optional[int] = None
    horse_nos: Tuple[str, ...] = ()
    odds: float = 0.0
    probability: float = 0.0
    ev: float = -1.0
    odds_estimated: bool = False


@dataclass
class AllocatedBet:
    candidate: BetCandidate
    stake: float
    actual_hit: Optional[bool] = None
    actual_return: Optional[float] = None
    profit: Optional[float] = None


@dataclass
class DayPortfolioResult:
    race_date: str
    venue: str
    budget: float
    total_stake: float
    total_return: float
    roi: float
    hit_count: int
    bet_count: int
    bets: List[AllocatedBet] = field(default_factory=list)
    skipped_reason: str = ""


class DayPortfolioOptimizer:
    PLACE_ODDS_RATIO = 0.35
    TRI_FACTOR = 1.0 / 6.0
    TCE_FACTOR = 0.15
    DBL_DISCOUNT = 0.92
    TOP_N = 5

    def __init__(self, min_stake: float = 10.0, min_ev: float = 0.0, max_candidates: int = 50):
        self.min_stake = min_stake
        self.min_ev = min_ev
        self.max_candidates = max_candidates
        self.engine = BettingStrategyEngine()

    def _attach_probs(self, runners: List[ScoredRunner]) -> List[ScoredRunner]:
        if not runners:
            return []
        scores = [r.win_probability * 100 for r in runners]
        names = [r.horse_name for r in runners]
        nos = [r.horse_no for r in runners]
        probs = self.engine.get_horse_probabilities(scores, names, horse_nos=nos)
        enriched = []
        for r, p in zip(runners, probs):
            enriched.append(
                ScoredRunner(
                    horse_no=r.horse_no,
                    horse_name=r.horse_name,
                    win_probability=r.win_probability,
                    odds_win=r.odds_win,
                    show_prob=p.show_prob / 100.0,
                    place_prob=p.place_prob / 100.0,
                )
            )
        return enriched

    def _place_odds(self, win_odds: float, estimated: bool = True) -> Tuple[float, bool]:
        if win_odds <= 0:
            return 0.0, estimated
        place = max(1.3, win_odds * self.PLACE_ODDS_RATIO)
        return place, estimated

    def _generate_candidates_for_race(self, race: RaceDayRace) -> List[BetCandidate]:
        candidates: List[BetCandidate] = []
        runners = self._attach_probs(race.sorted_runners())[: self.TOP_N]
        if not runners:
            return candidates

        for r in runners:
            if r.odds_win <= 1 or r.win_probability <= 0:
                continue
            ev = self.engine.calculate_ev(r.win_probability, r.odds_win)
            if ev > self.min_ev:
                candidates.append(
                    BetCandidate(
                        pool="WIN",
                        description=f"第{race.race_no}場 獨贏 {r.label}",
                        race_no=race.race_no,
                        horse_nos=(r.horse_no,),
                        odds=r.odds_win,
                        probability=r.win_probability,
                        ev=ev,
                        odds_estimated=False,
                    )
                )

            place_odds, est = self._place_odds(r.odds_win, estimated=True)
            if place_odds > 1:
                ev_p = self.engine.calculate_ev(r.show_prob, place_odds)
                if ev_p > self.min_ev:
                    candidates.append(
                        BetCandidate(
                            pool="PLA",
                            description=f"第{race.race_no}場 位置 {r.label}",
                            race_no=race.race_no,
                            horse_nos=(r.horse_no,),
                            odds=place_odds,
                            probability=r.show_prob,
                            ev=ev_p,
                            odds_estimated=est,
                        )
                    )

        for a, b in combinations(runners, 2):
            o1, o2 = a.odds_win, b.odds_win
            if o1 <= 0 or o2 <= 0:
                continue
            qin_odds = (o1 * o2) / 2.0
            combo_prob = a.win_probability * b.win_probability * 2
            ev_q = self.engine.calculate_ev(combo_prob, qin_odds)
            if ev_q > self.min_ev:
                candidates.append(
                    BetCandidate(
                        pool="QIN",
                        description=f"第{race.race_no}場 連贏 {a.label}+{b.label}",
                        race_no=race.race_no,
                        horse_nos=tuple(sorted([a.horse_no, b.horse_no])),
                        odds=qin_odds,
                        probability=combo_prob,
                        ev=ev_q,
                        odds_estimated=True,
                    )
                )

        top_tri = runners[:4]
        for combo in combinations(top_tri, 3):
            ods = [c.odds_win for c in combo]
            if any(o <= 0 for o in ods):
                continue
            tri_odds = ods[0] * ods[1] * ods[2] * self.TRI_FACTOR
            tri_prob = combo[0].win_probability * combo[1].win_probability * combo[2].win_probability * 6
            ev_t = self.engine.calculate_ev(tri_prob, tri_odds)
            if ev_t > self.min_ev:
                nos = tuple(sorted([c.horse_no for c in combo]))
                labels = "+".join(c.label for c in combo)
                candidates.append(
                    BetCandidate(
                        pool="TRI",
                        description=f"第{race.race_no}場 單T {labels}",
                        race_no=race.race_no,
                        horse_nos=nos,
                        odds=tri_odds,
                        probability=tri_prob,
                        ev=ev_t,
                        odds_estimated=True,
                    )
                )

        top_tce = runners[:3]
        if len(top_tce) == 3:
            ods = [c.odds_win for c in top_tce]
            if all(o > 0 for o in ods):
                base = ods[0] * ods[1] * ods[2]
                tce_odds = max(base * self.TCE_FACTOR, base * 0.08)
                for perm in permutations(top_tce, 3):
                    tce_prob = perm[0].win_probability * perm[1].win_probability * perm[2].win_probability
                    ev_c = self.engine.calculate_ev(tce_prob, tce_odds)
                    if ev_c > self.min_ev:
                        labels = ">".join(p.label for p in perm)
                        candidates.append(
                            BetCandidate(
                                pool="TCE",
                                description=f"第{race.race_no}場 三重彩 {labels}",
                                race_no=race.race_no,
                                horse_nos=tuple(p.horse_no for p in perm),
                                odds=tce_odds,
                                probability=tce_prob,
                                ev=ev_c,
                                odds_estimated=True,
                            )
                        )
                        break

        return candidates

    def _generate_dbl_candidates(self, races: List[RaceDayRace]) -> List[BetCandidate]:
        candidates: List[BetCandidate] = []
        by_no = {r.race_no: r for r in races}
        sorted_nos = sorted(by_no.keys())
        for i in range(len(sorted_nos) - 1):
            n1, n2 = sorted_nos[i], sorted_nos[i + 1]
            r1, r2 = by_no[n1], by_no[n2]
            top1 = self._attach_probs(r1.sorted_runners())[:3]
            top2 = self._attach_probs(r2.sorted_runners())[:3]
            for h1 in top1:
                for h2 in top2:
                    if h1.odds_win <= 1 or h2.odds_win <= 1:
                        continue
                    dbl_odds = h1.odds_win * h2.odds_win * self.DBL_DISCOUNT
                    joint_prob = h1.win_probability * h2.win_probability
                    ev_d = self.engine.calculate_ev(joint_prob, dbl_odds)
                    if ev_d > self.min_ev:
                        candidates.append(
                            BetCandidate(
                                pool="DBL",
                                description=f"孖寶 第{n1}場{h1.label} + 第{n2}場{h2.label}",
                                race_no=n1,
                                race_no_2=n2,
                                horse_nos=(h1.horse_no, h2.horse_no),
                                odds=dbl_odds,
                                probability=joint_prob,
                                ev=ev_d,
                                odds_estimated=True,
                            )
                        )
        return candidates

    def generate_candidates(self, races: List[RaceDayRace]) -> List[BetCandidate]:
        all_c: List[BetCandidate] = []
        for race in races:
            all_c.extend(self._generate_candidates_for_race(race))
        all_c.extend(self._generate_dbl_candidates(races))
        all_c = [c for c in all_c if c.ev > self.min_ev]
        all_c.sort(key=lambda x: x.ev, reverse=True)
        return all_c[: self.max_candidates]

    def allocate(self, candidates: List[BetCandidate], budget: float) -> List[AllocatedBet]:
        if not candidates or budget < self.min_stake:
            return []
        total_ev = sum(max(c.ev, 0.001) for c in candidates)
        raw = []
        for c in candidates:
            weight = max(c.ev, 0.001) / total_ev
            stake = budget * weight
            stake = max(self.min_stake, round(stake / self.min_stake) * self.min_stake)
            raw.append(AllocatedBet(candidate=c, stake=stake))

        total = sum(b.stake for b in raw)
        if total <= 0:
            return []

        if total > budget:
            scale = budget / total
            for b in raw:
                b.stake = max(self.min_stake, round(b.stake * scale / self.min_stake) * self.min_stake)
            while sum(b.stake for b in raw) > budget and len(raw) > 1:
                raw.sort(key=lambda x: x.stake, reverse=True)
                raw[-1].stake = 0
                raw = [b for b in raw if b.stake >= self.min_stake]
        elif total < budget * 0.85 and raw:
            diff = budget - sum(b.stake for b in raw)
            add = round(diff / self.min_stake) * self.min_stake
            if add >= self.min_stake:
                raw[0].stake += add

        return [b for b in raw if b.stake >= self.min_stake]

    def optimize_day(
        self,
        race_date: str,
        venue: str,
        races: List[RaceDayRace],
        budget: float = 1000.0,
    ) -> DayPortfolioResult:
        candidates = self.generate_candidates(races)
        if not candidates:
            return DayPortfolioResult(
                race_date=race_date,
                venue=venue,
                budget=budget,
                total_stake=0,
                total_return=0,
                roi=0,
                hit_count=0,
                bet_count=0,
                skipped_reason="no_positive_ev",
            )
        bets = self.allocate(candidates, budget)
        total_stake = sum(b.stake for b in bets)
        return DayPortfolioResult(
            race_date=race_date,
            venue=venue,
            budget=budget,
            total_stake=total_stake,
            total_return=0,
            roi=0,
            hit_count=0,
            bet_count=len(bets),
            bets=bets,
        )

    def settle_bet(self, bet: AllocatedBet, races_by_no: Dict[int, RaceDayRace]) -> AllocatedBet:
        c = bet.candidate
        hit = False
        race = races_by_no.get(c.race_no)
        if not race or not race.actual_top3:
            bet.actual_hit = False
            bet.actual_return = 0.0
            bet.profit = -bet.stake
            return bet

        top3 = race.actual_top3
        winner = top3[0] if top3 else ""
        top3_set = set(top3[:3])

        if c.pool == "WIN":
            hit = c.horse_nos[0] == winner
        elif c.pool == "PLA":
            hit = c.horse_nos[0] in top3_set
        elif c.pool == "QIN":
            hit = set(c.horse_nos) == set(top3[:2])
        elif c.pool == "TRI":
            hit = set(c.horse_nos) == top3_set and len(top3) >= 3
        elif c.pool == "TCE":
            hit = len(top3) >= 3 and c.horse_nos == tuple(top3[:3])
        elif c.pool == "DBL" and c.race_no_2 is not None:
            race2 = races_by_no.get(c.race_no_2)
            if race2 and race2.actual_top3:
                hit = c.horse_nos[0] == winner and c.horse_nos[1] == race2.actual_top3[0]

        ret = bet.stake * c.odds if hit else 0.0
        bet.actual_hit = hit
        bet.actual_return = ret
        bet.profit = ret - bet.stake
        return bet

    def settle_day(self, result: DayPortfolioResult, races: List[RaceDayRace]) -> DayPortfolioResult:
        by_no = {r.race_no: r for r in races}
        hits = 0
        total_return = 0.0
        for bet in result.bets:
            self.settle_bet(bet, by_no)
            if bet.actual_hit:
                hits += 1
            total_return += bet.actual_return or 0.0
        result.hit_count = hits
        result.total_return = round(total_return, 2)
        result.total_stake = round(sum(b.stake for b in result.bets), 2)
        if result.total_stake > 0:
            result.roi = round((result.total_return - result.total_stake) / result.total_stake * 100, 2)
        return result


def build_race_day_races_from_performances(
    race_date: str,
    venue: str,
    performances: List[Dict],
    scored_by_race: Dict[int, List[Dict]],
) -> List[RaceDayRace]:
    """从赛果/出马数据构建 RaceDayRace 列表。"""
    race_nos = sorted({p.get("race_no") for p in performances if p.get("race_no") is not None})
    if not race_nos and scored_by_race:
        race_nos = sorted(scored_by_race.keys())
    races: List[RaceDayRace] = []
    for race_no in race_nos:
        if race_no is None:
            continue
        race_no = int(race_no)
        day_rows = [
            p for p in performances
            if p.get("race_date") == race_date and p.get("venue") == venue and p.get("race_no") == race_no
        ]
        actual_top3 = []
        for pos in (1, 2, 3):
            for row in day_rows:
                if row.get("position") == pos:
                    hno = normalize_horse_no(row.get("horse_no"))
                    if hno:
                        actual_top3.append(hno)
                    break

        runners: List[ScoredRunner] = []
        for row in scored_by_race.get(race_no, []):
            odds = _safe_float(row.get("odds_win", row.get("odds")), 0)
            wp = _safe_float(row.get("win_probability"), 0)
            hno = normalize_horse_no(row.get("horse_no"))
            if not hno:
                continue
            runners.append(
                ScoredRunner(
                    horse_no=hno,
                    horse_name=row.get("horse_name", ""),
                    win_probability=wp if wp <= 1 else wp / 100.0,
                    odds_win=odds,
                )
            )
        if not runners and day_rows:
            for row in day_rows:
                hno = normalize_horse_no(row.get("horse_no"))
                if not hno:
                    continue
                runners.append(
                    ScoredRunner(
                        horse_no=hno,
                        horse_name=row.get("horse_name", ""),
                        win_probability=0.05,
                        odds_win=_safe_float(row.get("odds"), 10),
                    )
                )
        races.append(
            RaceDayRace(
                race_date=race_date,
                venue=venue,
                race_no=race_no,
                runners=runners,
                actual_top3=actual_top3 if actual_top3 else None,
            )
        )
    return races
