-- 赔率自动采集运行日志（Supabase SQL Editor 执行一次）
CREATE TABLE IF NOT EXISTS odds_collection_log (
    id BIGSERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL DEFAULT 'auto',
    races_checked INT NOT NULL DEFAULT 0,
    races_collected INT NOT NULL DEFAULT 0,
    races_skipped INT NOT NULL DEFAULT 0,
    rows_saved INT NOT NULL DEFAULT 0,
    rows_skipped INT NOT NULL DEFAULT 0,
    duration_ms INT,
    error_message TEXT,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_odds_collection_log_run_at
    ON odds_collection_log (run_at DESC);

-- 允许 service role 读写（按需调整 RLS）
ALTER TABLE odds_collection_log ENABLE ROW LEVEL SECURITY;
