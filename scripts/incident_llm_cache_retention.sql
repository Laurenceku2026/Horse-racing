-- incident_llm_cache 保留上限 15000 条（超出删最旧）
-- 在 Supabase SQL Editor 执行一次（已装过 manual_cleanup 也需执行本文件以更新函数）

CREATE OR REPLACE FUNCTION public.trim_incident_llm_cache(p_keep integer DEFAULT 15000)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF p_keep IS NULL OR p_keep < 1 THEN
        p_keep := 15000;
    END IF;
    RETURN public.trim_table_rows('incident_llm_cache', p_keep, 'created_at ASC, id ASC');
END;
$$;

REVOKE ALL ON FUNCTION public.trim_incident_llm_cache(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.trim_incident_llm_cache(integer) TO service_role;

-- 更新 manual_cleanup：incident_llm_cache 固定 15000，其它表仍用 p_keep（默认 20000）
CREATE OR REPLACE FUNCTION public.manual_cleanup(p_keep integer DEFAULT 20000)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_results jsonb := '[]'::jsonb;
    v_row jsonb;
    v_total_deleted bigint := 0;
    v_cfg record;
BEGIN
    IF p_keep IS NULL OR p_keep < 1 THEN
        p_keep := 20000;
    END IF;

    FOR v_cfg IN
        SELECT *
        FROM (
            VALUES
                ('past_performances_v2', 'race_date ASC, id ASC', NULL::integer),
                ('odds_history', 'recorded_at ASC, id ASC', NULL::integer),
                ('odds_collection_log', 'run_at ASC, id ASC', NULL::integer),
                ('horse_scores_cache', 'id ASC', NULL::integer),
                ('race_scores_cache', 'race_date ASC, id ASC', NULL::integer),
                ('race_runners_clean', 'race_date ASC, id ASC', NULL::integer),
                ('race_runners_scores', 'race_date ASC, id ASC', NULL::integer),
                ('races', 'race_date ASC, id ASC', NULL::integer),
                ('race_runners', 'runner_id ASC', NULL::integer),
                ('horses', 'hkjc_id ASC', NULL::integer),
                ('horses_v2', 'horse_id ASC', NULL::integer),
                ('incident_llm_cache', 'created_at ASC, id ASC', 15000),
                ('jockeys', 'jockey_id ASC', NULL::integer),
                ('trainers', 'trainer_id ASC', NULL::integer)
        ) AS t(table_name, order_sql, keep_override)
    LOOP
        v_row := public.trim_table_rows(
            v_cfg.table_name,
            COALESCE(v_cfg.keep_override, p_keep),
            v_cfg.order_sql
        );
        v_results := v_results || jsonb_build_array(v_row);
        v_total_deleted := v_total_deleted + COALESCE((v_row ->> 'deleted')::bigint, 0);
    END LOOP;

    RETURN jsonb_build_object(
        'keep_limit', p_keep,
        'incident_llm_cache_keep', 15000,
        'total_deleted', v_total_deleted,
        'ran_at', now(),
        'tables', v_results
    );
END;
$$;

-- 验证（当前 3380 条应 deleted=0）：
-- SELECT public.trim_incident_llm_cache(15000);
-- SELECT count(*) FROM incident_llm_cache;
