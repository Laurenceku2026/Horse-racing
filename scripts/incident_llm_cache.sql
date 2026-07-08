-- Incident LLM 永久缓存表（规则为主 + LLM 叠加，热路径只读）
-- 在 Supabase SQL Editor 中执行

CREATE TABLE IF NOT EXISTS incident_llm_cache (
    id BIGSERIAL PRIMARY KEY,
    incident_text_hash TEXT NOT NULL UNIQUE,
    incident_text TEXT NOT NULL,
    race_date DATE,
    venue TEXT,
    race_no INTEGER,
    horse_no TEXT,
    horse_id TEXT,
    horse_name TEXT,
    rule_score NUMERIC(6, 2) DEFAULT 0,
    llm_impact_score NUMERIC(6, 2) DEFAULT 0,
    incident_type TEXT DEFAULT 'normal',
    suggestion TEXT DEFAULT '',
    model_version TEXT DEFAULT 'deepseek-chat',
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incident_llm_cache_hash
    ON incident_llm_cache (incident_text_hash);

CREATE INDEX IF NOT EXISTS idx_incident_llm_cache_race_date
    ON incident_llm_cache (race_date DESC);

COMMENT ON TABLE incident_llm_cache IS
    '竞赛事件 LLM 分析缓存；combined = clamp(rule_score + 0.5 * llm_impact_score, -20, 20)';
