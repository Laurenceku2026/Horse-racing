"""
Top1 fixed strategy backtest engine.

- Every race: WIN + PLACE on model rank #1
- Optional: Double Trio (R6+R7), Triple Trio (R5-R7), Six Up (R6-R11)
- Trio picks: rank #1 mandatory + 2 weighted-random picks from the rest (reproducible seed)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple


def resolve_day_seed(base_seed: str, race_date: str, use_date_as_seed: bool) -> int:
    if use_date_as_seed:
        digits = race_date.replace("-", "")
        if digits.isdigit():
            return int(digits) & 0xFFFFFFFF
    text = (base_seed or "7").strip()
    if text.isdigit():
        return int(text) & 0xFFFFFFFF
    return 7


def _derive_rng_seed(day_seed: int, race_date: str, race_no: int, tag: str) -> int:
    raw = f"{day_seed}|{race_date}|{race_no}|{tag}"
    return hash(raw) & 0xFFFFFFFF


def pick_trio_runners(
    ranked_runners: Sequence[Dict],
    race_date: str,
    race_no: int,
    day_seed: int,
) -> List[Dict]:
    """Top1 mandatory + 2 others sampled by win_probability without replacement."""
    if len(ranked_runners) < 3:
        return []
    top1 = ranked_runners[0]
    rest = list(ranked_runners[1:])
    rng = random.Random(_derive_rng_seed(day_seed, race_date, race_no, "trio"))
    picked: List[Dict] = []
    remaining = list(rest)
    while len(picked) < 2 and remaining:
        weights = [max(float(r.get("win_probability") or 0.01), 0.001) for r in remaining]
        idx = rng.choices(range(len(remaining)), weights=weights, k=1)[0]
        picked.append(remaining.pop(idx))
    return [top1] + picked


def _horse_ids_top3(runners_data: Sequence[Dict]) -> Set:
    ids: Set = set()
    for row in runners_data:
        pos = row.get("position")
        if pos in (1, 2, 3):
            hid = row.get("horse_id")
            if hid:
                ids.add(hid)
    return ids


def _horse_id_at_position(runners_data: Sequence[Dict], position: int) -> Optional:
    for row in runners_data:
        if row.get("position") == position:
            return row.get("horse_id")
    return None


def _position_of_horse(runners_data: Sequence[Dict], horse_id) -> Optional[int]:
    for row in runners_data:
        if row.get("horse_id") == horse_id:
            pos = row.get("position")
            if isinstance(pos, int) and pos > 0:
                return pos
    return None


def _parse_odds(value) -> float:
    try:
        odds = float(value)
        return odds if odds > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _runner_label(runner: Optional[Dict]) -> str:
    if not runner:
        return "-"
    name = runner.get("horse_name") or runner.get("horse_name_zh") or "-"
    hno = runner.get("horse_no")
    if hno is not None and str(hno).strip():
        return f"{name}({hno})"
    return str(name)


def _trio_label(runners: Sequence[Dict]) -> str:
    return " + ".join(_runner_label(r) for r in runners)


def _actual_top3_label(runners_data: Sequence[Dict]) -> str:
    ordered = sorted(
        [r for r in runners_data if r.get("position") in (1, 2, 3)],
        key=lambda x: x.get("position", 99),
    )
    return " > ".join(_runner_label(r) for r in ordered) if ordered else "-"


def trio_matches(runners_data: Sequence[Dict], trio: Sequence[Dict]) -> bool:
    pred = {r.get("horse_id") for r in trio if r.get("horse_id")}
    actual = _horse_ids_top3(runners_data)
    return len(pred) == 3 and len(actual) == 3 and pred == actual


@dataclass
class BetDetail:
    pool: str
    race_date: str
    venue: str
    race_label: str
    recommended: str
    actual: str
    hit: bool
    stake: float
    return_amount: float
    note: str = ""


@dataclass
class PoolStats:
    bets: int = 0
    hits: int = 0
    stake: float = 0.0
    return_amount: float = 0.0

    @property
    def hit_rate(self) -> float:
        return (self.hits / self.bets * 100.0) if self.bets else 0.0

    @property
    def roi(self) -> float:
        return ((self.return_amount - self.stake) / self.stake * 100.0) if self.stake else 0.0


@dataclass
class Top1FixedBacktestResult:
    model_label: str
    start_date: str
    end_date: str
    stake_per_bet: float
    random_seed: str
    use_date_as_seed: bool
    include_win_place: bool
    include_double_trio: bool
    include_triple_trio: bool
    include_six_up: bool
    race_days: int = 0
    win_stats: PoolStats = field(default_factory=PoolStats)
    place_stats: PoolStats = field(default_factory=PoolStats)
    double_trio_stats: PoolStats = field(default_factory=PoolStats)
    triple_trio_stats: PoolStats = field(default_factory=PoolStats)
    six_up_stats: PoolStats = field(default_factory=PoolStats)
    details: List[BetDetail] = field(default_factory=list)
    skipped_notes: List[str] = field(default_factory=list)
    cancelled: bool = False


def evaluate_win_place_bets(
    top1: Dict,
    runners_data: Sequence[Dict],
    stake: float,
    race_date: str,
    venue: str,
    race_no: int,
) -> Tuple[BetDetail, BetDetail]:
    horse_id = top1.get("horse_id")
    position = _position_of_horse(runners_data, horse_id)
    win_odds = _parse_odds(top1.get("odds_win") or top1.get("odds"))
    if win_odds <= 0:
        for row in runners_data:
            if row.get("horse_id") == horse_id:
                win_odds = _parse_odds(row.get("odds"))
                break
    place_odds = win_odds * 0.3 if win_odds > 0 else 0.0

    win_hit = position == 1
    place_hit = position in (1, 2, 3) if position else False
    win_return = stake * win_odds if win_hit and win_odds > 0 else (stake * 3.0 if win_hit else 0.0)
    place_return = stake * place_odds if place_hit and place_odds > 0 else (stake * 1.5 if place_hit else 0.0)

    actual_winner = next((r for r in runners_data if r.get("position") == 1), None)
    actual_label = _runner_label(actual_winner)
    race_label = f"R{race_no}"

    win_detail = BetDetail(
        pool="WIN",
        race_date=race_date,
        venue=venue,
        race_label=race_label,
        recommended=_runner_label(top1),
        actual=actual_label,
        hit=win_hit,
        stake=stake,
        return_amount=win_return,
        note=f"独赢赔率 {win_odds:.1f}" if win_odds > 0 else "独赢赔率估算",
    )
    place_detail = BetDetail(
        pool="PLA",
        race_date=race_date,
        venue=venue,
        race_label=race_label,
        recommended=_runner_label(top1),
        actual=_actual_top3_label(runners_data),
        hit=place_hit,
        stake=stake,
        return_amount=place_return,
        note=f"位置赔率估算 {place_odds:.1f}" if place_odds > 0 else "位置赔率估算",
    )
    return win_detail, place_detail


def evaluate_multi_race_pool(
    pool: str,
    race_date: str,
    venue: str,
    race_nos: Sequence[int],
    scored_by_race: Dict[int, List[Dict]],
    runners_by_race: Dict[int, Sequence[Dict]],
    day_seed: int,
    stake: float,
    *,
    six_up: bool = False,
) -> Optional[BetDetail]:
    missing = [n for n in race_nos if n not in scored_by_race or n not in runners_by_race]
    if missing:
        return None

    if six_up:
        parts_rec: List[str] = []
        parts_act: List[str] = []
        all_hit = True
        for race_no in race_nos:
            ranked = sorted(
                scored_by_race[race_no],
                key=lambda x: float(x.get("win_probability") or 0),
                reverse=True,
            )
            top1 = ranked[0]
            runners_data = runners_by_race[race_no]
            pos = _position_of_horse(runners_data, top1.get("horse_id"))
            hit_race = pos in (1, 2) if pos else False
            all_hit = all_hit and hit_race
            parts_rec.append(f"R{race_no}:{_runner_label(top1)}")
            actual = next((r for r in runners_data if r.get("position") == pos), None) if pos else None
            parts_act.append(f"R{race_no}:{_runner_label(actual) if actual else '-'}")
        return BetDetail(
            pool=pool,
            race_date=race_date,
            venue=venue,
            race_label="-" + "-".join(str(n) for n in race_nos),
            recommended=" | ".join(parts_rec),
            actual=" | ".join(parts_act),
            hit=all_hit,
            stake=stake,
            return_amount=0.0,
            note="命中率-only（暂无历史赔率）",
        )

    trio_by_race: Dict[int, List[Dict]] = {}
    for race_no in race_nos:
        ranked = sorted(
            scored_by_race[race_no],
            key=lambda x: float(x.get("win_probability") or 0),
            reverse=True,
        )
        trio = pick_trio_runners(ranked, race_date, race_no, day_seed)
        if len(trio) < 3:
            return None
        trio_by_race[race_no] = trio

    all_hit = all(
        trio_matches(runners_by_race[race_no], trio_by_race[race_no])
        for race_no in race_nos
    )
    rec = " | ".join(f"R{rn}:{_trio_label(trio_by_race[rn])}" for rn in race_nos)
    act = " | ".join(f"R{rn}:{_actual_top3_label(runners_by_race[rn])}" for rn in race_nos)
    return BetDetail(
        pool=pool,
        race_date=race_date,
        venue=venue,
        race_label="-" + "-".join(str(n) for n in race_nos),
        recommended=rec,
        actual=act,
        hit=all_hit,
        stake=stake,
        return_amount=0.0,
        note="命中率-only（暂无历史赔率）",
    )


def accumulate_pool(stats: PoolStats, detail: BetDetail) -> None:
    stats.bets += 1
    if detail.hit:
        stats.hits += 1
    stats.stake += detail.stake
    stats.return_amount += detail.return_amount


def run_top1_fixed_backtest_core(
    *,
    start_date: str,
    end_date: str,
    model_label: str,
    stake_per_bet: float,
    random_seed: str,
    use_date_as_seed: bool,
    include_win_place: bool,
    include_double_trio: bool,
    include_triple_trio: bool,
    include_six_up: bool,
    day_race_groups: Dict[Tuple[str, str], List[Dict]],
    score_day_races: Callable[[str, str, List[Dict]], Dict[int, List[Dict]]],
    should_cancel: Callable[[], bool] = lambda: False,
) -> Top1FixedBacktestResult:
    result = Top1FixedBacktestResult(
        model_label=model_label,
        start_date=start_date,
        end_date=end_date,
        stake_per_bet=stake_per_bet,
        random_seed=random_seed,
        use_date_as_seed=use_date_as_seed,
        include_win_place=include_win_place,
        include_double_trio=include_double_trio,
        include_triple_trio=include_triple_trio,
        include_six_up=include_six_up,
    )

    sorted_days = sorted(day_race_groups.keys())
    result.race_days = len(sorted_days)

    for race_date, venue in sorted_days:
        if should_cancel():
            result.cancelled = True
            break

        day_races = day_race_groups[(race_date, venue)]
        scored_by_race = score_day_races(race_date, venue, day_races)
        if not scored_by_race:
            continue

        runners_by_race: Dict[int, Sequence[Dict]] = {}
        for race in day_races:
            race_no = int(race["race_no"])
            if race_no in scored_by_race:
                runners_by_race[race_no] = race.get("_runners_data") or []

        day_seed = resolve_day_seed(random_seed, race_date, use_date_as_seed)
        race_nos_present = set(scored_by_race.keys())
        max_race_no = max(race_nos_present) if race_nos_present else 0

        for race_no, ranked in scored_by_race.items():
            ranked_sorted = sorted(
                ranked,
                key=lambda x: float(x.get("win_probability") or 0),
                reverse=True,
            )
            if not ranked_sorted:
                continue
            top1 = ranked_sorted[0]
            runners_data = runners_by_race.get(race_no) or []
            if include_win_place and runners_data:
                win_d, pla_d = evaluate_win_place_bets(
                    top1, runners_data, stake_per_bet, race_date, venue, race_no
                )
                accumulate_pool(result.win_stats, win_d)
                accumulate_pool(result.place_stats, pla_d)
                result.details.extend([win_d, pla_d])

        if include_double_trio and max_race_no >= 7 and {6, 7}.issubset(race_nos_present):
            dt = evaluate_multi_race_pool(
                "DT",
                race_date,
                venue,
                [6, 7],
                scored_by_race,
                runners_by_race,
                day_seed,
                stake_per_bet,
            )
            if dt:
                accumulate_pool(result.double_trio_stats, dt)
                result.details.append(dt)
        elif include_double_trio:
            result.skipped_notes.append(f"{race_date} {venue}: 孖T 跳过（不足7场或无R6/R7）")

        if include_triple_trio and max_race_no >= 7 and {5, 6, 7}.issubset(race_nos_present):
            tt = evaluate_multi_race_pool(
                "TT",
                race_date,
                venue,
                [5, 6, 7],
                scored_by_race,
                runners_by_race,
                day_seed,
                stake_per_bet,
            )
            if tt:
                accumulate_pool(result.triple_trio_stats, tt)
                result.details.append(tt)
        elif include_triple_trio:
            result.skipped_notes.append(f"{race_date} {venue}: 三T 跳过（不足7场或无R5-R7）")

        if include_six_up and max_race_no >= 11 and all(n in race_nos_present for n in range(6, 12)):
            su = evaluate_multi_race_pool(
                "SixUP",
                race_date,
                venue,
                list(range(6, 12)),
                scored_by_race,
                runners_by_race,
                day_seed,
                stake_per_bet,
                six_up=True,
            )
            if su:
                accumulate_pool(result.six_up_stats, su)
                result.details.append(su)
        elif include_six_up:
            result.skipped_notes.append(f"{race_date} {venue}: 六环彩 跳过（不足11场或无R6-R11）")

    return result
