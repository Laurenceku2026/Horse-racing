-- 为 incident_llm_cache 增加 DeepSeek Token 统计列（已有表时执行）
ALTER TABLE incident_llm_cache
    ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS completion_tokens INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0;

COMMENT ON COLUMN incident_llm_cache.total_tokens IS 'DeepSeek API 返回的 total_tokens（写入时记录）';
