-- =============================================================================
-- Supabase RLS 安全加固 — 针对你库里 17 张未开 RLS 的表
-- 项目: Techlife-stock-quant (wglfpwlqesjrxonfaaeb)
-- 在 Supabase Dashboard → SQL Editor 执行
--
-- 说明：
--   • service_role（Streamlit / Node API secrets）绕过 RLS，后端不受影响
--   • user_settings_racing 已有 4 条策略，本脚本不会改动
--   • 赛马业务表只开 RLS、不加公开策略 = 仅 service_role 可读写
-- =============================================================================

-- -----------------------------------------------------------------------------
-- A) 修复前诊断（应返回下面 17 张表）
-- -----------------------------------------------------------------------------
SELECT c.relname AS table_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND NOT c.relrowsecurity
ORDER BY 1;

-- -----------------------------------------------------------------------------
-- B) 对这 17 张表启用 RLS（不加 policy = anon/authenticated 全部拒绝）
-- -----------------------------------------------------------------------------
ALTER TABLE public.horse_name_mapping       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.horse_scores_cache       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.horses                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incident_llm_cache       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jockeys                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.odds_history             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.odds_schedule_config     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.past_performances        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.race_runners             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.race_runners_clean       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.race_runners_scores      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.races                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recommendation_logs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scoring_config           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_backtest_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trainers                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_betting_strategies  ENABLE ROW LEVEL SECURITY;

-- odds_collection_log 已开 RLS 但 0 条 policy，保持即可（仅 service_role）

-- -----------------------------------------------------------------------------
-- C) 序列权限（防止 authenticated INSERT 时 permission denied for sequence）
-- -----------------------------------------------------------------------------
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO anon;

-- -----------------------------------------------------------------------------
-- D) user_betting_strategies：若有 user_id 列，允许用户读写自己的策略
--    （若表结构不同，执行后看 NOTICE，可手动调整）
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'user_betting_strategies'
          AND column_name = 'user_id'
    ) THEN
        EXECUTE 'DROP POLICY IF EXISTS user_betting_strategies_select_own ON public.user_betting_strategies';
        EXECUTE 'DROP POLICY IF EXISTS user_betting_strategies_update_own ON public.user_betting_strategies';
        EXECUTE 'DROP POLICY IF EXISTS user_betting_strategies_insert_own ON public.user_betting_strategies';
        EXECUTE 'DROP POLICY IF EXISTS user_betting_strategies_delete_own ON public.user_betting_strategies';

        EXECUTE $p$
            CREATE POLICY user_betting_strategies_select_own
                ON public.user_betting_strategies FOR SELECT TO authenticated
                USING (auth.uid() = user_id)
        $p$;
        EXECUTE $p$
            CREATE POLICY user_betting_strategies_update_own
                ON public.user_betting_strategies FOR UPDATE TO authenticated
                USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id)
        $p$;
        EXECUTE $p$
            CREATE POLICY user_betting_strategies_insert_own
                ON public.user_betting_strategies FOR INSERT TO authenticated
                WITH CHECK (auth.uid() = user_id)
        $p$;
        EXECUTE $p$
            CREATE POLICY user_betting_strategies_delete_own
                ON public.user_betting_strategies FOR DELETE TO authenticated
                USING (auth.uid() = user_id)
        $p$;
        RAISE NOTICE 'user_betting_strategies: 已添加 user_id 策略';
    ELSE
        RAISE NOTICE 'user_betting_strategies: 无 user_id 列，仅 service_role 可访问';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- E) 修复后验证：应返回 0 行
-- -----------------------------------------------------------------------------
SELECT c.relname AS table_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND NOT c.relrowsecurity
ORDER BY 1;

-- -----------------------------------------------------------------------------
-- F) 序列权限检查（修正版 SQL 5）
-- -----------------------------------------------------------------------------
SELECT
    n.nspname AS schema_name,
    c.relname AS sequence_name,
    r.rolname AS grantee,
    pr.privilege_type
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_roles r ON r.rolname IN ('anon', 'authenticated')
LEFT JOIN LATERAL aclexplode(COALESCE(c.relacl, acldefault('s', c.relowner))) AS acl
    ON acl.grantee = r.oid
LEFT JOIN LATERAL (
    SELECT unnest(ARRAY['USAGE', 'SELECT', 'UPDATE']) AS privilege_type
) pr ON (
    (pr.privilege_type = 'USAGE'   AND acl.privilege_type = 'USAGE')
 OR (pr.privilege_type = 'SELECT'  AND acl.privilege_type = 'SELECT')
 OR (pr.privilege_type = 'UPDATE'  AND acl.privilege_type = 'UPDATE')
)
WHERE n.nspname = 'public'
  AND c.relkind = 'S'
ORDER BY sequence_name, grantee, privilege_type;
