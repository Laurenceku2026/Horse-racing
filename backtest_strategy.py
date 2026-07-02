"""
策略回测系统
- 基于 AI 胜率 + 市场赔率计算 EV，仅在 EV > 门槛时模拟投注
- 与智能投注共用 BettingStrategyEngine 的概率/EV 逻辑
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def normalize_horse_no(horse_no) -> str:
    if horse_no is None:
        return ""
    return str(horse_no).strip()


def format_horse_label(name: str, horse_no=None) -> str:
    from betting_strategy_engine import format_horse_display
    return format_horse_display(name or "", horse_no)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def attach_win_odds_to_runners(
    runners: List[Dict],
    odds_by_horse: Optional[Dict] = None,
) -> List[Dict]:
    """为每匹马附加 odds_win；优先使用 odds_history 快照，否则用赛果表 odds。"""
    odds_by_horse = odds_by_horse or {}
    enriched = []
    for runner in runners:
        row = dict(runner)
        hno = normalize_horse_no(row.get("horse_no"))
        snapshot_odds = _safe_float(odds_by_horse.get(hno) or odds_by_horse.get(row.get("horse_no")), 0)
        fallback_odds = _safe_float(row.get("odds_win", row.get("odds")), 0)
        row["odds_win"] = snapshot_odds if snapshot_odds > 0 else fallback_odds
        enriched.append(row)
    return enriched


def fetch_win_odds_snapshot(race_date: str, venue: str, race_no: int) -> Dict[str, float]:
    """从 odds_history 获取独赢赔率（每匹马取最近一条）。"""
    try:
        from supabase import create_client
        import streamlit as st

        supabase_url = st.secrets.get("SUPABASE_STOCK_URL", "")
        supabase_key = st.secrets.get("SUPABASE_STOCK_SECRET_KEY", "")
        if not supabase_url or not supabase_key:
            return {}

        supabase = create_client(supabase_url, supabase_key)
        response = (
            supabase.table("odds_history")
            .select("horse_no, odds_value, recorded_at")
            .eq("race_date", race_date)
            .eq("venue", venue)
            .eq("race_no", race_no)
            .eq("odds_type", "WIN")
            .order("recorded_at", desc=True)
            .execute()
        )
        odds_map: Dict[str, float] = {}
        for item in response.data or []:
            hno = normalize_horse_no(item.get("horse_no"))
            odds = _safe_float(item.get("odds_value"), 0)
            if hno and odds > 0 and hno not in odds_map:
                odds_map[hno] = odds
        return odds_map
    except Exception as exc:
        print(f"获取独赢赔率失败: {exc}")
        return {}


def fetch_qin_odds_snapshot(race_date: str, venue: str, race_no: int) -> Dict[str, float]:
    """从 odds_history 获取连赢赔率；horse_id 格式为 '3+7'。"""
    try:
        from supabase import create_client
        import streamlit as st

        supabase_url = st.secrets.get("SUPABASE_STOCK_URL", "")
        supabase_key = st.secrets.get("SUPABASE_STOCK_SECRET_KEY", "")
        if not supabase_url or not supabase_key:
            return {}

        supabase = create_client(supabase_url, supabase_key)
        response = (
            supabase.table("odds_history")
            .select("horse_id, combination, odds_value, recorded_at")
            .eq("race_date", race_date)
            .eq("venue", venue)
            .eq("race_no", race_no)
            .eq("odds_type", "QIN")
            .order("recorded_at", desc=True)
            .execute()
        )
        odds_map: Dict[str, float] = {}
        for item in response.data or []:
            combo_raw = item.get("combination") or item.get("horse_id") or ""
            combo_raw = str(combo_raw).replace("+", ",").replace(" ", "")
            parts = [p for p in combo_raw.split(",") if p]
            if len(parts) != 2:
                continue
            odds = _safe_float(item.get("odds_value"), 0)
            if odds <= 0:
                continue
            a, b = normalize_horse_no(parts[0]), normalize_horse_no(parts[1])
            key = f"{a},{b}"
            if key not in odds_map:
                odds_map[key] = odds
            rev = f"{b},{a}"
            if rev not in odds_map:
                odds_map[rev] = odds
        return odds_map
    except Exception as exc:
        print(f"获取连赢赔率失败: {exc}")
        return {}


def estimate_qin_odds_from_win(sorted_runners: List[Dict]) -> Dict[str, float]:
    """与智能投注 UI 一致：用独赢赔率估算连赢组合赔率。"""
    odds_map: Dict[str, float] = {}
    n = len(sorted_runners)
    for i in range(n):
        for j in range(i + 1, n):
            h1, h2 = sorted_runners[i], sorted_runners[j]
            o1 = _safe_float(h1.get("odds_win"), 0)
            o2 = _safe_float(h2.get("odds_win"), 0)
            if o1 <= 0 or o2 <= 0:
                continue
            est = (o1 * o2) / 2
            a = normalize_horse_no(h1.get("horse_no"))
            b = normalize_horse_no(h2.get("horse_no"))
            if not a or not b:
                continue
            odds_map[f"{a},{b}"] = est
            odds_map[f"{b},{a}"] = est
    return odds_map


def build_qin_odds_map(
    race_date: str,
    venue: str,
    race_no: int,
    sorted_runners: List[Dict],
) -> Tuple[Dict[str, float], bool]:
    """返回 (连赢赔率表, 是否为估算赔率)。"""
    db_odds = fetch_qin_odds_snapshot(race_date, venue, race_no)
    if db_odds:
        return db_odds, False
    return estimate_qin_odds_from_win(sorted_runners), True


def get_actual_winner_horse_no(runners_data: List[Dict]) -> Optional[str]:
    for row in runners_data:
        if row.get("position") == 1:
            hno = normalize_horse_no(row.get("horse_no"))
            return hno or None
    return None


def get_actual_qin_combo(runners_data: List[Dict]) -> Optional[str]:
    top2 = []
    for row in sorted(runners_data, key=lambda x: x.get("position", 99)):
        if row.get("position") in (1, 2):
            hno = normalize_horse_no(row.get("horse_no"))
            if hno:
                top2.append(hno)
        if len(top2) == 2:
            break
    if len(top2) == 2:
        return f"{top2[0]},{top2[1]}"
    return None


@dataclass
class BacktestResult:
    race_date: str
    venue: str
    race_no: int
    recommendation_type: str
    recommendation_content: str
    odds: float
    ev_calculated: float
    actual_hit: bool
    actual_return: float
    profit: float
    model_name: str = ""
    odds_estimated: bool = False


@dataclass
class BacktestDiagnostics:
    total_races: int = 0
    bet_races: int = 0
    skipped_no_runners: int = 0
    skipped_no_odds: int = 0
    skipped_ev_below: int = 0
    skipped_no_result: int = 0


@dataclass
class BacktestSummary:
    total_bets: int = 0
    hit_count: int = 0
    win_rate: float = 0.0
    total_stake: float = 0.0
    total_return: float = 0.0
    roi: float = 0.0
    avg_odds: float = 0.0
    avg_ev: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    model_name: str = ""
    diagnostics: BacktestDiagnostics = field(default_factory=BacktestDiagnostics)
    details: List[BacktestResult] = field(default_factory=list)


class StrategyBacktester:
    """策略回测器：单场 EV 决策 + 汇总统计。"""

    def __init__(self):
        self.daily_returns: List[float] = []

    def _get_engine(self):
        from betting_strategy_engine import BettingStrategyEngine
        return BettingStrategyEngine()

    def calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.025) -> float:
        if len(returns) < 2:
            return 0.0
        returns_array = np.array(returns)
        daily_rf = (1 + risk_free_rate) ** (1 / 365) - 1
        excess_returns = returns_array - daily_rf
        if np.std(excess_returns) == 0:
            return 0.0
        sharpe = (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(252)
        return round(float(sharpe), 2)

    def calculate_max_drawdown(self, values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        peak = values[0]
        max_dd = 0.0
        for value in values:
            if value > peak:
                peak = value
            if peak > 0:
                dd = (peak - value) / peak * 100
                max_dd = max(max_dd, dd)
        return round(max_dd, 2)

    def _sorted_runners_from_ml(self, runners: List[Dict]) -> List[Dict]:
        return sorted(
            runners,
            key=lambda x: float(x.get("win_probability") or 0),
            reverse=True,
        )

    def evaluate_win_race(
        self,
        race_date: str,
        venue: str,
        race_no: int,
        runners: List[Dict],
        min_ev_threshold: float,
        stake_per_bet: float = 100,
        model_name: str = "",
        odds_by_horse: Optional[Dict] = None,
    ) -> Tuple[Optional[BacktestResult], str]:
        if not runners:
            return None, "no_runners"

        enriched = attach_win_odds_to_runners(runners, odds_by_horse)
        sorted_runners = self._sorted_runners_from_ml(enriched)
        if not any(_safe_float(r.get("odds_win"), 0) > 0 for r in sorted_runners):
            return None, "no_odds"

        engine = self._get_engine()
        scores = [
            float(r.get("overall_score") or float(r.get("win_probability") or 0) * 100)
            for r in sorted_runners
        ]
        horse_names = [r.get("horse_name", "") for r in sorted_runners]
        horse_nos = [r.get("horse_no") for r in sorted_runners]
        odds_win = [_safe_float(r.get("odds_win"), 0) for r in sorted_runners]
        probs = engine.get_horse_probabilities(scores, horse_names, horse_nos=horse_nos)

        best_ev = -999.0
        best_idx = -1
        for idx, (prob, odds) in enumerate(zip(probs, odds_win)):
            if odds <= 0:
                continue
            ev = engine.calculate_ev(prob.win_prob / 100, odds)
            if ev > best_ev:
                best_ev = ev
                best_idx = idx

        if best_idx < 0 or best_ev <= min_ev_threshold:
            return None, "ev_below"

        chosen = sorted_runners[best_idx]
        chosen_prob = probs[best_idx]
        chosen_odds = odds_win[best_idx]
        chosen_hno = normalize_horse_no(chosen.get("horse_no"))

        actual_winner = get_actual_winner_horse_no(runners)
        if not actual_winner:
            return None, "no_result"

        actual_hit = chosen_hno == actual_winner
        if actual_hit:
            actual_return = stake_per_bet * chosen_odds
            profit = actual_return - stake_per_bet
        else:
            actual_return = 0.0
            profit = -stake_per_bet

        label = format_horse_label(chosen.get("horse_name", ""), chosen.get("horse_no"))
        return BacktestResult(
            race_date=race_date,
            venue=venue,
            race_no=race_no,
            recommendation_type="WIN",
            recommendation_content=label,
            odds=chosen_odds,
            ev_calculated=best_ev,
            actual_hit=actual_hit,
            actual_return=actual_return,
            profit=profit,
            model_name=model_name,
        ), "bet"

    def evaluate_qin_race(
        self,
        race_date: str,
        venue: str,
        race_no: int,
        runners: List[Dict],
        min_ev_threshold: float,
        stake_per_bet: float = 100,
        model_name: str = "",
        odds_by_horse: Optional[Dict] = None,
    ) -> Tuple[Optional[BacktestResult], str, bool]:
        if len(runners) < 2:
            return None, "no_runners", False

        enriched = attach_win_odds_to_runners(runners, odds_by_horse)
        sorted_runners = self._sorted_runners_from_ml(enriched)
        if not any(_safe_float(r.get("odds_win"), 0) > 0 for r in sorted_runners):
            return None, "no_odds", False

        odds_qin, estimated = build_qin_odds_map(race_date, venue, race_no, sorted_runners)
        if not odds_qin:
            return None, "no_odds", estimated

        engine = self._get_engine()
        scores = [
            float(r.get("overall_score") or float(r.get("win_probability") or 0) * 100)
            for r in sorted_runners
        ]
        horse_names = [r.get("horse_name", "") for r in sorted_runners]
        horse_nos = [r.get("horse_no") for r in sorted_runners]
        probs = engine.get_horse_probabilities(scores, horse_names, horse_nos=horse_nos)

        best_ev = -999.0
        best_combo = None
        best_odds = 0.0
        best_labels = ("", "")
        n = len(probs)
        for i in range(n):
            for j in range(i + 1, n):
                hno_i = normalize_horse_no(probs[i].horse_no)
                hno_j = normalize_horse_no(probs[j].horse_no)
                combo_key = f"{hno_i},{hno_j}"
                odds = odds_qin.get(combo_key) or odds_qin.get(f"{hno_j},{hno_i}")
                if not odds or odds <= 0:
                    continue
                combo_prob = (probs[i].win_prob / 100) * (probs[j].win_prob / 100) * 2
                ev = engine.calculate_ev(combo_prob, odds)
                if ev > best_ev:
                    best_ev = ev
                    best_combo = combo_key
                    best_odds = odds
                    best_labels = (probs[i].horse_name, probs[j].horse_name)

        if not best_combo or best_ev <= min_ev_threshold:
            return None, "ev_below", estimated

        actual_combo = get_actual_qin_combo(runners)
        if not actual_combo:
            return None, "no_result", estimated

        parts = best_combo.split(",")
        rev = f"{parts[1]},{parts[0]}" if len(parts) == 2 else best_combo
        actual_hit = actual_combo == best_combo or actual_combo == rev
        if actual_hit:
            actual_return = stake_per_bet * best_odds
            profit = actual_return - stake_per_bet
        else:
            actual_return = 0.0
            profit = -stake_per_bet

        content = f"{best_labels[0]} + {best_labels[1]}"
        return BacktestResult(
            race_date=race_date,
            venue=venue,
            race_no=race_no,
            recommendation_type="QIN",
            recommendation_content=content,
            odds=best_odds,
            ev_calculated=best_ev,
            actual_hit=actual_hit,
            actual_return=actual_return,
            profit=profit,
            model_name=model_name,
            odds_estimated=estimated,
        ), "bet", estimated

    def build_summary(
        self,
        results: List[BacktestResult],
        diagnostics: BacktestDiagnostics,
        stake_per_bet: float,
        model_name: str = "",
    ) -> BacktestSummary:
        if not results:
            return BacktestSummary(
                model_name=model_name,
                diagnostics=diagnostics,
            )

        profits = [r.profit for r in results]
        total_bets = len(results)
        hit_count = sum(1 for r in results if r.actual_hit)
        total_stake = total_bets * stake_per_bet
        total_return = sum(r.actual_return for r in results)
        roi = (total_return - total_stake) / total_stake * 100 if total_stake > 0 else 0.0
        cumulative = np.cumsum(profits)

        return BacktestSummary(
            total_bets=total_bets,
            hit_count=hit_count,
            win_rate=round(hit_count / total_bets * 100, 2),
            total_stake=round(total_stake, 2),
            total_return=round(total_return, 2),
            roi=round(roi, 2),
            avg_odds=round(float(np.mean([r.odds for r in results])), 2),
            avg_ev=round(float(np.mean([r.ev_calculated for r in results])), 4),
            sharpe_ratio=self.calculate_sharpe_ratio(profits),
            max_drawdown=self.calculate_max_drawdown(cumulative.tolist()),
            model_name=model_name,
            diagnostics=diagnostics,
            details=results,
        )
