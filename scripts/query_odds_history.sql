-- ============================================================
-- odds_history 诊断查询（Supabase SQL Editor）
-- ============================================================

-- 1) 某赛日各场是否有 WIN/PLA 快照（例：2026-07-01）
SELECT
    race_date,
    venue,
    race_no,
    odds_type,
    COUNT(*) AS row_count,
    COUNT(DISTINCT horse_no) AS horses,
    COUNT(DISTINCT minutes_before_race) AS time_points,
    MIN(recorded_at) AS first_recorded,
    MAX(recorded_at) AS last_recorded
FROM odds_history
WHERE race_date = '2026-07-01'
  AND odds_type IN ('WIN', 'PLA')
  AND horse_no IS NOT NULL
  AND horse_no <> 0
GROUP BY race_date, venue, race_no, odds_type
ORDER BY venue, race_no, odds_type;

-- 2) 单场明细（改 date / venue / race_no）
SELECT
    race_date,
    venue,
    race_no,
    horse_no,
    odds_type,
    odds_value,
    minutes_before_race,
    recorded_at
FROM odds_history
WHERE race_date = '2026-07-01'
  AND venue = 'ST'
  AND race_no = 1
  AND odds_type IN ('WIN', 'PLA')
ORDER BY odds_type, horse_no, minutes_before_race DESC;

-- 3) 最近有哪些赛日采到过 WIN 快照
SELECT
    race_date,
    venue,
    COUNT(*) AS win_rows,
    COUNT(DISTINCT race_no) AS races,
    MAX(recorded_at) AS last_collect
FROM odds_history
WHERE odds_type = 'WIN'
  AND horse_no IS NOT NULL
  AND horse_no <> 0
GROUP BY race_date, venue
ORDER BY race_date DESC
LIMIT 30;

-- 4) 库里实际有哪些 venue 代码
SELECT DISTINCT venue
FROM odds_history
ORDER BY venue;

-- 5) 全库 WIN/PLA 快照总量（确认表是否为空）
SELECT
    odds_type,
    COUNT(*) AS total_rows,
    MIN(race_date) AS earliest_race,
    MAX(race_date) AS latest_race
FROM odds_history
WHERE odds_type IN ('WIN', 'PLA')
  AND horse_no IS NOT NULL
  AND horse_no <> 0
GROUP BY odds_type;
