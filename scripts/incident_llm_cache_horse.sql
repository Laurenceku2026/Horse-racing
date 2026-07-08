-- 为 incident_llm_cache 增加马匹字段（已有表时执行）
ALTER TABLE incident_llm_cache
    ADD COLUMN IF NOT EXISTS horse_id TEXT,
    ADD COLUMN IF NOT EXISTS horse_name TEXT;

CREATE INDEX IF NOT EXISTS idx_incident_llm_cache_race_lookup
    ON incident_llm_cache (race_date, venue, race_no, horse_no);

COMMENT ON COLUMN incident_llm_cache.horse_name IS '写入缓存时的马名（来自 past_performances_v2）';
