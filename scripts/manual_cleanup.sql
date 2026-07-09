-- 统一数据行数清理（Supabase SQL Editor 执行一次）
-- 各业务数据表超过 keep 行（默认 20000）时删除最旧记录，保留最新数据
-- Node 采集后 / Streamlit 数据更新 均调用 manual_cleanup()
--
-- ⚠️ 本文件内容粘贴到 Supabase → SQL Editor → Run
-- ⚠️ 不要粘贴 curl 命令；curl 只在 Windows PowerShell / 终端里运行
--
-- 安装完成后，可在 SQL Editor 验证：
--   SELECT public.manual_cleanup(20000);

CREATE OR REPLACE FUNCTION public.trim_table_rows(
    p_table text,
    p_keep integer DEFAULT 20000,
    p_order_sql text DEFAULT 'id ASC'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total bigint;
    v_delete bigint;
    v_deleted bigint;
BEGIN
    IF p_keep IS NULL OR p_keep < 1 THEN
        p_keep := 20000;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = p_table
    ) THEN
        RETURN jsonb_build_object(
            'table', p_table,
            'skipped', true,
            'reason', 'table_not_found'
        );
    END IF;

    EXECUTE format('SELECT count(*)::bigint FROM public.%I', p_table)
        INTO v_total;

    IF v_total <= p_keep THEN
        RETURN jsonb_build_object(
            'table', p_table,
            'total', v_total,
            'deleted', 0,
            'kept', v_total
        );
    END IF;

    v_delete := v_total - p_keep;

    EXECUTE format(
        'WITH doomed AS (
            SELECT ctid
            FROM public.%I
            ORDER BY %s
            LIMIT $1
        )
        DELETE FROM public.%I AS t
        USING doomed AS d
        WHERE t.ctid = d.ctid',
        p_table,
        p_order_sql,
        p_table
    )
    USING v_delete;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    RETURN jsonb_build_object(
        'table', p_table,
        'total', v_total,
        'deleted', v_deleted,
        'kept', p_keep
    );
EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'table', p_table,
            'error', SQLERRM
        );
END;
$$;


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

    -- 仅清理会持续增长的数据/缓存表；不触碰用户设置与评分配置
    -- 第三列 keep_override：NULL 表示使用 p_keep；incident_llm_cache 固定 15000
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
        'total_deleted', v_total_deleted,
        'ran_at', now(),
        'tables', v_results
    );
END;
$$;

REVOKE ALL ON FUNCTION public.trim_table_rows(text, integer, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.manual_cleanup(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.trim_table_rows(text, integer, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.manual_cleanup(integer) TO service_role;

COMMENT ON FUNCTION public.manual_cleanup(integer) IS
    'Trim append-only/cache tables; incident_llm_cache capped at 15000 rows, others use p_keep (default 20000).';


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

COMMENT ON FUNCTION public.trim_incident_llm_cache(integer) IS
    'Keep at most p_keep rows in incident_llm_cache (default 15000), deleting oldest by created_at.';

-- ========== 安装后验证（可选，单独 Run 下面这一行）==========
-- SELECT public.manual_cleanup(20000);
