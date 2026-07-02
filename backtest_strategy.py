"""Backward-compatible re-exports. Prefer strategy_backtest_engine."""

from strategy_backtest_engine import (  # noqa: F401
    BacktestDiagnostics,
    BacktestResult,
    BacktestSummary,
    StrategyBacktester,
    attach_win_odds_to_runners,
    build_qin_odds_map,
    fetch_qin_odds_snapshot,
    fetch_win_odds_snapshot,
    format_horse_label,
    get_actual_qin_combo,
    get_actual_winner_horse_no,
    normalize_horse_no,
)
