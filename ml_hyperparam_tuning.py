"""
LightGBM walk-forward hyperparameter search (Optuna).
Objective: maximize Top1-in-actual-top-3 rate on a backtest date range.
"""

from __future__ import annotations

import copy
from typing import Callable, Dict, Optional, Tuple


ProgressCallback = Callable[[str, float], None]


def evaluate_lgb_top1_in_top3_rate(
    start_date: str,
    end_date: str,
    ml_config_override: Dict,
    max_race_days: Optional[int] = 15,
    progress_callback: Optional[ProgressCallback] = None,
) -> Tuple[float, int, int]:
    """
    Walk-forward evaluation for LightGBM with temporary ml_config override.

    Returns:
        (top1_in_top3_rate_percent, hit_count, race_count)
    """
    from scoring_engine import get_ml_config, update_ml_config

    import racing_app as ra

    if not ra.LGB_AVAILABLE:
        return 0.0, 0, 0

    saved_config = copy.deepcopy(get_ml_config())
    try:
        update_ml_config(ml_config_override)

        all_performances = ra.get_performances_batch(start_date, end_date)
        if not all_performances:
            return 0.0, 0, 0

        incident_llm_map = ra._build_incident_llm_map(
            [p.get("incident", "") for p in all_performances if p.get("incident")]
        )
        horse_cache = ra.build_horse_performances_cache(all_performances)
        races = ra.get_races_from_performances(all_performances)
        if not races:
            return 0.0, 0, 0

        races_by_date: Dict[str, list] = {}
        for race in races:
            races_by_date.setdefault(race["race_date"], []).append(race)

        sorted_dates = sorted(races_by_date.keys())
        if max_race_days and len(sorted_dates) > max_race_days:
            step = max(1, len(sorted_dates) // max_race_days)
            sorted_dates = sorted_dates[::step][-max_race_days:]

        top1_hits = 0
        race_count = 0
        n_dates = len(sorted_dates)

        for idx, current_date in enumerate(sorted_dates):
            if progress_callback:
                progress_callback(
                    f"评估赛日 {current_date} ({idx + 1}/{n_dates})",
                    (idx + 1) / max(n_dates, 1),
                )

            train_X, train_y, train_w = ra.prepare_training_data_by_date(
                current_date,
                all_performances,
                horse_cache,
                incident_llm_map=incident_llm_map,
            )
            if train_X is None or len(train_X) < 50:
                continue

            tune_key = f"tune_{current_date}_{hash(frozenset(ml_config_override.items()))}"
            model = ra.get_or_train_model(
                train_X,
                train_y,
                "lightgbm",
                tune_key,
                sample_weight=train_w,
                use_cache=False,
            )
            if model is None:
                continue

            for race in races_by_date[current_date]:
                race_date = race["race_date"]
                venue = race["venue"]
                race_no = race["race_no"]

                runners_data = [
                    p
                    for p in all_performances
                    if p.get("race_date") == race_date
                    and p.get("venue") == venue
                    and p.get("race_no") == race_no
                ]
                if len(runners_data) < 4:
                    continue

                ml_probs = ra.get_model_predictions(
                    race_date,
                    venue,
                    race_no,
                    runners_data,
                    "lightgbm",
                    model,
                    incident_llm_map=incident_llm_map,
                )
                if not ml_probs:
                    continue

                ranked = sorted(
                    zip(ml_probs, runners_data),
                    key=lambda item: item[0],
                    reverse=True,
                )
                predicted_1st_id = ranked[0][1].get("horse_id")
                actual_top3 = {
                    p.get("horse_id")
                    for p in runners_data
                    if p.get("position") in (1, 2, 3) and p.get("horse_id")
                }
                if not predicted_1st_id or not actual_top3:
                    continue

                race_count += 1
                if predicted_1st_id in actual_top3:
                    top1_hits += 1

        rate = (top1_hits / race_count * 100.0) if race_count > 0 else 0.0
        return rate, top1_hits, race_count
    finally:
        update_ml_config(saved_config)


def run_optuna_lgb_search(
    start_date: str,
    end_date: str,
    n_trials: int = 20,
    max_race_days: int = 15,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict:
    """
    Search LightGBM hyperparameters with Optuna (maximize Top1-in-top-3 rate).
    """
    try:
        import optuna
    except ImportError:
        return {
            "success": False,
            "error": "未安装 optuna，请运行: pip install optuna>=3.0.0",
        }

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    trial_progress: Dict[str, int] = {"current": 0}

    def objective(trial: "optuna.Trial") -> float:
        trial_progress["current"] += 1
        if progress_callback:
            progress_callback(
                f"Optuna 试验 {trial_progress['current']}/{n_trials}",
                trial_progress["current"] / max(n_trials, 1),
            )

        cfg = {
            "recent_games": trial.suggest_int("recent_games", 30, 80, step=10),
            "lgb_n_estimators": trial.suggest_int("lgb_n_estimators", 40, 120, step=20),
            "lgb_max_depth": trial.suggest_int("lgb_max_depth", 3, 6),
            "lgb_learning_rate": trial.suggest_float("lgb_learning_rate", 0.05, 0.15),
            "lgb_num_leaves": trial.suggest_int("lgb_num_leaves", 8, 32, step=4),
            "lgb_subsample": trial.suggest_float("lgb_subsample", 0.6, 0.9),
            "lgb_colsample_bytree": trial.suggest_float("lgb_colsample_bytree", 0.6, 0.9),
        }
        rate, hits, races = evaluate_lgb_top1_in_top3_rate(
            start_date,
            end_date,
            cfg,
            max_race_days=max_race_days,
        )
        trial.set_user_attr("hits", hits)
        trial.set_user_attr("races", races)
        return rate

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    if not study.best_trial:
        return {"success": False, "error": "搜参未完成或无有效试验"}

    best = study.best_trial
    return {
        "success": True,
        "best_rate": float(best.value or 0.0),
        "best_hits": int(best.user_attrs.get("hits", 0)),
        "best_races": int(best.user_attrs.get("races", 0)),
        "best_params": dict(best.params),
        "n_trials": n_trials,
        "start_date": start_date,
        "end_date": end_date,
        "max_race_days": max_race_days,
    }
