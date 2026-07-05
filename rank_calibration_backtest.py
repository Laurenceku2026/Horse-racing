"""
AI rank calibration backtest — per-race tables comparing model ranking vs actual top 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Dict, List, Optional, Sequence


@dataclass
class RankCalibrationRow:
    rank: int
    horse_no: str
    horse_name: str
    win_probability: float
    odds: float
    in_actual_top4: bool
    actual_pos_label: str = ""
    actual_horse_no: str = ""
    actual_horse_name: str = ""
    highlight_actual: bool = False


@dataclass
class RankCalibrationRace:
    race_date: str
    venue: str
    race_no: int
    ai_top1_horse_id: Optional[str] = None
    ai_top1_horse_no: str = ""
    ai_top1_in_top3: bool = False
    rows: List[RankCalibrationRow] = field(default_factory=list)


@dataclass
class RankCalibrationResult:
    model_label: str
    start_date: str
    end_date: str
    training_window_days: int = 0
    race_count: int = 0
    top1_in_top3_count: int = 0
    top1_in_top3_rate: float = 0.0
    ai_top4_cover_count: int = 0
    ai_top4_cover_rate: float = 0.0
    races: List[RankCalibrationRace] = field(default_factory=list)
    cancelled: bool = False


def _parse_odds(value) -> float:
    try:
        odds = float(value)
        return odds if odds > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _horse_label(name: str, horse_no) -> str:
    name = (name or "-").strip()
    if horse_no is not None and str(horse_no).strip():
        return f"{name}({horse_no})"
    return name


def build_rank_calibration_race(
    race_date: str,
    venue: str,
    race_no: int,
    scored_runners: Sequence[Dict],
    runners_data: Sequence[Dict],
    *,
    name_resolver=None,
) -> Optional[RankCalibrationRace]:
    """Build one race table from scored runners and actual results."""
    if not scored_runners or not runners_data:
        return None

    resolve = name_resolver or (lambda r: r.get("horse_name") or "-")

    actual_by_pos: Dict[int, Dict] = {}
    for row in runners_data:
        pos = row.get("position")
        if isinstance(pos, int) and 1 <= pos <= 4:
            actual_by_pos[pos] = row

    actual_top4_ids = {
        row.get("horse_id")
        for row in actual_by_pos.values()
        if row.get("horse_id")
    }

    ranked = sorted(
        scored_runners,
        key=lambda x: float(x.get("win_probability") or 0),
        reverse=True,
    )
    if not ranked:
        return None

    top1 = ranked[0]
    ai_top1_id = top1.get("horse_id")
    ai_top1_no = top1.get("horse_no")
    ai_top1_in_top3 = False
    for pos in (1, 2, 3):
        act = actual_by_pos.get(pos)
        if act and act.get("horse_id") == ai_top1_id:
            ai_top1_in_top3 = True
            break

    table_rows: List[RankCalibrationRow] = []
    for idx, runner in enumerate(ranked, start=1):
        hid = runner.get("horse_id")
        horse_no = runner.get("horse_no")
        odds = _parse_odds(runner.get("odds_win") or runner.get("odds"))
        if odds <= 0:
            for raw in runners_data:
                if raw.get("horse_id") == hid:
                    odds = _parse_odds(raw.get("odds"))
                    break

        actual_pos_label = ""
        actual_horse_no = ""
        actual_horse_name = ""
        highlight_actual = False
        if idx <= 4:
            act = actual_by_pos.get(idx)
            if act:
                actual_pos_label = str(idx)
                actual_horse_no = str(act.get("horse_no") or "")
                actual_horse_name = _horse_label(
                    resolve(act),
                    act.get("horse_no"),
                )
                if idx <= 3 and act.get("horse_id") == ai_top1_id:
                    highlight_actual = True

        table_rows.append(
            RankCalibrationRow(
                rank=idx,
                horse_no=str(horse_no) if horse_no is not None else "",
                horse_name=_horse_label(resolve(runner), horse_no),
                win_probability=float(runner.get("win_probability") or 0),
                odds=odds,
                in_actual_top4=hid in actual_top4_ids if hid else False,
                actual_pos_label=actual_pos_label,
                actual_horse_no=actual_horse_no,
                actual_horse_name=actual_horse_name,
                highlight_actual=highlight_actual,
            )
        )

    return RankCalibrationRace(
        race_date=race_date,
        venue=venue,
        race_no=race_no,
        ai_top1_horse_id=ai_top1_id,
        ai_top1_horse_no=str(ai_top1_no) if ai_top1_no is not None else "",
        ai_top1_in_top3=ai_top1_in_top3,
        rows=table_rows,
    )


def summarize_rank_calibration(races: List[RankCalibrationRace]) -> Dict[str, float]:
    race_count = len(races)
    if not race_count:
        return {
            "race_count": 0,
            "top1_in_top3_count": 0,
            "top1_in_top3_rate": 0.0,
            "ai_top4_cover_count": 0,
            "ai_top4_cover_rate": 0.0,
        }

    top1_hits = sum(1 for r in races if r.ai_top1_in_top3)
    cover_hits = 0
    for race in races:
        actual_top4_nos = {
            row.actual_horse_no for row in race.rows[:4] if row.actual_horse_no
        }
        ai_top4_nos = {row.horse_no for row in race.rows[:4] if row.horse_no}
        if actual_top4_nos and actual_top4_nos.issubset(ai_top4_nos):
            cover_hits += 1

    return {
        "race_count": race_count,
        "top1_in_top3_count": top1_hits,
        "top1_in_top3_rate": top1_hits / race_count * 100.0,
        "ai_top4_cover_count": cover_hits,
        "ai_top4_cover_rate": cover_hits / race_count * 100.0,
    }


def render_rank_calibration_html(
    result: RankCalibrationResult,
    labels: Dict[str, str],
) -> str:
    """Render spreadsheet-style HTML tables grouped by date."""
    css = """
    <style>
    .rc-wrap { font-size: 0.92rem; margin-bottom: 1.5rem; }
    .rc-date { font-size: 1.05rem; font-weight: 700; margin: 1rem 0 0.35rem 0; }
    .rc-race { font-weight: 600; margin: 0.6rem 0 0.25rem 0; color: #374151; }
    table.rc-table {
        border-collapse: collapse; width: 100%; max-width: 960px;
        margin-bottom: 0.75rem;
    }
    table.rc-table th, table.rc-table td {
        border: 1px solid #d1d5db; padding: 4px 8px; text-align: center;
    }
    table.rc-table th { background: #f3f4f6; font-weight: 600; }
    table.rc-table td.name { text-align: left; white-space: nowrap; }
    table.rc-table td.num { text-align: right; }
    .rc-hit-top4 { background-color: #fff3cd !important; }
    .rc-hit-top1 { background-color: #ffc107 !important; font-weight: 700; }
    .rc-legend { font-size: 0.85rem; color: #6b7280; margin-bottom: 0.75rem; }
    .rc-legend span { display: inline-block; padding: 2px 8px; margin-right: 10px; border: 1px solid #d1d5db; }
    </style>
    """
    parts = [css, '<div class="rc-wrap">']
    parts.append(
        f'<div class="rc-legend">'
        f'<span class="rc-hit-top4">{escape(labels["legend_top4"])}</span>'
        f'<span class="rc-hit-top1">{escape(labels["legend_top1"])}</span>'
        f'</div>'
    )

    current_date = None
    for race in result.races:
        if race.race_date != current_date:
            current_date = race.race_date
            parts.append(f'<div class="rc-date">{escape(race.race_date)}</div>')

        parts.append(
            f'<div class="rc-race">{escape(labels["race_label"].format(race_no=race.race_no))}'
            f' · {escape(race.venue)}</div>'
        )
        parts.append("<table class='rc-table'><thead><tr>")
        for key in (
            "col_rank",
            "col_horse_no",
            "col_horse_name",
            "col_win_prob",
            "col_odds",
            "col_actual_top4",
        ):
            parts.append(f"<th>{escape(labels[key])}</th>")
        parts.append("</tr></thead><tbody>")

        for row in race.rows:
            left_cls = "rc-hit-top4" if row.in_actual_top4 else ""
            actual_cls = "rc-hit-top1" if row.highlight_actual else ""
            prob_pct = row.win_probability * 100 if row.win_probability <= 1 else row.win_probability
            odds_txt = f"{row.odds:.1f}" if row.odds > 0 else "-"
            actual_txt = row.actual_horse_no or ""
            parts.append("<tr>")
            parts.append(f'<td class="{left_cls}">{row.rank}</td>')
            parts.append(f'<td class="{left_cls}">{escape(row.horse_no)}</td>')
            parts.append(f'<td class="name {left_cls}">{escape(row.horse_name)}</td>')
            parts.append(f'<td class="num {left_cls}">{prob_pct:.1f}%</td>')
            parts.append(f'<td class="num {left_cls}">{odds_txt}</td>')
            parts.append(f'<td class="{actual_cls}">{escape(actual_txt)}</td>')
            parts.append("</tr>")

        parts.append("</tbody></table>")

    parts.append("</div>")
    return "".join(parts)
