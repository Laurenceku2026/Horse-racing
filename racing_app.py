"""
香港赛马AI分析系统 - 第1次代码
模块：基础架构 + 用户管理
包含：配置、Supabase连接、用户认证、Stripe支付、侧边栏、右上角按钮
版本：v1.0
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import re
import time
import hmac
import hashlib
import plotly.graph_objects as go
import plotly.express as px
from typing import Callable, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from supabase import create_client, Client
from bs4 import BeautifulSoup
from betting_strategy_engine import BettingStrategyEngine, get_odds_qin_from_db, get_odds_tri_from_db, get_odds_tce_from_db
from parlay_recommender import ParlayRecommender, describe_parlay_type, format_parlay_display
from top1_fixed_backtest_engine import run_top1_fixed_backtest_core, Top1FixedBacktestResult
from rank_calibration_backtest import (
    RankCalibrationResult,
    RankCalibrationRace,
    build_rank_calibration_race,
    render_rank_calibration_html,
    summarize_rank_calibration,
)
from pwa_setup import inject_pwa_head, render_pwa_install_hint
# ==================== 从 scoring_engine 导入 ====================
SCORING_ENGINE_OK = False
try:
    from scoring_engine import (
        # 核心评分函数
        calculate_basic_score,
        calculate_race_score,
        calculate_odds_score,
        calculate_status_score,
        calculate_overall_score,
        # 状态因子函数
        calculate_age_score,
        calculate_weight_change_score,
        calculate_incident_score,
        calculate_burst_score,
        # 辅助函数
        softmax_probabilities,
        get_horses_performances_batch as se_get_horses_performances_batch,
        get_horse_past_performances_v2_optimized,
        get_horse_weight_comfort_range_from_cache,
        score_runners_for_prediction,
        load_horse_birth_years,
        # 配置加载
        get_scoring_config,
        # 旧版兼容
        normalize_odds,
    )
    SCORING_ENGINE_OK = True
    print("scoring_engine loaded")
except ImportError as e:
    print(f"scoring_engine import failed: {e}")
# ==================== 页面配置 ====================
st.set_page_config(
    page_title="Equi-AI 智马",
    page_icon="static/pwa/icon-192.png",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_pwa_head()

# ==================== 自定义CSS ====================
st.markdown("""
<style>
    .main-header {
        text-align: center;
        margin-bottom: 1rem;
    }
    .sidebar-user-info {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .stButton button {
        border-radius: 0.5rem;
        transition: all 0.2s;
    }
    .stDataFrame {
        font-size: 0.9rem;
    }
    .stMetric {
        text-align: center;
    }
    .race-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .signal-S { color: #ff4b4b; font-weight: bold; }
    .signal-A { color: #ff6b6b; font-weight: bold; }
    .signal-B { color: #ffaa00; font-weight: bold; }
    .signal-C { color: #ff8800; font-weight: bold; }
    .signal-D { color: #888888; font-weight: bold; }
    /* 主页三大功能导航：加大字体，方便点击 */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        gap: 0.75rem;
        justify-content: center;
        flex-wrap: wrap;
    }
    div[data-testid="stRadio"] label {
        background-color: #eef2ff;
        border: 2px solid #c7d2fe;
        border-radius: 0.75rem;
        padding: 0.85rem 1.5rem !important;
        min-width: 9rem;
        justify-content: center;
    }
    div[data-testid="stRadio"] label p {
        font-size: 1.35rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] label[data-checked="true"] {
        background-color: #4f46e5;
        border-color: #4f46e5;
    }
    div[data-testid="stRadio"] label[data-checked="true"] p {
        color: #ffffff !important;
    }
    /* 智能投注：日期模式 radio 保持简洁（非首个 radio） */
    div[data-testid="stRadio"]:not(:first-of-type) label {
        background-color: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0.15rem 0.5rem !important;
        min-width: auto !important;
    }
    div[data-testid="stRadio"]:not(:first-of-type) label p {
        font-size: 0.85rem !important;
        font-weight: 500 !important;
    }
    div[data-testid="stRadio"]:not(:first-of-type) label[data-checked="true"] {
        background-color: transparent !important;
        border: none !important;
    }
    div[data-testid="stRadio"]:not(:first-of-type) label[data-checked="true"] p {
        color: #4f46e5 !important;
    }

    /* ========== 手机 / 窄屏：放宽主区域，减少两侧留白 ========== */
    @media screen and (max-width: 768px) {
        .stAppViewContainer .main .block-container,
        section.main > div.block-container,
        [data-testid="stMain"] > div {
            max-width: 100% !important;
            padding-left: max(0.65rem, env(safe-area-inset-left)) !important;
            padding-right: max(0.65rem, env(safe-area-inset-right)) !important;
        }
        .main-header h1,
        .auth-title {
            font-size: 1.65rem !important;
            line-height: 1.35 !important;
        }
        div[data-testid="stForm"] {
            width: 100% !important;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input {
            font-size: 16px !important;
            min-height: 2.75rem !important;
        }
        .stButton > button,
        div[data-testid="stFormSubmitButton"] button {
            min-height: 2.75rem !important;
            font-size: 1rem !important;
        }
        div[data-testid="stCheckbox"] label p {
            font-size: 0.95rem !important;
        }
        div[data-testid="stRadio"] > div[role="radiogroup"] label {
            min-width: 6.5rem !important;
            padding: 0.65rem 0.85rem !important;
        }
        div[data-testid="stRadio"] > div[role="radiogroup"] label p {
            font-size: 1.05rem !important;
        }
    }

    /* 登录 / 注册：统一卡片宽度，居中 */
    .auth-header-wrap {
        text-align: center;
        margin: 0 0 0.75rem 0;
    }
    .auth-title {
        width: 100%;
        text-align: center !important;
        margin: 0 auto !important;
    }
    div[data-testid="stMarkdownContainer"]:has(.auth-header-wrap) {
        width: 100% !important;
    }
    .auth-header-wrap,
    body:has(.auth-header-wrap) [data-testid="stElementContainer"]:has(.auth-header-wrap),
    body:has(.auth-header-wrap) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]),
    body:has(.auth-header-wrap) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]) ~ [data-testid="stElementContainer"] {
        max-width: min(440px, calc(100vw - 2rem));
        width: 100%;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    body:has(.auth-header-wrap) [data-testid="stMain"] [data-testid="stVerticalBlock"] {
        align-items: center !important;
    }
    body:has(.auth-header-wrap) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]) ~ [data-testid="stElementContainer"] .stButton > button {
        width: 100%;
    }
    @media screen and (min-width: 769px) {
        .auth-header-wrap {
            max-width: 440px;
        }
    }
    @media screen and (max-width: 768px) {
        /* 未登录页：隐藏侧边栏（不影响已登录页面的展开按钮） */
        body.auth-mobile-login [data-testid="stSidebar"],
        body.auth-mobile-login [data-testid="stSidebarCollapsedControl"],
        body.auth-mobile-login [data-testid="collapsedControl"],
        body.auth-mobile-login #equi-mobile-sidebar-btn,
        body.auth-mobile-login #equi-sidebar-expand-hint {
            display: none !important;
        }
        body.auth-mobile-login section.main {
            width: 100% !important;
            max-width: 100% !important;
        }
        body.auth-mobile-login section.main > div.block-container {
            padding-top: 0.75rem !important;
            padding-left: max(1rem, env(safe-area-inset-left)) !important;
            padding-right: max(1rem, env(safe-area-inset-right)) !important;
            max-width: 100% !important;
        }
        body.auth-mobile-login [data-testid="stVerticalBlock"] {
            width: 100% !important;
        }
        .auth-header-wrap {
            padding: 0.25rem 0 0.75rem;
        }
        .auth-title {
            font-size: 1.75rem !important;
            line-height: 1.35 !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ==================== 常量定义 ====================
FREE_TRIAL_LIMIT = 30
MAX_RECOMMENDED_HORSES = 30
ADMIN_USERNAME = "Laurence_ku"
ADMIN_PASSWORD = "Ku_product$2026"
ADMIN_EMAIL = "Techlife2027@gmail.com"
SCHEMA_NAME = "racing"  # 独立schema名称
SMART_BETTING_ML_TRAINING_WINDOW_DAYS = 730

# 默认评分权重
DEFAULT_WEIGHTS = {
    "basic": 0.30,
    "race": 0.40,
    "odds": 0.30,
    "temperature": 0.8,
    "odds_mix_ratio": 0.6
}

# 信号等级映射
SIGNAL_LEVELS = {
    "S": {"min_score": 85, "action": "强烈推荐", "position": "10-15%", "color": "#ff4b4b"},
    "A": {"min_score": 70, "action": "推荐", "position": "5-10%", "color": "#ff6b6b"},
    "B": {"min_score": 55, "action": "观望", "position": "0-5%", "color": "#ffaa00"},
    "C": {"min_score": 40, "action": "回避", "position": "0%", "color": "#ff8800"},
    "D": {"min_score": 0, "action": "不推荐", "position": "0%", "color": "#888888"}
}

# 多语言文本（繁体中文 + 英文）
TEXTS = {
    "zh": {
        # ==================== 基础 ====================
        "app_title": "香港赛马AI分析系统",
        "login": "登入",
        "register": "註冊",
        "logout": "登出",
        "email": "電郵",
        "password": "密碼",
        "confirm_password": "確認密碼",
        "login_btn": "登入",
        "register_btn": "註冊",
        "back_to_login": "返回登入",
        "welcome": "歡迎回來",
        "login_failed": "登入失敗，請檢查電郵和密碼",
        "register_success": "註冊成功！請登入",
        "email_exists": "該電郵已註冊，請直接登入",
        "not_registered_for_racing": "該電郵未註冊賽馬App，請先註冊",
        "forgot_password": "忘記密碼？",
        "remember_me": "记住我（7 天内免登录）",
        "remember_me_restoring": "正在恢复登录…",
        "pool_single_title": "**單場彩池**",
        "pool_win": "獨贏",
        "pool_place": "位置",
        "pool_qin": "連贏",
        "pool_qpl": "位置Q",
        "pool_tri": "單T",
        "pool_tce": "三重彩",
        "pool_f4": "四連環",
        "pool_qtt": "四重彩",
        "pool_multi_title": "**多場彩池**",
        "pool_double": "孖寶",
        "pool_treble": "三寶",
        "pool_double_trio": "孖T",
        "pool_trio": "三T",
        "pool_six_up": "六環彩",
        "data_source_footer": "數據: HKJC API | 支付: Stripe",
        "home_subtitle": "基於AI技術，智能預測馬匹勝率，優化投注策略",
        "horse_count": "馬匹總數",
        "race_count": "賽事總數",
        "record_count": "成績記錄總數",
        "jockey_count": "騎師總數",
        "trainer_count": "練馬師總數",
        "date_range": "數據日期範圍",
        "update_all_data": "更新所有數據",
        "horse_rating_title": "全馬基礎評分榜",
        "horse_rating_desc": "📌 基於最近 N 場歷史表現計算，分數越高代表整體實力越強。",
        "calculate_games": "計算場次",
        "display_limit": "顯示數量",
        "all_games": "全部",
        "recent_n_games_format": "最近 {n} 場",
        "rating_calculating": "正在計算馬匹評分（{scope}）...",
        "data_update": "🔄 數據更新",
        "checking_update": "正在檢查並更新數據...",
        "update_complete": "✅ 更新完成！新增 {new_races} 場賽事，{new_records} 條成績記錄",
        "update_failed": "更新失敗",
        "qin_ev_insufficient": "連贏組合 {horse1} + {horse2} 期望值不足，暫不推薦",
        "qin_recommendation": "🔗 連贏推薦",
        "qin_no_odds": "暫無連贏賠率數據",
        "qin_insufficient_horses": "馬匹數量不足，無法推薦連贏",
        "data_source": "📅 數據來源：香港賽馬會 | 更新頻率：賽日自動更新",
        "betting_pools": "🎲 彩池玩法",
        "race_table_title": "第{race_no}場 出賽馬匹",
        "run_backtest": "▶️ 運行模型對比回測",
        "select_models": "🤖 選擇要對比的模型",
        "rating_system": "評分系統",
        "lightgbm": "LightGBM",
        "xgboost": "XGBoost",
        "ensemble": "集成模型",
        
        # ==================== 侧边栏 ====================
        "about_header": "📘 關於系統",
        "about_text": """
        **香港賽馬AI分析系統** 基於AI技術提供：
        
        - 🏇 馬匹評分系統
        - 🎯 智能投注建議
        - 📊 全天優化策略
        - 📈 歷史回測驗證
        - 💡 AI勝率預測
        
        讓AI成為您的賽馬助手。
        """,
                "contact_header": "📧 聯絡我們",
                "contact_email": "✉️ 電郵: Techlife2027@gmail.com",
                "guide_header": "📖 快速指南",
                "guide_text": """
        1. 點擊[更新數據]獲取最新賽事
        2. 查看馬匹評分榜
        3. 進入智能投注頁生成建議
        4. 運行回測驗證策略
        
        💡 每次更新/生成消耗1次免費次數
        💎 升級專業版後無限使用
        """,
        
        # ==================== 订阅 ====================
        "subscription": "訂閱",
        "free_tier": "免費版",
        "pro_tier": "專業版",
        "remaining": "剩餘次數",
        "unlimited": "無限",
        "upgrade": "升級專業版",
        "monthly": "月付 HK$380/月",
        "quarterly": "季付 HK$988/季",
        "save_info": "季付更划算",
        
        # ==================== 语言 ====================
        "chinese": "中文",
        "english": "English",
        
        # ==================== 管理员 ====================
        "admin_panel": "管理員面板",
        "total_users": "總用戶數",
        "pro_users": "專業版用戶",
        "free_users": "免費版用戶",
        "user_list": "用戶列表",
        
        # ==================== 智能投注页面 ====================
        "smart_betting": "🎯 智能投注",
        "betting_settings": "⚙️ 投注設置",
        "betting_budget": "💰 投注預算 (HKD)",
        "risk_preference": "📊 風險偏好",
        "conservative": "保守",
        "standard": "標準",
        "aggressive": "進取",
        "ai_model": "🤖 AI 模型",
        "rating_weights": "📐 評分權重",
        "basic_weight": "基礎:30%",
        "race_weight": "場次:40%",
        "odds_weight": "賠率:30%",
        "temperature": "溫度:0.8",
        "odds_mix": "賠率混合比:0.6",
        "select_race_day": "📅 選擇賽日",
        "refresh_schedule": "🔄 刷新賽程",
        "no_races": "📌 未來14天暫無賽事，請點擊「刷新賽程」同步最新賽程",
        "total_races": "📋 共 {count} 場賽事",
        "single_race_analysis": "📊 單場分析",
        "select_race": "選擇場次",
        "refresh_race_data": "🔄 更新本場數據",
        "no_runners": "暫無出賽馬匹數據，請點擊「更新本場數據」同步",
        
        # ==================== AI 建议 ====================
        "ai_strategy_suggestions": "💡 AI 投注策略建議",
        "ev_description": "基於AI評分和賠率計算的期望值(EV)推薦",
        "low_risk": "🎯 低風險 - 獨贏/位置",
        "medium_risk": "🎯 中風險 - 連贏",
        "high_risk": "🎯 高風險 - 單T",
        "no_suggestions": "暫無建議",
        "qin_recommendation": "🔗 連贏推薦",
        
        # ==================== 过关推荐 ====================
        "parlay_recommendation": "🎲 過関投注推薦",
        "select_parlay_races": "選擇要過關的場次",
        "select_2_6_races": "選擇2-6場比賽（按順序）",
        "selected_races_count": "已選擇 {count} 場比賽",
        "generate_parlay": "🎲 生成過關推薦",
        "best_parlay": "🏆 最佳推薦",
        
        # ==================== 全天优化 ====================
        "full_day_optimization": "🌟 全天優化投注",
        "kelly_description": "基於凱利公式 + 風險管理，自動分配全天投注策略",
        "generate_full_day": "🚀 生成全天投注策略",
        "parlay_generation": "🔗 過關組合推薦",
        "parlay_description": "基於各場信心馬匹，推薦2串1、3串1過關組合",
        "generate_parlay_combo": "🎲 生成過關組合",
        
        # ==================== 表格列名 ====================
        "horse_name": "馬名",
        "horse_name_no": "馬名/馬號",
        "horse_no": "馬號",
        "row_index": "序號",
        "draw": "檔位",
        "actual_weight": "負磅",
        "jockey": "騎師",
        "win_odds": "獨贏",
        "place_odds": "位置",
        "win_rate": "勝率",
        "overall_score": "綜合評分",
        "ev": "期望值",
        "no_data": "暫無出賽馬匹數據",
        "realtime_odds_analysis": "📈 實時賠率分析",
        "realtime_odds_expand": "展開圖表與明細",
        "click_open": "點擊打開",
        "click_open_recommend": "點擊打開推薦",
        "collapse_section": "▼ 收起",
        "reopen_section": "▶ 展開",
        "expand_section_short": "▶ 展開",
        "realtime_odds_no_data": "本場在賠率快照庫中無 WIN/PLA 時間序列。自動採集僅在開賽前約 90 分鐘內執行；若該賽日當時未採集，歷史賽事將無走勢數據（僅出馬表中的終場賠率）。",
        "realtime_odds_latest": "最新賠率快照",
        "realtime_odds_trend": "賠率走勢（距開賽分鐘）",
        "realtime_odds_snapshots": "快照數",
        "realtime_odds_min_before": "距開賽（分鐘）",
        "realtime_odds_recorded_at": "採集時間",
        "realtime_odds_detail": "各時間點明細",
        "realtime_odds_points": "已採集 {count} 個時間點",
        "realtime_odds_opening": "早段賠率",
        "realtime_odds_latest_val": "最新賠率",
        "realtime_odds_change": "變化",
        
        # ==================== 回测页面 ====================
        "backtest": "📊 回測",
        "model_comparison": "📊 模型對比回測",
        "backtest_period": "選擇回測期間，比較不同模型的預測準確率和 ROI",
        "start_date": "開始日期",
        "end_date": "結束日期",
        "run_backtest": "▶️ 運行模型對比回測",
        "strategy_backtest": "📊 策略回測",
        "strategy_backtest_desc": "基於市場賠率的期望值(EV)模型：EV = 預測勝率 × 賠率 - 1，當 EV > 門檻時觸發投注",
        "win_strategy": "獨贏策略",
        "qin_strategy": "連贏策略",
        "min_ev_threshold": "最小期望值門檻",
        "run_strategy_backtest": "▶️ 運行策略回測",
        "backtest_result_invalid": "回測結果無效或無投注記錄",
        "disclaimer_backtest": "📌 回測結果基於歷史數據，不構成投資建議",
        "top1_fixed_backtest": "🎯 第一名固定策略回測",
        "top1_fixed_backtest_caption": "每场买模型胜率第1名的独赢+位置；可选孖T(R6-7)、三T(R5-7)、六环彩(R6-11)；Trio 为 Top1 必选 + 按胜率加权随机2匹（独立日期，默认最近两周）",
        "top1_stake_label": "每注金额 (HK$)",
        "top1_random_seed_label": "随机种子",
        "top1_use_date_seed": "以赛日日期作为随机种子",
        "top1_include_win_place": "独赢 + 位置（每场）",
        "top1_include_double_trio": "孖T（第6、7场）",
        "top1_include_triple_trio": "三T（第5、6、7场）",
        "top1_include_six_up": "六环彩（第6–11场）",
        "run_top1_fixed_backtest": "▶️ 运行第一名固定策略回测",
        "top1_backtest_running": "正在运行第一名固定策略回测 ({model})...",
        "top1_summary_title": "汇总",
        "top1_detail_title": "明细（推荐 vs 实际）",
        "top1_col_pool": "彩池",
        "top1_col_date": "赛日",
        "top1_col_venue": "场地",
        "top1_col_race": "场次",
        "top1_col_recommended": "推荐",
        "top1_col_actual": "实际",
        "top1_col_hit": "命中",
        "top1_col_stake": "投注",
        "top1_col_return": "回报",
        "top1_col_note": "备注",
        "top1_hit_rate": "命中率",
        "top1_race_days": "赛日数",
        "top1_skipped": "跳过说明",

        "rank_calib_title": "📊 AI 排名校准表",
        "rank_calib_caption": "每场按模型胜率排序列出全部出马；黄色=实际跑进前4；右侧实际前4列中，若 AI 第1名跑进实际前三则标深黄",
        "run_rank_calib": "▶️ 生成排名校准表",
        "rank_calib_running": "正在生成排名校准表 ({model})...",
        "rank_calib_top1_top3": "AI 第1名进前三",
        "rank_calib_ai_top4_cover": "AI 前4 覆盖实际前4",
        "rank_calib_race_count": "场次数",
        "rank_calib_legend_top4": "跑进实际前4",
        "rank_calib_legend_top1": "AI第1进实际前三",
        "rank_calib_col_rank": "序号",
        "rank_calib_col_horse_no": "马号",
        "rank_calib_col_horse_name": "马名",
        "rank_calib_col_win_prob": "胜率",
        "rank_calib_col_odds": "赔率",
        "rank_calib_col_actual": "实际前4",
        "rank_calib_race_label": "第{race_no}场",
        "rank_calib_train_window_label": "训练窗口（天）",
        "rank_calib_train_window_help": "ML 训练仅使用每场赛日前 N 天的历史赛事；0 = 不限（使用已拉取的全部历史）。730 与智能投注 App 一致。",
        "rank_calib_train_window_summary": "训练窗口 {days} 天",
        "rank_calib_train_window_unlimited": "训练窗口：不限",
        
        # ==================== 消息提示 ====================
        "upgrade_pro": "💎 升級專業版",
        "free_trial_used": "免費次數已用完，請升級到專業版",
        "data_updated": "數據已更新",
        "update_failed": "更新失敗",
        "syncing_schedule": "正在同步最新賽程...",
        "sync_complete": "同步完成！成功 {success} 場，失敗 {failed} 場",
        "updating_odds": "正在更新最新賠率和出賽馬匹...",
        "calculating_win_rate": "正在計算馬匹勝率（評分系統）...",
        "calculating_ml": "正在計算馬匹勝率（{model}）...",
        "betting_records": "📋 我的投注記錄",
        "disclaimer": "⚠️ 本建議基於AI模型預測，不保證實際收益。請理性投注，切勿超出預算。",
        "data_source": "📅 數據來源：香港賽馬會 | 更新頻率：賽日自動更新",
        # ==================== 补充 i18n ====================
        "fill_email_password": "請填寫電郵和密碼",
        "logging_in": "登入中...",
        "password_mismatch": "兩次輸入的密碼不一致",
        "password_min_length": "密碼長度至少6位",
        "registering": "註冊中...",
        "register_failed": "註冊失敗",
        "email_exists_login": "該郵箱已在系統中，請直接登入",
        "login_success": "登入成功",
        "wrong_email_password": "電郵或密碼錯誤",
        "create_settings_failed": "創建用戶設置失敗",
        "session_expired": "登錄已過期，請重新登錄",
        "trial_update_failed": "更新次數失敗，可能是網絡或認證問題，請刷新頁面重試",
        "contact_admin_reset_password": "請聯絡管理員重置密碼",
        "stripe_session_detected": "🔔 檢測到支付會話，請點擊按鈕完成驗證",
        "stripe_session_id": "會話ID",
        "stripe_verify_button": "✅ 手動驗證支付並升級",
        "stripe_verifying": "正在驗證...",
        "stripe_verify_success": "✅ 支付驗證成功！您已是專業版用戶",
        "stripe_user_not_found": "無法識別用戶，請重新登錄後重試",
        "stripe_payment_incomplete": "支付狀態未完成，請完成支付",
        "stripe_api_failed": "API請求失敗",
        "stripe_verify_failed": "驗證失敗",
        "stripe_payment_cancelled": "支付已取消",
        "stripe_not_configured": "Stripe密鑰未配置",
        "checkout_session_failed": "創建支付會話失敗",
        "checkout_go_stripe_monthly": "💳 前往Stripe支付（月付HK$380）",
        "checkout_go_stripe_quarterly": "💳 前往Stripe支付（季付HK$988）",
        "back": "返回",
        "paywall_trials_remaining": "🔓 您當前還有 {remaining} 次免費試用機會",
        "paywall_upgrade_hint": "💎 升級專業版後，可無限次使用所有功能",
        "paywall_feature": "功能",
        "paywall_free": "免費版",
        "paywall_pro": "專業版",
        "paywall_usage": "使用次數",
        "paywall_usage_free": "30次",
        "paywall_horse_rating": "馬匹評分榜",
        "paywall_smart_betting": "智能投注",
        "paywall_full_day": "全天優化",
        "paywall_backtest": "歷史回測",
        "admin_login_title": "管理員登入",
        "admin_username": "用戶名",
        "admin_login_btn": "登入",
        "admin_login_failed": "用戶名或密碼錯誤",
        "back_to_user_login": "返回用戶登入",
        "admin_login_help": "管理員登入",
        "back_to_user": "👤 返回",
        "exit_admin_mode": "退出管理員模式",
        "logout_help": "退出登入",
        "sidebar_expand_hint": "点击打开",
        "sidebar_open_menu": "☰ 打开菜单",
        "tier_pro": "💎 專業版",
        "tier_free": "🔒 免費版",
        "day_portfolio_title": "賽日最優組合",
        "day_portfolio_desc": "約 HK$1,000 預算 · 獨贏/位置/連贏/單T/三重彩/孖寶 · EV 比例分配（最低 HK$10/注）",
        "day_portfolio_budget_label": "賽日預算 (HK$)",
        "generate_day_portfolio": "🎯 生成賽日最優組合",
        "optimizing_day_portfolio": "正在優化賽日組合...",
        "day_portfolio_import_failed": "賽日組合優化模組載入失敗",
        "lightgbm_not_installed": "LightGBM 未安裝",
        "xgboost_not_installed": "XGBoost 未安裝",
        "no_data_fetched": "未獲取到任何數據",
        "no_races_found": "未找到任何賽事",
        "backtest_cancelled": "⚠️ 回測已被用戶取消",
        "day_portfolio_backtest_progress": "賽日組合回測 {model}: {date} {venue} ({current}/{total})",
        "day_portfolio_backtest_title": "📈 賽日組合策略回測（{model}）",
        "day_portfolio_mode_fast": "快速（每週重訓）",
        "day_portfolio_mode_std": "標準 walk-forward",
        "day_portfolio_backtest_caption": "模式：{mode} · 賽日數 {days} · 彩池：獨贏/位置/連贏/單T/三重彩/孖寶",
        "metric_day_count": "賽日數",
        "metric_total_bets": "總注數",
        "metric_hit_bets": "命中注數",
        "metric_hit_rate": "命中率",
        "metric_total_stake": "總投入",
        "metric_total_return": "總回報",
        "portfolio_bet_details": "📋 逐注明細",
        "col_race_day": "賽日",
        "col_venue": "場地",
        "col_pool": "彩池",
        "col_content": "內容",
        "col_odds": "賠率",
        "col_estimated": "估算",
        "col_yes": "是",
        "col_no": "否",
        "col_stake": "金額",
        "col_hit": "命中",
        "col_return": "回報",
        "col_profit": "盈虧",
        "no_day_portfolio_bets": "未找到符合條件的賽日組合（無正 EV 注項）",
        "day_portfolio_live_title": "💰 賽日最優組合推薦",
        "day_portfolio_live_caption": "目標預算約 HK${budget:,.0f} · 實際分配 HK${stake:,.0f} · 含獨贏/位置/連贏/單T/三重彩/孖寶",
        "col_recommendation": "推薦",
        "col_probability": "概率",
        "col_suggested_stake": "建議金額",
        "estimated_odds_footnote": "* 星號表示估算賠率",
        "fast_mode_label": "快速模式（每週重訓）",
        "fast_mode_help": "標準模式：每個賽日 walk-forward 重訓；快速模式：每週重訓一次以加快回測",
        "strategy_backtest_caption": "每日約 HK$1,000 在獨贏/位置/連贏/單T/三重彩/孖寶間 EV 優化分配 · 與智能投注共用同一優化器",
        "strategy_model_help": "策略回测使用的 ML 模型（默认 LightGBM）",
        "min_ev_help": "只投注期望值大於此門檻的建議",
        "running_day_portfolio_backtest": "正在运行赛日组合策略回测（{model}）...",
        "using_cached_backtest": "📋 使用缓存的回测结果",
        "backtest_no_bets": "回测完成但未产生任何投注（请尝试扩大日期范围或降低 EV 门槛）",
        "invalid_date_range": "開始日期不能晚於結束日期",
        "backtest_period_info": "📊 回測期間: {start} 至 {end} (共 {days} 天)",
        "running_model_backtest": "正在運行模型對比回測...",
        "calculating_full_day": "正在計算全天投注策略...",
        "no_betting_opportunities": "未找到符合條件的投注機會",
        "calculating_parlay": "正在計算過關組合...",
        "parlay_3leg_hint": "💡 3串1 需至少 3 場勝率≥20% 的信心馬；目前僅列出 2串1。",
        "no_parlay_combos": "暫無符合條件的過關組合（需正期望值 EV>0）",
        "col_race_no": "場次",
        "col_horse": "馬匹",
        "col_win_rate": "勝率",
        "col_suggested_amount": "建議注額",
        "col_expected_value": "期望值",
        "total_stake_metric": "💰 總投注額",
        "total_ev_metric": "📈 總期望值",
        "expected_roi_metric": "📊 預期ROI",
        "install_lightgbm_help": "需要安装 lightgbm 库",
        "install_xgboost_help": "需要安装 xgboost 库",
        "ml_install_hint": "请先安装 LightGBM 和/或 XGBoost 库后再运行 ML 回测",
        "model_select_help": "选择预测模型：评分系统（规则驱动）、LightGBM、XGBoost 或集成模型",
        "date_mode_label": "選擇日期模式",
        "date_mode_future": "未來賽事",
        "date_mode_history": "歷史賽事",
        "select_history_race_day": "選擇歷史賽日",
        "no_race_detail_data": "暂无详细赛事数据，请先刷新赛程",
        "no_races_available": "暂无赛事",
        "no_history_race_data": "暂无历史赛事数据",
        "no_race_detail_for_date": "该日期暂无详细赛事数据",
        "sync_failed": "同步失败",
        "prediction_error": "🔍 预测异常",
        "scoring_weights_paywall_hint": "点击下方按钮扣费后可查看和调整评分权重",
        "scoring_weights_paywall_btn": "💎 扣费查看评分权重设置",
        "nav_data_ratings": "📊 數據與評分",
        "nav_smart_betting": "🎯 智能投注",
        "nav_backtest": "📈 回測",
        "nav_label": "功能导航",
        "no_model_detail": "該模型暫無詳細預測數據",
        "no_detail_data": "暫無詳細數據",
        "update_failed_msg": "更新失败",
        "historical_mode_info": "📅 歷史測試模式：評分僅用該賽日之前往績；ML 模型訓練亦只使用所選賽日之前數據（不含當日），避免洩露未來賽果。",
        "calculating_parlay_schedule": "正在計算過關推薦...",
        "parlay_insufficient_data": "所选场次数据不足，请尝试选择更多场次",
        "parlay_select_hint": "選好場次後，點擊「🎲 生成過關推薦」查看最優 2串1 / 3串1 等組合",
        "no_qin_combos": "暫無連贏組合數據",
        "missing_win_odds_hint": "⚠️ 缺少獨贏賠率，以下 EV 僅供參考（估算連贏賠率）",
        "odds_label": "賠率",
        "odds_estimated_label": "估算",
        "select_label": "選擇",
        "qin_selected_summary": "✅ 已選擇 {count} 組，建議總投注額: HK${stake:.0f}",
        "select_combos_hint": "請勾選您感興趣的組合",
        "tri_insufficient_horses": "馬匹數量不足，無法推薦單T",
        "no_parlay_combo_found": "未找到合适的过关组合，请尝试选择更多场次或更换 AI 模型",
        "weekdays": "星期一,星期二,星期三,星期四,星期五,星期六,星期日",
        "win_place_recommend": "🎯 獨贏/位置 推薦",
        "qin_recommend_expander": "🔗 連贏 推薦",
        "tri_recommend_expander": "🎲 單T 推薦",
        "tce_recommend_expander": "🏆 三重彩 推薦",
        "win_odds_label": "獨贏賠率",
        "place_odds_label": "位置賠率",
        "expected_roi_label": "預期ROI",
        "parlay_select_races_title": "選擇要過關的場次",
        "selected_races_caption": "已选择 {count} 场比赛",
        "parlay_results_title": "📊 过关推荐结果",
        "parlay_odds_label": "賠率",
        "parlay_combined_prob": "聯合概率",
        "parlay_risk_label": "風險",
        "parlay_expected_roi": "預期ROI",
        "parlay_suggested_bet": "💡 建議投注",
        "parlay_best_title": "🏆 最佳推薦",
        "parlay_best_combo": "最佳过关组合",
        "parlay_method": "过关方式",
        "parlay_total_odds": "总赔率",
        "parlay_suggest_stake": "建议投注",
        "risk_low": "低",
        "risk_medium": "中",
        "risk_high": "高",
        "tri_est_odds": "估算賠率: {odds:.1f}倍",
        "tri_est_odds_pending": "估算賠率: 待補充",
        "tri_joint_prob": "聯合概率",
        "tri_ev": "期望值(EV)",
        "tri_ev_recommend": "✅ EV > 0.15，建議投注",
        "tri_ev_skip": "❌ EV 不足，暫不建議",
        "tri_missing_odds": "⚠️ 缺少獨贏賠率，以下為估算值",
        "tce_insufficient_horses": "馬匹數量不足，無法推薦三重彩",
        "tce_order_hint": "順序：冠軍 > 亞軍 > 季軍（必須按名次順序命中）",
        "tce_est_odds": "估算賠率: {odds:.1f}倍",
        "tce_est_odds_pending": "估算賠率: 待補充",
        "tce_joint_prob": "順序概率",
        "tce_ev": "期望值(EV)",
        "tce_ev_recommend": "✅ EV > 0.15，建議投注",
        "tce_ev_skip": "❌ EV 不足，暫不建議",
        "tce_missing_odds": "⚠️ 缺少獨贏賠率，以下為估算值",
        "sb_loading_runners": "正在載入出賽馬匹...",
        "sb_scoring_runners": "正在計算勝率...",
        "sb_building_recommendations": "正在生成投注建議...",
        "sb_analysis_done": "分析完成",
        "model_compare_results": "📈 模型對比結果",
        "model_compare_caption": "💡 獨贏 ROI：每場固定投注 $100 在「評分最高馬」的獨贏；若整段期間從未猜中第一名，ROI 會是 -100%。",
        "backtest_details_title": "🔍 回測詳細",
        "backtest_select_model": "請至少選擇一個模型",
        "backtest_partial_cancelled": "⚠️ 部分回測被取消: {count} 個模型未完成",
        "backtest_all_failed": "所有回測均被取消或失敗",
        "backtest_chart_title": "模型性能對比",
        "backtest_races_scroll": "📊 共 {count} 場賽事，可滾動查看所有場次",
        "backtest_no_detail": "該模型暫無詳細預測數據",
        "backtest_expander_detail": "📊 {model}（共 {detail_count} 場 / 測試場次: {test_races}）",
        "backtest_expander_empty": "📊 {model}（暫無詳細數據）",
        "ml_loading_data": "📥 正在加載 {start} 至 {end} 的歷史數據...",
        "ml_no_data": "未獲取到任何數據",
        "ml_processing_date": "正在處理日期: {date} ({current}/{total})",
        "ml_preparing_train": "正在訓練模型: {date} (準備訓練數據中...)",
        "ml_insufficient_train": "⚠️ {date} 訓練數據不足 ({count} 條)，跳過",
        "ml_training": "正在訓練模型: {date} (訓練數據: {count} 條, 模型: {model})",
        "ml_train_failed": "⚠️ {date} 模型訓練失敗，跳過",
        "progress_race_analysis": "正在分析第 {current}/{total} 场...",
        "progress_building_parlay": "正在计算过关组合...",
        "progress_optimizing_full_day": "正在优化全天投注策略...",
        "rule_backtest_progress": "正在回测: {date} 第{race_no}场 ({current}/{total})",
        "parlay_col_combo": "组合",
        "parlay_col_races": "场次",
        "parlay_col_horses": "马匹",
        "parlay_col_odds": "组合赔率",
        "parlay_col_joint_prob": "联合概率",
        "parlay_col_stake": "建议注额",
        "parlay_combo_2x1": "2串1",
        "parlay_combo_3x1": "3串1",
        "parlay_races_2": "第{r1}场 + 第{r2}场",
        "parlay_races_3": "第{r1}场 + 第{r2}场 + 第{r3}场",
    },
    "en": {
        # ==================== Basic ====================
        "app_title": "🐎 HK Horse Racing AI System",
        "login": "Login",
        "register": "Register",
        "logout": "Logout",
        "email": "Email",
        "password": "Password",
        "confirm_password": "Confirm Password",
        "login_btn": "Login",
        "register_btn": "Register",
        "back_to_login": "Back to Login",
        "welcome": "Welcome back",
        "login_failed": "Login failed. Please check your email and password.",
        "register_success": "Registration successful! Please login.",
        "email_exists": "Email already registered. Please login.",
        "not_registered_for_racing": "This email is not registered for Racing App. Please sign up first.",
        "forgot_password": "Forgot Password?",
        "remember_me": "Remember me (stay signed in for 7 days)",
        "remember_me_restoring": "Restoring your session…",
        "pool_single_title": "**Single Race Pools**",
        "pool_win": "Win",
        "pool_place": "Place",
        "pool_qin": "Quinella",
        "pool_qpl": "Quinella Place",
        "pool_tri": "Trio",
        "pool_tce": "Tierce",
        "pool_f4": "First 4",
        "pool_qtt": "Quartet",
        "pool_multi_title": "**Multi-Race Pools**",
        "pool_double": "Double",
        "pool_treble": "Treble",
        "pool_double_trio": "Double Trio",
        "pool_trio": "Triple Trio",
        "pool_six_up": "Six Up",
        "data_source_footer": "Data: HKJC API | Payment: Stripe",
        "home_subtitle": "AI-powered horse racing analysis, smart betting recommendations",
        "horse_count": "Total Horses",
        "race_count": "Total Races",
        "record_count": "Total Records",
        "jockey_count": "Total Jockeys",
        "trainer_count": "Total Trainers",
        "date_range": "Date Range",
        "update_all_data": "Update All Data",
        "horse_rating_title": "Horse Rating Leaderboard",
        "horse_rating_desc": "📌 Based on recent N races performance. Higher score = stronger horse.",
        "calculate_games": "Games",
        "display_limit": "Display Limit",
        "all_games": "All",
        "recent_n_games_format": "Last {n} races",
        "rating_calculating": "Calculating horse ratings ({scope})...",
        "update_all_data": "Update All Data",
        "checking_update": "Checking and updating data...",
        "update_complete": "✅ Update complete! Added {new_races} races, {new_records} records",
        "update_failed": "Update failed",
        "betting_pools": "🎲 Betting Pools",
        "single_pool": "Single Race Pools",
        "multi_pool": "Multi-Race Pools",
        "win_pool": "Win",
        "place_pool": "Place", 
        "qin_pool": "Quinella",
        "qpl_pool": "Quinella Place",
        "tri_pool": "Trio",
        "tce_pool": "Tierce",
        "f4_pool": "First 4",
        "qtt_pool": "Quartet",
        "double_pool": "Double",
        "treble_pool": "Treble",
        "double_trio": "Double Trio",
        "trio_pool": "Triple Trio",
        "six_up": "Six Up",
        "data_overview": "📊 Data Overview",
        "data_update": "🔄 Data Update",
        "smart_betting": "🎯 Smart Betting",
        "select_race_day": "📅 Select Race Day",
        "total_races": "📋 Total {count} races",
        "race_table_title": "🏇 Race {race_no} Runners",
        "qin_ev_insufficient": "Quinella {horse1} + {horse2} EV insufficient, not recommended",
        "qin_recommendation": "🔗 Quinella Recommendation",
        "qin_no_odds": "No quinella odds available",
        "qin_insufficient_horses": "Insufficient horses for quinella recommendation",
        "data_source": "📅 Data Source: HKJC | Update Frequency: Daily auto-update",
        "betting_pools": "🎲 Betting Pools",
        "race_table_title": "Race {race_no} Runners",
        "run_backtest": "▶️ Run Model Comparison",
        "select_models": "🤖 Select Models to Compare",
        "rating_system": "Rating System",
        "lightgbm": "LightGBM",
        "xgboost": "XGBoost",
        "ensemble": "Ensemble",
        
        # ==================== Sidebar ====================
        "about_header": "📘 About System",
        "about_text": """
**HK Horse Racing AI System** powered by AI:

- 🏇 Horse Rating System
- 🎯 Smart Betting Recommendations
- 📊 Full-day Optimization
- 📈 Historical Backtesting
- 💡 AI Win Probability

Let AI be your racing assistant.
""",
        "contact_header": "📧 Contact Us",
        "contact_email": "✉️ Email: Techlife2027@gmail.com",
        "guide_header": "📖 Quick Guide",
        "guide_text": """
1. Click [Refresh] for latest races
2. Check horse ratings
3. Go to Smart Betting for recommendations
4. Run backtest to validate strategies

💡 Each refresh uses 1 free trial
💎 Upgrade to Pro for unlimited access
""",
        
        # ==================== Subscription ====================
        "subscription": "Subscription",
        "free_tier": "Free",
        "pro_tier": "Pro",
        "remaining": "Remaining",
        "unlimited": "Unlimited",
        "upgrade": "Upgrade to Pro",
        "monthly": "Monthly HK$380/mo",
        "quarterly": "Quarterly HK$988/quarter",
        "save_info": "Save with quarterly",
        
        # ==================== Language ====================
        "chinese": "中文",
        "english": "English",
        
        # ==================== Admin ====================
        "admin_panel": "Admin Panel",
        "total_users": "Total Users",
        "pro_users": "Pro Users",
        "free_users": "Free Users",
        "user_list": "User List",
        
        # ==================== Smart Betting Page ====================
        "smart_betting": "🎯 Smart Betting",
        "betting_settings": "⚙️ Betting Settings",
        "betting_budget": "💰 Budget (HKD)",
        "risk_preference": "📊 Risk Preference",
        "conservative": "Conservative",
        "standard": "Standard",
        "aggressive": "Aggressive",
        "ai_model": "🤖 AI Model",
        "rating_weights": "📐 Rating Weights",
        "basic_weight": "Basic:30%",
        "race_weight": "Race:40%",
        "odds_weight": "Odds:30%",
        "temperature": "Temp:0.8",
        "odds_mix": "Odds Mix:0.6",
        "select_race_day": "📅 Select Race Day",
        "refresh_schedule": "🔄 Refresh Schedule",
        "no_races": "📌 No races in the next 14 days. Click 'Refresh Schedule' to sync.",
        "total_races": "📋 Total {count} races",
        "single_race_analysis": "📊 Single Race Analysis",
        "select_race": "Select Race",
        "refresh_race_data": "🔄 Refresh Race Data",
        "no_runners": "No runner data available. Click 'Refresh Race Data' to sync.",
        
        # ==================== AI Suggestions ====================
        "ai_strategy_suggestions": "💡 AI Betting Strategy",
        "ev_description": "Expected Value (EV) based on AI rating and odds",
        "low_risk": "🎯 Low Risk - Win/Place",
        "medium_risk": "🎯 Medium Risk - Quinella",
        "high_risk": "🎯 High Risk - Trio",
        "no_suggestions": "No suggestions",
        "qin_recommendation": "🔗 Quinella Recommendation",
        
        # ==================== Parlay Recommendation ====================
        "parlay_recommendation": "🎲 Parlay Recommendation",
        "select_parlay_races": "Select races for parlay",
        "select_2_6_races": "Select 2-6 races (in order)",
        "selected_races_count": "Selected {count} races",
        "generate_parlay": "🎲 Generate Parlay",
        "best_parlay": "🏆 Best Parlay",
        
        # ==================== Full Day Optimization ====================
        "full_day_optimization": "🌟 Full Day Optimization",
        "kelly_description": "Kelly Criterion + Risk Management",
        "generate_full_day": "🚀 Generate Full Day Strategy",
        "parlay_generation": "🔗 Parlay Generation",
        "parlay_description": "Recommend 2x1, 3x1 parlays based on confident horses",
        "generate_parlay_combo": "🎲 Generate Parlay",
        
        # ==================== Table Columns ====================
        "horse_name": "Horse",
        "horse_name_no": "Horse / No.",
        "horse_no": "No.",
        "row_index": "#",
        "draw": "Draw",
        "actual_weight": "Weight",
        "jockey": "Jockey",
        "win_odds": "Win",
        "place_odds": "Place",
        "win_rate": "Win Rate",
        "overall_score": "Score",
        "ev": "EV",
        "no_data": "No runner data",
        "realtime_odds_analysis": "📈 Real-time Odds Analysis",
        "realtime_odds_expand": "Show charts & details",
        "click_open": "Click to open",
        "click_open_recommend": "Click to open recommendation",
        "collapse_section": "▼ Collapse",
        "reopen_section": "▶ Expand",
        "expand_section_short": "▶ Expand",
        "realtime_odds_no_data": "No WIN/PLA time-series snapshots for this race. Collection runs only in the ~90 minutes before post time; past race days have no trend data unless captured at the time (final odds may still appear in the runner table).",
        "realtime_odds_latest": "Latest Odds Snapshots",
        "realtime_odds_trend": "Odds Trend (minutes before post)",
        "realtime_odds_snapshots": "Snapshots",
        "realtime_odds_min_before": "Min before post",
        "realtime_odds_recorded_at": "Recorded at",
        "realtime_odds_detail": "Time-point detail",
        "realtime_odds_points": "{count} time points captured",
        "realtime_odds_opening": "Opening odds",
        "realtime_odds_latest_val": "Latest odds",
        "realtime_odds_change": "Change",
        
        # ==================== Backtest Page ====================
        "backtest": "📊 Backtest",
        "model_comparison": "📊 Model Comparison",
        "backtest_period": "Select backtest period to compare model accuracy and ROI",
        "start_date": "Start Date",
        "end_date": "End Date",
        "run_backtest": "▶️ Run Model Comparison",
        "strategy_backtest": "📊 Strategy Backtest",
        "strategy_backtest_desc": "EV = Predicted Win Rate × Odds - 1. Bet when EV > threshold.",
        "win_strategy": "Win Strategy",
        "qin_strategy": "Quinella Strategy",
        "min_ev_threshold": "Min EV Threshold",
        "run_strategy_backtest": "▶️ Run Strategy Backtest",
        "backtest_result_invalid": "Invalid backtest result or no betting records",
        "disclaimer_backtest": "📌 Backtest results are based on historical data and do not guarantee future performance.",
        "top1_fixed_backtest": "🎯 Top1 Fixed Strategy Backtest",
        "top1_fixed_backtest_caption": "WIN+PLACE on rank #1 every race; optional Double Trio (R6-7), Triple Trio (R5-7), Six Up (R6-11); trio = Top1 + 2 weighted-random picks (separate dates, default last 2 weeks)",
        "top1_stake_label": "Stake per bet (HK$)",
        "top1_random_seed_label": "Random seed",
        "top1_use_date_seed": "Use meeting date as random seed",
        "top1_include_win_place": "Win + Place (every race)",
        "top1_include_double_trio": "Double Trio (R6 & R7)",
        "top1_include_triple_trio": "Triple Trio (R5–R7)",
        "top1_include_six_up": "Six Up (R6–R11)",
        "run_top1_fixed_backtest": "▶️ Run Top1 Fixed Strategy Backtest",
        "top1_backtest_running": "Running Top1 fixed strategy backtest ({model})...",
        "top1_summary_title": "Summary",
        "top1_detail_title": "Details (recommended vs actual)",
        "top1_col_pool": "Pool",
        "top1_col_date": "Date",
        "top1_col_venue": "Venue",
        "top1_col_race": "Race",
        "top1_col_recommended": "Recommended",
        "top1_col_actual": "Actual",
        "top1_col_hit": "Hit",
        "top1_col_stake": "Stake",
        "top1_col_return": "Return",
        "top1_col_note": "Note",
        "top1_hit_rate": "Hit rate",
        "top1_race_days": "Race days",
        "top1_skipped": "Skipped",

        "rank_calib_title": "📊 AI Rank Calibration Table",
        "rank_calib_caption": "All runners ranked by model win probability; yellow = finished top 4; dark yellow in actual column = AI #1 in actual top 3",
        "run_rank_calib": "▶️ Generate rank calibration table",
        "rank_calib_running": "Building rank calibration table ({model})...",
        "rank_calib_top1_top3": "AI #1 in actual top 3",
        "rank_calib_ai_top4_cover": "AI top 4 covers actual top 4",
        "rank_calib_race_count": "Races",
        "rank_calib_legend_top4": "Finished top 4",
        "rank_calib_legend_top1": "AI #1 in actual top 3",
        "rank_calib_col_rank": "#",
        "rank_calib_col_horse_no": "No.",
        "rank_calib_col_horse_name": "Horse",
        "rank_calib_col_win_prob": "Win %",
        "rank_calib_col_odds": "Odds",
        "rank_calib_col_actual": "Actual top 4",
        "rank_calib_race_label": "Race {race_no}",
        "rank_calib_train_window_label": "Training window (days)",
        "rank_calib_train_window_help": "ML training uses only races within N days before each race day; 0 = unlimited (all fetched history). 730 matches the Smart Betting app.",
        "rank_calib_train_window_summary": "Training window {days} days",
        "rank_calib_train_window_unlimited": "Training window: unlimited",
        
        # ==================== Messages ====================
        "upgrade_pro": "💎 Upgrade to Pro",
        "free_trial_used": "Free trials exhausted. Please upgrade to Pro.",
        "data_updated": "Data updated",
        "update_failed": "Update failed",
        "syncing_schedule": "Syncing schedule...",
        "sync_complete": "Sync complete! Success: {success}, Failed: {failed}",
        "updating_odds": "Updating odds and runners...",
        "calculating_win_rate": "Calculating win rate (Rating System)...",
        "calculating_ml": "Calculating win rate ({model})...",
        "betting_records": "📋 My Betting Records",
        "disclaimer": "⚠️ Predictions are for reference only. Bet responsibly.",
        "data_source": "📅 Data Source: HKJC | Update Frequency: Race day auto-update",
        # ==================== Extended i18n ====================
        "fill_email_password": "Please enter email and password",
        "logging_in": "Logging in...",
        "password_mismatch": "Passwords do not match",
        "password_min_length": "Password must be at least 6 characters",
        "registering": "Registering...",
        "register_failed": "Registration failed",
        "email_exists_login": "Email already registered. Please login.",
        "login_success": "Login successful",
        "wrong_email_password": "Incorrect email or password",
        "create_settings_failed": "Failed to create user settings",
        "session_expired": "Session expired. Please login again.",
        "trial_update_failed": "Failed to update trial count. Please refresh and try again.",
        "contact_admin_reset_password": "Contact admin to reset password",
        "stripe_session_detected": "🔔 Payment session detected. Click the button to verify.",
        "stripe_session_id": "Session ID",
        "stripe_verify_button": "✅ Verify Payment & Upgrade",
        "stripe_verifying": "Verifying...",
        "stripe_verify_success": "✅ Payment verified! You are now a Pro user.",
        "stripe_user_not_found": "User not found. Please login and try again.",
        "stripe_payment_incomplete": "Payment not completed. Please finish checkout.",
        "stripe_api_failed": "API request failed",
        "stripe_verify_failed": "Verification failed",
        "stripe_payment_cancelled": "Payment cancelled",
        "stripe_not_configured": "Stripe secret key not configured",
        "checkout_session_failed": "Failed to create checkout session",
        "checkout_go_stripe_monthly": "💳 Go to Stripe (Monthly HK$380)",
        "checkout_go_stripe_quarterly": "💳 Go to Stripe (Quarterly HK$988)",
        "back": "Back",
        "paywall_trials_remaining": "🔓 You have {remaining} free trials remaining",
        "paywall_upgrade_hint": "💎 Upgrade to Pro for unlimited access to all features",
        "paywall_feature": "Feature",
        "paywall_free": "Free",
        "paywall_pro": "Pro",
        "paywall_usage": "Usage",
        "paywall_usage_free": "30 trials",
        "paywall_horse_rating": "Horse Ratings",
        "paywall_smart_betting": "Smart Betting",
        "paywall_full_day": "Full-day Optimization",
        "paywall_backtest": "Historical Backtest",
        "admin_login_title": "Admin Login",
        "admin_username": "Username",
        "admin_login_btn": "Login",
        "admin_login_failed": "Incorrect username or password",
        "back_to_user_login": "Back to User Login",
        "admin_login_help": "Admin login",
        "back_to_user": "👤 Back",
        "exit_admin_mode": "Exit admin mode",
        "logout_help": "Logout",
        "sidebar_expand_hint": "Click to open",
        "sidebar_open_menu": "☰ Open menu",
        "tier_pro": "💎 Pro",
        "tier_free": "🔒 Free",
        "day_portfolio_title": "Best Race-day Portfolio",
        "day_portfolio_desc": "~HK$1,000 budget · Win/Place/Quinella/Trio/Tierce/Double · EV-weighted (min HK$10/bet)",
        "day_portfolio_budget_label": "Race-day Budget (HK$)",
        "generate_day_portfolio": "🎯 Generate Best Race-day Portfolio",
        "optimizing_day_portfolio": "Optimizing race-day portfolio...",
        "day_portfolio_import_failed": "Day portfolio optimizer failed to load",
        "lightgbm_not_installed": "LightGBM is not installed",
        "xgboost_not_installed": "XGBoost is not installed",
        "no_data_fetched": "No data retrieved",
        "no_races_found": "No races found",
        "backtest_cancelled": "⚠️ Backtest cancelled by user",
        "day_portfolio_backtest_progress": "Day portfolio backtest {model}: {date} {venue} ({current}/{total})",
        "day_portfolio_backtest_title": "📈 Day Portfolio Strategy Backtest ({model})",
        "day_portfolio_mode_fast": "Fast (weekly retrain)",
        "day_portfolio_mode_std": "Standard walk-forward",
        "day_portfolio_backtest_caption": "Mode: {mode} · Race days: {days} · Pools: Win/Place/Quinella/Trio/Tierce/Double",
        "metric_day_count": "Race Days",
        "metric_total_bets": "Total Bets",
        "metric_hit_bets": "Winning Bets",
        "metric_hit_rate": "Hit Rate",
        "metric_total_stake": "Total Stake",
        "metric_total_return": "Total Return",
        "portfolio_bet_details": "📋 Bet Details",
        "col_race_day": "Date",
        "col_venue": "Venue",
        "col_pool": "Pool",
        "col_content": "Selection",
        "col_odds": "Odds",
        "col_estimated": "Est.",
        "col_yes": "Yes",
        "col_no": "No",
        "col_stake": "Stake",
        "col_hit": "Hit",
        "col_return": "Return",
        "col_profit": "P/L",
        "no_day_portfolio_bets": "No qualifying race-day portfolio (no positive EV bets)",
        "day_portfolio_live_title": "💰 Best Race-day Portfolio",
        "day_portfolio_live_caption": "Target budget ~HK${budget:,.0f} · Allocated HK${stake:,.0f} · Win/Place/Quinella/Trio/Tierce/Double",
        "col_recommendation": "Pick",
        "col_probability": "Probability",
        "col_suggested_stake": "Suggested Stake",
        "estimated_odds_footnote": "* Asterisk indicates estimated odds",
        "fast_mode_label": "Fast mode (weekly retrain)",
        "fast_mode_help": "Standard: walk-forward retrain each race day. Fast: retrain weekly for speed.",
        "strategy_backtest_caption": "~HK$1,000/day EV allocation across Win/Place/Quinella/Trio/Tierce/Double · Same optimizer as Smart Betting",
        "strategy_model_help": "ML model for strategy backtest (default LightGBM)",
        "min_ev_help": "Only bet when expected value exceeds this threshold",
        "running_day_portfolio_backtest": "Running day portfolio backtest ({model})...",
        "using_cached_backtest": "📋 Using cached backtest result",
        "backtest_no_bets": "Backtest completed with no bets (try a wider date range or lower EV threshold)",
        "invalid_date_range": "Start date cannot be after end date",
        "backtest_period_info": "📊 Backtest period: {start} to {end} ({days} days)",
        "running_model_backtest": "Running model comparison backtest...",
        "calculating_full_day": "Calculating full-day betting strategy...",
        "no_betting_opportunities": "No qualifying betting opportunities found",
        "calculating_parlay": "Calculating parlay combinations...",
        "parlay_3leg_hint": "💡 3-leg parlay needs at least 3 races with ≥20% win probability; showing 2-leg only.",
        "no_parlay_combos": "No qualifying parlay combinations (requires positive EV)",
        "col_race_no": "Race",
        "col_horse": "Horse",
        "col_win_rate": "Win Rate",
        "col_suggested_amount": "Suggested Stake",
        "col_expected_value": "Expected Value",
        "total_stake_metric": "💰 Total Stake",
        "total_ev_metric": "📈 Total Expected Value",
        "expected_roi_metric": "📊 Expected ROI",
        "install_lightgbm_help": "Requires lightgbm library",
        "install_xgboost_help": "Requires xgboost library",
        "ml_install_hint": "Install LightGBM and/or XGBoost before running ML backtest",
        "model_select_help": "Choose prediction model: Rating System, LightGBM, XGBoost, or Ensemble",
        "date_mode_label": "Date Mode",
        "date_mode_future": "Upcoming Races",
        "date_mode_history": "Historical Races",
        "select_history_race_day": "Select Historical Race Day",
        "no_race_detail_data": "No detailed race data. Please refresh schedule.",
        "no_races_available": "No races available",
        "no_history_race_data": "No historical race data",
        "no_race_detail_for_date": "No detailed race data for this date",
        "sync_failed": "Sync failed",
        "prediction_error": "🔍 Prediction error",
        "scoring_weights_paywall_hint": "Click below to unlock scoring weight settings",
        "scoring_weights_paywall_btn": "💎 Unlock Scoring Weight Settings",
        "nav_data_ratings": "📊 Data & Ratings",
        "nav_smart_betting": "🎯 Smart Betting",
        "nav_backtest": "📈 Backtest",
        "nav_label": "Navigation",
        "no_model_detail": "No detailed prediction data for this model",
        "no_detail_data": "No detailed data",
        "update_failed_msg": "Update failed",
        "historical_mode_info": "📅 Historical test mode: scoring and ML training use data strictly before the selected race day.",
        "calculating_parlay_schedule": "Calculating parlay recommendations...",
        "parlay_insufficient_data": "Insufficient data for selected races. Try selecting more races.",
        "parlay_select_hint": "Select races, then click Generate Parlay for best 2-leg / 3-leg combos.",
        "no_qin_combos": "No quinella combination data",
        "missing_win_odds_hint": "⚠️ Missing win odds; EV below uses estimated quinella odds",
        "odds_label": "Odds",
        "odds_estimated_label": "Est.",
        "select_label": "Select",
        "qin_selected_summary": "✅ Selected {count} combos, suggested total stake: HK${stake:.0f}",
        "select_combos_hint": "Check the combinations you are interested in",
        "tri_insufficient_horses": "Insufficient horses for trio recommendation",
        "no_parlay_combo_found": "No suitable parlay found. Try more races or a different AI model.",
        "weekdays": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",
        "win_place_recommend": "🎯 Win/Place Recommendation",
        "qin_recommend_expander": "🔗 Quinella Recommendation",
        "tri_recommend_expander": "🎲 Trio Recommendation",
        "tce_recommend_expander": "🏆 Tierce Recommendation",
        "win_odds_label": "Win Odds",
        "place_odds_label": "Place Odds",
        "expected_roi_label": "Expected ROI",
        "parlay_select_races_title": "Select races for parlay",
        "selected_races_caption": "Selected {count} races",
        "parlay_results_title": "📊 Parlay Recommendations",
        "parlay_odds_label": "Odds",
        "parlay_combined_prob": "Combined Prob.",
        "parlay_risk_label": "Risk",
        "parlay_expected_roi": "Expected ROI",
        "parlay_suggested_bet": "💡 Suggested bet",
        "parlay_best_title": "🏆 Best Pick",
        "parlay_best_combo": "Best parlay combo",
        "parlay_method": "Parlay type",
        "parlay_total_odds": "Total odds",
        "parlay_suggest_stake": "Suggested stake",
        "risk_low": "Low",
        "risk_medium": "Medium",
        "risk_high": "High",
        "tri_est_odds": "Est. odds: {odds:.1f}x",
        "tri_est_odds_pending": "Est. odds: pending",
        "tri_joint_prob": "Combined probability",
        "tri_ev": "Expected value (EV)",
        "tri_ev_recommend": "✅ EV > 0.15, recommended",
        "tri_ev_skip": "❌ EV too low, not recommended",
        "tri_missing_odds": "⚠️ Missing win odds; values below are estimates",
        "tce_insufficient_horses": "Insufficient horses for tierce recommendation",
        "tce_order_hint": "Order: 1st > 2nd > 3rd (exact finishing order required)",
        "tce_est_odds": "Est. odds: {odds:.1f}x",
        "tce_est_odds_pending": "Est. odds: pending",
        "tce_joint_prob": "Ordered probability",
        "tce_ev": "Expected value (EV)",
        "tce_ev_recommend": "✅ EV > 0.15, recommended",
        "tce_ev_skip": "❌ EV too low, not recommended",
        "tce_missing_odds": "⚠️ Missing win odds; values below are estimates",
        "sb_loading_runners": "Loading runners...",
        "sb_scoring_runners": "Scoring runners...",
        "sb_building_recommendations": "Building recommendations...",
        "sb_analysis_done": "Analysis complete",
        "model_compare_results": "📈 Model Comparison Results",
        "model_compare_caption": "💡 Win ROI: $100 win bet on top-rated horse each race. If no wins in the period, ROI is -100%.",
        "backtest_details_title": "🔍 Backtest Details",
        "backtest_select_model": "Please select at least one model",
        "backtest_partial_cancelled": "⚠️ Partially cancelled: {count} model(s) incomplete",
        "backtest_all_failed": "All backtests were cancelled or failed",
        "backtest_chart_title": "Model Performance Comparison",
        "backtest_races_scroll": "📊 {count} races total — scroll to view all",
        "backtest_no_detail": "No detailed prediction data for this model",
        "backtest_expander_detail": "📊 {model} ({detail_count} races / tested: {test_races})",
        "backtest_expander_empty": "📊 {model} (no detail data)",
        "ml_loading_data": "📥 Loading historical data {start} to {end}...",
        "ml_no_data": "No data retrieved",
        "ml_processing_date": "Processing date: {date} ({current}/{total})",
        "ml_preparing_train": "Training model: {date} (preparing data...)",
        "ml_insufficient_train": "⚠️ {date} insufficient training data ({count} rows), skipped",
        "ml_training": "Training model: {date} ({count} rows, model: {model})",
        "ml_train_failed": "⚠️ {date} model training failed, skipped",
        "progress_race_analysis": "Analyzing race {current}/{total}...",
        "progress_building_parlay": "Building parlay combinations...",
        "progress_optimizing_full_day": "Optimizing full-day strategy...",
        "rule_backtest_progress": "Backtesting: {date} Race {race_no} ({current}/{total})",
        "parlay_col_combo": "Combo",
        "parlay_col_races": "Races",
        "parlay_col_horses": "Horses",
        "parlay_col_odds": "Combined Odds",
        "parlay_col_joint_prob": "Joint Prob.",
        "parlay_col_stake": "Suggested Stake",
        "parlay_combo_2x1": "2-leg",
        "parlay_combo_3x1": "3-leg",
        "parlay_races_2": "R{r1} + R{r2}",
        "parlay_races_3": "R{r1} + R{r2} + R{r3}",
    }
}
#---------
def t():
    """获取当前语言文本"""
    try:
        lang = st.session_state.get("lang", "zh")
        # 确保返回的是字典
        if lang == "zh":
            return TEXTS["zh"]
        else:
            return TEXTS["en"]
    except Exception as e:
        print(f"t() 函数错误: {e}")
        return TEXTS["zh"]


def get_lang() -> str:
    return st.session_state.get("lang", "zh")


def _make_betting_strategy_engine() -> "BettingStrategyEngine":
    try:
        return BettingStrategyEngine(lang=get_lang())
    except TypeError:
        return BettingStrategyEngine()


def tx(zh: str, en: str) -> str:
    return zh if get_lang() == "zh" else en


MODEL_CHOICE_OPTIONS = ["评分系统", "LightGBM", "XGBoost", "集成模型"]


def display_model_choice(model_choice: str) -> str:
    mapping = {
        "评分系统": t()["rating_system"],
        "LightGBM": t()["lightgbm"],
        "XGBoost": t()["xgboost"],
        "集成模型": t()["ensemble"],
    }
    return mapping.get(model_choice, model_choice)


def _model_section_title(title: str, model_choice: str) -> str:
    label = display_model_choice(model_choice)
    if get_lang() == "zh":
        return f"{title}（{label}）"
    return f"{title} ({label})"


def _weekday_label(date_str: str) -> str:
    weekdays = t()["weekdays"].split(",")
    wd = datetime.strptime(date_str, "%Y-%m-%d").weekday()
    return weekdays[wd] if wd < len(weekdays) else ""


def _format_race_date_short(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m")
    except ValueError:
        return date_str


def _format_post_time(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        value = value.strip()
        iso_match = re.search(r"T(\d{2}:\d{2})", value)
        if iso_match:
            return iso_match.group(1)
        if "T" in value:
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.strftime("%H:%M")
            except ValueError:
                pass
        if len(value) >= 5 and value[2:3] == ":":
            return value[:5]
    return str(value)


def _normalize_surface_label(label: str) -> str:
    if not label:
        return ""
    if get_lang() != "zh":
        return label
    mapping = {
        "Turf": "草地",
        "All Weather Track": "全天候跑道",
        "AWT": "全天候跑道",
    }
    return mapping.get(label, label)


def _race_surface_label(race: Dict) -> str:
    surface = race.get("surface") or race.get("race_track") or ""
    if surface:
        return _normalize_surface_label(str(surface))
    rt = race.get("raceTrack") or {}
    if isinstance(rt, dict):
        if get_lang() == "zh":
            desc = rt.get("description_ch") or rt.get("description_en") or ""
        else:
            desc = rt.get("description_en") or rt.get("description_ch") or ""
        return _normalize_surface_label(desc)
    return ""


def _race_course_label(race: Dict) -> str:
    rc = race.get("raceCourse") or {}
    if isinstance(rc, dict):
        if get_lang() == "zh":
            desc = (rc.get("description_ch") or "").strip()
            if desc:
                return desc if "賽道" in desc else f"{desc}賽道"
        else:
            desc = (rc.get("description_en") or "").strip()
            if desc:
                return desc
    code = race.get("race_course_code") or ""
    if not code:
        return ""
    code_str = str(code).strip()
    if get_lang() == "zh":
        if code_str.endswith("賽道"):
            return code_str
        return f"{code_str}賽道"
    if code_str.lower().startswith("course"):
        return code_str
    return f"Course {code_str}"


def _is_local_venue(venue: Optional[str]) -> bool:
    return (venue or "ST").strip().upper() in ("ST", "HV")


def _venue_display_label(race: Dict) -> str:
    """赛马场/赛事来源显示名（ST=沙田, HV=跑马地, S*=海外转播）"""
    venue = (race.get("venue") or "ST").strip().upper()
    venue_name = (race.get("venue_name") or "").strip()
    if get_lang() == "zh":
        local_names = {"ST": "沙田", "HV": "跑馬地"}
        if venue in local_names:
            return local_names[venue]
        if venue.startswith("S") or venue in ("OS", "AU", "UK", "FR", "JP"):
            return f"海外({venue})"
        if venue_name:
            return venue_name
        return venue
    local_names = {"ST": "Sha Tin", "HV": "Happy Valley"}
    if venue in local_names:
        return local_names[venue]
    if venue.startswith("S") or venue in ("OS", "AU", "UK", "FR", "JP"):
        return f"Overseas ({venue})"
    return venue_name or venue


def _race_list_sort_key(race: Dict):
    venue = (race.get("venue") or "ST").strip().upper()
    local_rank = {"ST": 0, "HV": 1}.get(venue, 2)
    post_time = _format_post_time(
        race.get("post_time") or race.get("postTime") or race.get("race_time") or ""
    )
    return (local_rank, race.get("race_no", 0), post_time)


def _format_race_select_label(race: Dict, *, include_date: bool = True) -> str:
    """Format race dropdown label, e.g. 第1場 （04/07 (六), 沙田, 16:00, 1200米, 草地, C+3賽道, 好地）"""
    race_no = race.get("race_no", 0)
    race_date = race.get("race_date", "")
    parts: List[str] = []

    if include_date and race_date:
        short_date = _format_race_date_short(race_date)
        weekday = _weekday_label(race_date)
        if short_date and weekday:
            parts.append(f"{short_date} ({weekday})")
        elif short_date:
            parts.append(short_date)

    venue_label = _venue_display_label(race)
    if venue_label:
        parts.append(venue_label)

    post_time = _format_post_time(
        race.get("post_time")
        or race.get("postTime")
        or race.get("scheduledStart")
        or race.get("startTime")
        or race.get("race_time")
    )
    if post_time:
        parts.append(post_time)

    distance = race.get("distance") or race.get("distanceMeters") or 0
    try:
        distance = int(distance)
    except (TypeError, ValueError):
        distance = 0
    if distance > 0:
        parts.append(f"{distance}米" if get_lang() == "zh" else f"{distance}m")

    surface = _race_surface_label(race)
    if surface:
        parts.append(surface)

    course = _race_course_label(race)
    if course:
        parts.append(course)

    going = race.get("going") or ""
    if going:
        parts.append(str(going))

    sep = "，" if get_lang() == "zh" else ", "
    if get_lang() == "zh":
        if parts:
            return f"第{race_no}場 （{sep.join(parts)}）"
        return f"第{race_no}場"
    if parts:
        return f"Race {race_no} ({sep.join(parts)})"
    return f"Race {race_no}"


DATE_MODE_FUTURE = "未來賽事"
DATE_MODE_HISTORY = "歷史賽事"


def _date_mode_label(mode: str) -> str:
    if mode == DATE_MODE_FUTURE:
        return t()["date_mode_future"]
    if mode == DATE_MODE_HISTORY:
        return t()["date_mode_history"]
    return mode


@st.cache_data(ttl=3600, show_spinner=False)
def get_horses_name_lookup() -> Dict[str, Dict[str, str]]:
    """horse_id -> {name_zh, name_en}，用于英文模式补全马名。"""
    lookup: Dict[str, Dict[str, str]] = {}
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/horses_v2?select=horse_id,name_zh,name_en&limit=50000"
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            for row in response.json():
                hid = row.get("horse_id")
                if hid:
                    lookup[str(hid)] = {
                        "name_zh": row.get("name_zh") or "",
                        "name_en": row.get("name_en") or "",
                    }
    except Exception as exc:
        print(f"get_horses_name_lookup failed: {exc}")
    return lookup


@st.cache_data(ttl=3600, show_spinner=False)
def get_horses_name_by_zh_lookup() -> Dict[str, str]:
    """Chinese horse name -> English name."""
    by_zh: Dict[str, str] = {}
    for info in get_horses_name_lookup().values():
        zh = (info.get("name_zh") or "").strip()
        en = (info.get("name_en") or "").strip()
        if zh and en:
            by_zh[zh] = en
    return by_zh


def _apply_name_lookups_to_record(record: Dict) -> Dict:
    """Fill horse_name_en on a copy using horses_v2 (by id, then by Chinese name)."""
    enriched = dict(record)
    if (enriched.get("horse_name_en") or "").strip():
        return enriched
    by_id = get_horses_name_lookup()
    by_zh = get_horses_name_by_zh_lookup()
    hid = str(enriched.get("horse_id") or "")
    if hid and hid in by_id:
        enriched["horse_name_en"] = by_id[hid].get("name_en") or ""
    zh = (enriched.get("horse_name_zh") or enriched.get("horse_name") or "").strip()
    if not (enriched.get("horse_name_en") or "").strip() and zh and zh in by_zh:
        enriched["horse_name_en"] = by_zh[zh]
    return enriched


def resolve_horse_name(record: Dict) -> str:
    """当前语言下的马名。"""
    from betting_strategy_engine import pick_horse_name

    lang = get_lang()
    rec = _apply_name_lookups_to_record(record) if lang == "en" else record
    lookup = get_horses_name_lookup() if lang == "en" else None
    return pick_horse_name(rec, lang, lookup)


def _enrich_runner_horse_names(runners: List[Dict]) -> List[Dict]:
    """Fill missing English names from horses_v2 (language-neutral, safe to cache)."""
    if not runners:
        return runners
    for runner in runners:
        if not (runner.get("horse_name_en") or "").strip():
            runner["horse_name_en"] = _apply_name_lookups_to_record(runner).get("horse_name_en") or ""
    return runners


def localize_runner_names(runners: List[Dict]) -> List[Dict]:
    """就地更新 runner 的 horse_name 为当前语言。"""
    for runner in runners:
        runner["horse_name"] = resolve_horse_name(runner)
    return runners


SEX_EN_MAP = {
    "雄": "G",
    "阉": "G",
    "閹": "G",
    "牡": "C",
    "雌": "F",
    "Gelding": "G",
    "Colt": "C",
    "Filly": "F",
    "Mare": "F",
}


def format_sex(value, lang: Optional[str] = None) -> str:
    """性别字段英文显示（G/C/F）。"""
    lang = lang or get_lang()
    if lang != "en" or value in (None, "", "-"):
        return value if value not in (None, "") else "-"
    text = str(value).strip()
    if text in SEX_EN_MAP:
        return SEX_EN_MAP[text]
    if len(text) == 1 and text.upper() in ("G", "C", "F", "M", "H"):
        return text.upper()
    return text


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in str(text))


@st.cache_data(ttl=3600, show_spinner=False)
def get_jockeys_name_lookup() -> Dict[str, str]:
    """Chinese jockey name -> English name."""
    lookup: Dict[str, str] = {}
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/jockeys?select=name_zh,name_en,name&limit=5000"
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            for row in response.json():
                zh = (row.get("name_zh") or row.get("name") or "").strip()
                en = (row.get("name_en") or "").strip()
                if zh and en:
                    lookup[zh] = en
    except Exception as exc:
        print(f"get_jockeys_name_lookup failed: {exc}")
    return lookup


def resolve_jockey_name(record: Dict) -> str:
    """当前语言下的骑师名。"""
    lang = get_lang()
    name = record.get("jockey_name") or record.get("jockey") or "-"
    if lang != "en":
        return name or "-"
    en_name = (record.get("jockey_name_en") or "").strip()
    if en_name:
        return en_name
    if name and not _has_cjk(name):
        return name
    if name:
        mapped = get_jockeys_name_lookup().get(str(name).strip())
        if mapped:
            return mapped
    return name or "-"


def format_risk_level(level: str) -> str:
    mapping = {
        "低": t()["risk_low"],
        "中": t()["risk_medium"],
        "高": t()["risk_high"],
        "Low": t()["risk_low"],
        "Medium": t()["risk_medium"],
        "High": t()["risk_high"],
    }
    return mapping.get(level, level)


class _UiProgressBar:
    """Streamlit progress bar helper for long smart-betting operations."""

    def __init__(self, start_text: Optional[str] = None):
        self.bar = st.progress(0, text=start_text or t()["sb_loading_runners"])

    def step(self, fraction: float, text: str) -> None:
        self.bar.progress(min(max(fraction, 0.0), 1.0), text=text)

    def finish(self, text: Optional[str] = None) -> None:
        self.bar.progress(1.0, text=text or t()["sb_analysis_done"])
        self.bar.empty()


def _runner_record(row: Dict) -> Dict:
    """Build a horse record dict for name resolution."""
    horse_name_zh = row.get("horse_name_zh") or row.get("horse_name") or row.get("name_zh") or ""
    return {
        "horse_id": row.get("horse_id"),
        "horse_name": horse_name_zh,
        "horse_name_zh": horse_name_zh,
        "horse_name_en": row.get("horse_name_en") or row.get("name_en") or "",
        "horse_no": row.get("horse_no"),
    }


def _finalize_parlay_runners(runners: List[Dict]) -> List[Dict]:
    return localize_runner_names(runners) if runners else []
#-------------------------
#-------------
@st.cache_data(ttl=300)
def get_qin_odds(race_date: str, venue: str, race_no: int, horse_no1: int, horse_no2: int) -> Optional[float]:
    """从 odds_history 获取连赢赔率"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/odds_history?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race_no}&odds_type=eq.QIN&horse_id=eq.{horse_no1}+{horse_no2}&order=recorded_at.desc&limit=1"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('odds_value')
        return None
    except Exception as e:
        print(f"获取连赢赔率失败: {e}")
        return None
#--------------
#-------------------------
# ==================== Supabase配置 ====================
SUPABASE_URL = st.secrets.get("SUPABASE_STOCK_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_STOCK_SECRET_KEY", "")
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_STOCK_ANON_KEY", "")

# ==================== Stripe配置 ====================
STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_MONTHLY = st.secrets.get("STRIPE_PRICE_MONTHLY", "price_1TeohqRtFEp2E97kgAACxQl0")
STRIPE_PRICE_QUARTERLY = st.secrets.get("STRIPE_PRICE_QUARTERLY", "price_1TeokmRtFEp2E97kmHvf2YXe")

# ==================== 初始化Session State ====================
def init_session_state():
    """初始化所有session state变量"""
    defaults = {
        "lang": "zh",
        "authenticated": False,
        "user_id": None,
        "user_email": None,
        "access_token": None,
        "refresh_token": None,
        "token_expiry": 0,
        "remember_me_active": False,
        "admin_mode": False,
        "show_admin_login": False,
        "admin_session_expires_at": 0,
        "try_admin_local_restore": False,
        "show_register": False,
        "show_paywall": False,
        "payment_url": None,
        "payment_type": None,
        "stop_backtest": False,  # ⭐ 新增：回测取消标志
        # 删除 current_page，因为不再需要页面路由
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ==================== Supabase连接 ====================
@st.cache_resource
def init_supabase() -> Optional[Client]:
    """初始化Supabase连接"""
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase初始化失败: {e}")
    return None

supabase = init_supabase()
#---------------
def get_supabase_headers(use_secret=False, access_token=None):
    """获取Supabase API请求头"""
    if use_secret:
        # 直接使用 SUPABASE_KEY（service_role 密钥）
        return {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
    elif access_token:
        return {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    else:
        return {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json"
        }


try:
    from strategy_backtest_engine import (
        BacktestDiagnostics,
        BacktestSummary,
        StrategyBacktester,
        fetch_win_odds_snapshot,
    )
    STRATEGY_BACKTEST_OK = True
except ImportError as _strategy_backtest_import_error:
    STRATEGY_BACKTEST_OK = False
    STRATEGY_BACKTEST_IMPORT_ERROR = str(_strategy_backtest_import_error)
    BacktestDiagnostics = None  # type: ignore
    BacktestSummary = None  # type: ignore
    StrategyBacktester = None  # type: ignore
    fetch_win_odds_snapshot = None  # type: ignore

try:
    from day_portfolio_optimizer import (
        DayPortfolioOptimizer,
        DayPortfolioResult,
        build_race_day_races_from_performances,
    )
    DAY_PORTFOLIO_OK = True
except ImportError as _day_portfolio_import_error:
    DAY_PORTFOLIO_OK = False
    DAY_PORTFOLIO_IMPORT_ERROR = str(_day_portfolio_import_error)

try:
    import incident_llm_service as ils
    get_combined_incident_adjustment = ils.get_combined_incident_adjustment
    get_llm_impact_from_cache = ils.get_llm_impact_from_cache
    incident_combined_feature_score = getattr(ils, "incident_combined_feature_score", None)
    batch_cache_missing_incidents = ils.batch_cache_missing_incidents
    fetch_incident_llm_usage_stats = ils.fetch_incident_llm_usage_stats
    count_missing_incident_cache = getattr(ils, "count_missing_incident_cache", None)
    estimate_backfill_tokens = getattr(ils, "estimate_backfill_tokens", None)
    format_datetime_hkt = getattr(
        ils,
        "format_datetime_hkt",
        lambda iso_str: (iso_str or "")[:19].replace("T", " "),
    )
    fetch_past_incident_texts = getattr(ils, "fetch_past_incident_texts", None)
    run_auto_incident_backfill = getattr(ils, "run_auto_incident_backfill", None)
    search_incident_llm_cache = getattr(ils, "search_incident_llm_cache", None)
    build_incident_context_maps = getattr(ils, "build_incident_context_maps", None)
    build_incident_llm_map_from_texts = getattr(ils, "build_incident_llm_map_from_texts", None)
    resolve_incident_cache_display = getattr(ils, "resolve_incident_cache_display", None)
    format_venue_label = getattr(ils, "format_venue_label", lambda v, lang="zh": v or "-")
    incident_text_hash_fn = getattr(ils, "incident_text_hash", None)
    INCIDENT_SCAN_LIMIT = getattr(ils, "INCIDENT_SCAN_LIMIT", 5000)
    INCIDENT_LLM_OK = True
    INCIDENT_LLM_IMPORT_ERROR = ""
except ImportError as _incident_llm_import_error:
    ils = None
    INCIDENT_LLM_OK = False
    INCIDENT_LLM_IMPORT_ERROR = str(_incident_llm_import_error)
    get_combined_incident_adjustment = None
    get_llm_impact_from_cache = None
    incident_combined_feature_score = None
    batch_cache_missing_incidents = None
    fetch_incident_llm_usage_stats = None
    count_missing_incident_cache = None
    estimate_backfill_tokens = None
    format_datetime_hkt = lambda iso_str: (iso_str or "")[:19].replace("T", " ")
    fetch_past_incident_texts = None
    run_auto_incident_backfill = None
    search_incident_llm_cache = None
    build_incident_context_maps = None
    build_incident_llm_map_from_texts = None
    resolve_incident_cache_display = None
    format_venue_label = lambda v, lang="zh": v or "-"
    incident_text_hash_fn = None
    INCIDENT_SCAN_LIMIT = 5000


@st.cache_data(ttl=300, show_spinner=False)
def _load_missing_incident_stats(supabase_url: str) -> Dict:
    if not count_missing_incident_cache or not supabase_url:
        return {}
    hdrs = get_supabase_headers(use_secret=True)
    return count_missing_incident_cache(supabase_url, hdrs)

def supabase_request(method: str, table: str, data=None, params=None, access_token=None):
    """通用的Supabase REST API请求"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = get_supabase_headers(access_token, use_secret=(access_token is None))
    
    if params:
        url += f"?{params}"
    
    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method == "PATCH":
        response = requests.patch(url, headers=headers, json=data)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    return response

# ==================== 用户认证函数 ====================
REMEMBER_ME_DAYS = 7
AUTH_STORAGE_KEY = "racing_app_auth_v1"
ADMIN_SESSION_HOURS = 24
ADMIN_STORAGE_KEY = "racing_app_admin_v1"


def persist_remember_me_auth(
    refresh_token: str,
    user_id: str,
    user_email: str,
) -> None:
    """将 refresh_token 写入浏览器 localStorage（7 天有效）。"""
    if not refresh_token or not user_id:
        return
    import streamlit.components.v1 as components

    expires_at = int((time.time() + REMEMBER_ME_DAYS * 86400) * 1000)
    payload = {
        "refresh_token": refresh_token,
        "user_id": user_id,
        "user_email": user_email or "",
        "expires_at": expires_at,
    }
    components.html(
        f"""
        <script>
        (function() {{
            try {{
                localStorage.setItem({json.dumps(AUTH_STORAGE_KEY)}, {json.dumps(payload)});
            }} catch (e) {{
                console.error("remember me save failed", e);
            }}
        }})();
        </script>
        """,
        height=0,
    )


def clear_persisted_remember_me_auth() -> None:
    """清除浏览器 localStorage 中的记住我凭证。"""
    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        try {{
            localStorage.removeItem({json.dumps(AUTH_STORAGE_KEY)});
        }} catch (e) {{
            console.error("remember me clear failed", e);
        }}
        </script>
        """,
        height=0,
    )


def _inject_remember_me_restore_js() -> None:
    """未登录时读取 localStorage，通过一次性 URL 参数把 refresh_token 交给 Python。"""
    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        (function() {{
            try {{
                const key = {json.dumps(AUTH_STORAGE_KEY)};
                const raw = localStorage.getItem(key);
                if (!raw) return;
                const auth = JSON.parse(raw);
                if (!auth || !auth.refresh_token || !auth.expires_at) {{
                    localStorage.removeItem(key);
                    return;
                }}
                if (auth.expires_at <= Date.now()) {{
                    localStorage.removeItem(key);
                    return;
                }}
                const url = new URL(window.parent.location.href);
                if (url.searchParams.get("remember_restore") === "1") return;
                url.searchParams.set("remember_restore", "1");
                url.searchParams.set("rt", auth.refresh_token);
                url.searchParams.set("uid", auth.user_id || "");
                url.searchParams.set("email", auth.user_email || "");
                window.parent.location.replace(url.toString());
            }} catch (e) {{
                console.error("remember me restore failed", e);
            }}
        }})();
        </script>
        """,
        height=0,
    )


def _admin_session_token(expires_at_sec: int) -> str:
    raw = f"{ADMIN_USERNAME}|{ADMIN_PASSWORD}|{expires_at_sec}|racing_admin_v1"
    return hashlib.sha256(raw.encode()).hexdigest()


def persist_admin_session() -> None:
    """管理员会话写入 localStorage（24 小时内点击齿轮免重复登录）。"""
    import streamlit.components.v1 as components

    expires_at_ms = int((time.time() + ADMIN_SESSION_HOURS * 3600) * 1000)
    expires_at_sec = expires_at_ms // 1000
    token = _admin_session_token(expires_at_sec)
    st.session_state.admin_session_expires_at = expires_at_sec
    payload = {"expires_at": expires_at_ms, "token": token}
    components.html(
        f"""
        <script>
        (function() {{
            try {{
                localStorage.setItem({json.dumps(ADMIN_STORAGE_KEY)}, {json.dumps(payload)});
            }} catch (e) {{
                console.error("admin session save failed", e);
            }}
        }})();
        </script>
        """,
        height=0,
    )


def clear_persisted_admin_session() -> None:
    import streamlit.components.v1 as components

    st.session_state.admin_session_expires_at = 0
    components.html(
        f"""
        <script>
        try {{
            localStorage.removeItem({json.dumps(ADMIN_STORAGE_KEY)});
        }} catch (e) {{
            console.error("admin session clear failed", e);
        }}
        </script>
        """,
        height=0,
    )


def _inject_admin_restore_js() -> None:
    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        (function() {{
            try {{
                const key = {json.dumps(ADMIN_STORAGE_KEY)};
                const raw = localStorage.getItem(key);
                if (!raw) return;
                const auth = JSON.parse(raw);
                if (!auth || !auth.token || !auth.expires_at) {{
                    localStorage.removeItem(key);
                    return;
                }}
                if (auth.expires_at <= Date.now()) {{
                    localStorage.removeItem(key);
                    return;
                }}
                const url = new URL(window.parent.location.href);
                if (url.searchParams.get("admin_restore") === "1") return;
                url.searchParams.set("admin_restore", "1");
                url.searchParams.set("exp", String(auth.expires_at));
                url.searchParams.set("token", auth.token);
                window.parent.location.replace(url.toString());
            }} catch (e) {{
                console.error("admin session restore failed", e);
            }}
        }})();
        </script>
        """,
        height=0,
    )


def _verify_admin_session_token(expires_at_ms: int, token: str) -> bool:
    try:
        expires_at_ms = int(expires_at_ms)
    except (TypeError, ValueError):
        return False
    if expires_at_ms <= int(time.time() * 1000):
        return False
    expected = _admin_session_token(expires_at_ms // 1000)
    return hmac.compare_digest(expected, token or "")


def is_admin_session_valid() -> bool:
    if float(st.session_state.get("admin_session_expires_at") or 0) > time.time():
        return True
    return False


def activate_admin_mode(*, preserve_user: bool = True) -> None:
    """进入管理员模式（可选保留原用户会话以便退出时恢复）。"""
    if preserve_user and st.session_state.get("user_id") not in (None, "admin"):
        st.session_state.admin_previous_user_id = st.session_state.get("user_id")
        st.session_state.admin_previous_user_email = st.session_state.get("user_email")
        st.session_state.admin_previous_access_token = st.session_state.get("access_token")
        st.session_state.admin_previous_refresh_token = st.session_state.get("refresh_token")
    st.session_state.admin_mode = True
    st.session_state.show_admin_login = False
    st.session_state.authenticated = True
    st.session_state.user_id = "admin"
    st.session_state.user_email = ADMIN_EMAIL


def try_restore_admin_session() -> None:
    """从 URL 参数或 localStorage 恢复管理员会话。"""
    if st.session_state.get("admin_mode"):
        return

    qp = st.query_params
    if qp.get("admin_restore") == "1" and qp.get("token") and qp.get("exp"):
        expires_at_ms = qp.get("exp")
        token = qp.get("token")
        for key in ("admin_restore", "exp", "token"):
            if key in qp:
                del qp[key]
        if _verify_admin_session_token(int(expires_at_ms), token):
            st.session_state.admin_session_expires_at = int(expires_at_ms) // 1000
            activate_admin_mode(preserve_user=True)
            st.rerun()
        else:
            clear_persisted_admin_session()
        return

    if qp.get("admin_restore") == "1":
        return


def restore_session_with_refresh_token(
    refresh_token: str,
    user_id: str,
    user_email: str,
) -> bool:
    """用 refresh_token 恢复 Supabase 会话。"""
    if not refresh_token:
        return False
    st.session_state.refresh_token = refresh_token
    st.session_state.user_id = user_id or None
    st.session_state.user_email = user_email or None
    new_token = refresh_auth_token()
    if not new_token:
        return False
    st.session_state.authenticated = True
    st.session_state.remember_me_active = True
    st.session_state.home_section_nav = t()["nav_smart_betting"]
    persist_remember_me_auth(
        st.session_state.refresh_token,
        st.session_state.user_id,
        st.session_state.user_email,
    )
    return True


def try_restore_remember_me_login() -> None:
    """启动时尝试从「记住我」恢复登录。"""
    if st.session_state.get("authenticated"):
        return

    qp = st.query_params
    if qp.get("remember_restore") == "1" and qp.get("rt"):
        refresh_token = qp.get("rt")
        user_id = qp.get("uid") or ""
        user_email = qp.get("email") or ""
        for key in ("remember_restore", "rt", "uid", "email"):
            if key in qp:
                del qp[key]
        if restore_session_with_refresh_token(refresh_token, user_id, user_email):
            st.rerun()
        else:
            clear_persisted_remember_me_auth()
            st.warning(t()["session_expired"])
        return

    if qp.get("remember_restore") == "1":
        return

    _inject_remember_me_restore_js()


def ensure_valid_access_token() -> None:
    """access_token 将过期时主动刷新；失败则清会话但保留「记住我」供下次自动恢复。"""
    if not st.session_state.get("authenticated"):
        return
    if st.session_state.get("user_id") == "admin":
        return
    expiry = float(st.session_state.get("token_expiry") or 0)
    if time.time() < expiry - 300:
        return
    if refresh_auth_token():
        if st.session_state.get("remember_me_active"):
            persist_remember_me_auth(
                st.session_state.refresh_token,
                st.session_state.user_id,
                st.session_state.user_email,
            )
        return
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.token_expiry = 0
    st.session_state.remember_me_active = False


def sign_up(email: str, password: str) -> Tuple[bool, str, Optional[str]]:
    """用户注册 - 创建Auth用户 + racing.user_settings记录"""
    try:
        url = f"{SUPABASE_URL}/auth/v1/signup"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json"
        }
        data = {"email": email, "password": password}
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            resp_data = response.json()
            user_id = resp_data.get("user", {}).get("id")
            
            if user_id:
                # 创建 racing.user_settings 记录
                settings_data = {
                    "user_id": user_id,
                    "email": email,
                    "subscription_tier": "free",
                    "free_trials_remaining": FREE_TRIAL_LIMIT,
                    "weights_basic": DEFAULT_WEIGHTS["basic"],
                    "weights_race": DEFAULT_WEIGHTS["race"],
                    "weights_odds": DEFAULT_WEIGHTS["odds"],
                    "temperature": DEFAULT_WEIGHTS["temperature"],
                    "odds_mix_ratio": DEFAULT_WEIGHTS["odds_mix_ratio"]
                }
                headers_secret = get_supabase_headers(use_secret=True)
                insert_url = f"{SUPABASE_URL}/rest/v1/user_settings_racing"
                insert_response = requests.post(insert_url, headers=headers_secret, json=settings_data)
                
                if insert_response.status_code in [200, 201]:
                    return True, t()["register_success"], user_id
                else:
                    # 即使 user_settings 创建失败，也允许登录（后续会自动创建）
                    print(f"创建user_settings失败: {insert_response.text}")
                    return True, t()["register_success"], user_id
            return True, t()["register_success"], user_id
        else:
            error = response.json()
            if "User already registered" in str(error):
                # 用户已存在，尝试为其创建 racing.user_settings 记录
                # 先通过邮箱查找用户
                admin_url = f"{SUPABASE_URL}/auth/v1/admin/users"
                admin_headers = get_supabase_headers(use_secret=True)
                admin_response = requests.get(admin_url, headers=admin_headers)
                
                if admin_response.status_code == 200:
                    users = admin_response.json().get("users", [])
                    for user in users:
                        if user.get("email") == email:
                            user_id = user.get("id")
                            # 检查是否已有 racing.user_settings 记录
                            check_url = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
                            check_response = requests.get(check_url, headers=admin_headers)
                            
                            if check_response.status_code == 200 and not check_response.json():
                                # 没有记录，创建
                                settings_data = {
                                    "user_id": user_id,
                                    "email": email,
                                    "subscription_tier": "free",
                                    "free_trials_remaining": FREE_TRIAL_LIMIT,
                                    "weights_basic": DEFAULT_WEIGHTS["basic"],
                                    "weights_race": DEFAULT_WEIGHTS["race"],
                                    "weights_odds": DEFAULT_WEIGHTS["odds"],
                                    "temperature": DEFAULT_WEIGHTS["temperature"],
                                    "odds_mix_ratio": DEFAULT_WEIGHTS["odds_mix_ratio"]
                                }
                                insert_url = f"{SUPABASE_URL}/rest/v1/user_settings_racing"
                                requests.post(insert_url, headers=admin_headers, json=settings_data)
                            
                            return True, t()["email_exists_login"], user_id
                return False, t()["email_exists"], None
            return False, f"{t()['register_failed']}: {error.get('msg', 'unknown')}", None
    except Exception as e:
        return False, f"{t()['register_failed']}: {str(e)}", None
#--------------
def sign_in(email: str, password: str) -> Tuple[bool, str, Optional[str], Optional[str], Optional[str], Optional[str]]:
    """用户登录 - 最终修正版"""
    try:
        # 1. Auth 登录
        url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json"
        }
        data = {"email": email, "password": password}
        response = requests.post(url, headers=headers, json=data)
        
        print(f"Auth 状态码: {response.status_code}")
        
        if response.status_code != 200:
            return False, t()["wrong_email_password"], None, None, None, None
        
        resp_data = response.json()
        user_id = resp_data.get("user", {}).get("id")
        user_email = resp_data.get("user", {}).get("email")
        access_token = resp_data.get("access_token")
        refresh_token = resp_data.get("refresh_token")
        
        print(f"用户ID: {user_id}")
        
        # 2. 使用用户的 access_token 查询 user_settings
        user_headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        check_url = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
        check_response = requests.get(check_url, headers=user_headers)
        
        print(f"查询 user_settings 状态码: {check_response.status_code}")
        print(f"查询结果: {check_response.text}")
        
        if check_response.status_code == 200 and check_response.json():
            return True, t()["login_success"], user_id, user_email, access_token, refresh_token
        else:
            # 没有记录，尝试自动创建
            # 注意：POST 请求需要添加 Prefer 头
            insert_headers = {
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"  # 关键！
            }
            
            settings_data = {
                "user_id": user_id,
                "email": user_email,
                "subscription_tier": "free",
                "free_trials_remaining": FREE_TRIAL_LIMIT,
                "weights_basic": DEFAULT_WEIGHTS["basic"],
                "weights_race": DEFAULT_WEIGHTS["race"],
                "weights_odds": DEFAULT_WEIGHTS["odds"],
                "temperature": DEFAULT_WEIGHTS["temperature"],
                "odds_mix_ratio": DEFAULT_WEIGHTS["odds_mix_ratio"]
            }
            
            insert_url = f"{SUPABASE_URL}/rest/v1/user_settings_racing"
            insert_response = requests.post(insert_url, headers=insert_headers, json=settings_data)
            
            print(f"创建 user_settings 状态码: {insert_response.status_code}")
            print(f"创建结果: {insert_response.text}")
            
            if insert_response.status_code in [200, 201]:
                return True, t()["login_success"], user_id, user_email, access_token, refresh_token
            else:
                return False, f"{t()['create_settings_failed']}: {insert_response.text}", None, None, None, None
                
    except Exception as e:
        print(f"登录异常: {e}")
        return False, f"{t()['login_failed']}: {str(e)}", None, None, None, None

def sign_out():
    """退出登录"""
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.token_expiry = 0
    st.session_state.remember_me_active = False
    st.session_state.admin_mode = False
    clear_persisted_remember_me_auth()
    clear_persisted_admin_session()
    st.rerun()
#--------
def refresh_auth_token() -> Optional[str]:
    """使用 refresh_token 刷新 access_token"""
    refresh_token = st.session_state.get("refresh_token")
    if not refresh_token:
        print("❌ 无 refresh_token，无法刷新")
        return None
    
    try:
        url = f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json"
        }
        data = {"refresh_token": refresh_token}
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            resp_data = response.json()
            st.session_state.access_token = resp_data["access_token"]
            st.session_state.refresh_token = resp_data["refresh_token"]
            st.session_state.token_expiry = time.time() + resp_data.get("expires_in", 3600)
            print("✅ 令牌刷新成功")
            return resp_data["access_token"]
        else:
            print(f"❌ 刷新令牌失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ 刷新令牌异常: {e}")
        return None
#---------
def _profile_cache_key(user_id: str) -> str:
    return f"user_profile_cache_{user_id}"


def _cache_user_profile(user_id: str, profile: Dict) -> None:
    st.session_state[_profile_cache_key(user_id)] = profile


def _default_user_profile(free_trials_remaining: int = 0) -> Dict:
    return {
        "subscription_tier": "free",
        "free_trials_remaining": free_trials_remaining,
        "subscription_expires_at": None,
        "weights_basic": DEFAULT_WEIGHTS["basic"],
        "weights_race": DEFAULT_WEIGHTS["race"],
        "weights_odds": DEFAULT_WEIGHTS["odds"],
        "temperature": DEFAULT_WEIGHTS["temperature"],
        "odds_mix_ratio": DEFAULT_WEIGHTS["odds_mix_ratio"],
        "risk_preference": "standard",
        "default_bankroll": 1000,
    }


def get_user_profile(user_id: str, *, force_refresh: bool = False) -> Dict:
    """获取用户资料（会话内缓存；读失败时不回退为 30 次）"""
    if not user_id or user_id == "admin":
        profile = _default_user_profile(free_trials_remaining=FREE_TRIAL_LIMIT)
        profile["subscription_tier"] = "pro"
        return profile

    cache_key = _profile_cache_key(user_id)
    if not force_refresh and cache_key in st.session_state:
        return st.session_state[cache_key]

    try:
        access_token = st.session_state.get("access_token", "")
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        url = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
        response = requests.get(url, headers=headers)

        if response.status_code == 401:
            if refresh_auth_token():
                return get_user_profile(user_id, force_refresh=True)

        if response.status_code == 200 and response.json():
            data = response.json()[0]
            remaining_raw = data.get("free_trials_remaining")
            try:
                remaining = int(remaining_raw) if remaining_raw is not None else 0
            except (TypeError, ValueError):
                remaining = 0
            profile = {
                "subscription_tier": data.get("subscription_tier", "free"),
                "free_trials_remaining": remaining,
                "subscription_expires_at": data.get("subscription_expires_at"),
                "weights_basic": data.get("weights_basic", DEFAULT_WEIGHTS["basic"]),
                "weights_race": data.get("weights_race", DEFAULT_WEIGHTS["race"]),
                "weights_odds": data.get("weights_odds", DEFAULT_WEIGHTS["odds"]),
                "temperature": data.get("temperature", DEFAULT_WEIGHTS["temperature"]),
                "odds_mix_ratio": data.get("odds_mix_ratio", DEFAULT_WEIGHTS["odds_mix_ratio"]),
                "risk_preference": data.get("risk_preference", "standard"),
                "default_bankroll": data.get("default_bankroll", 1000),
            }
            _cache_user_profile(user_id, profile)
            return profile
    except Exception as e:
        print(f"获取用户资料失败: {e}")

    if cache_key in st.session_state:
        return st.session_state[cache_key]
    return _default_user_profile(free_trials_remaining=0)
#-------------
def update_user_profile(user_id: str, data: Dict) -> bool:
    """更新用户资料（支持令牌过期后自动刷新重试）"""
    try:
        access_token = st.session_state.get("access_token", "")
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        url = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
        response = requests.patch(url, headers=headers, json=data)
        
        print(f"update_user_profile - 状态码: {response.status_code}")
        
        # ⭐ 如果令牌过期，刷新并重试一次
        if response.status_code == 401:
            print("🔄 令牌过期，尝试刷新...")
            new_token = refresh_auth_token()
            if new_token:
                # 使用新令牌重试
                headers["Authorization"] = f"Bearer {new_token}"
                retry_response = requests.patch(url, headers=headers, json=data)
                print(f"update_user_profile - 重试状态码: {retry_response.status_code}")
                return retry_response.status_code in [200, 204]
            else:
                print("❌ 刷新令牌失败，请重新登录")
                # 清除失效的认证状态
                st.session_state.authenticated = False
                st.session_state.access_token = None
                st.session_state.refresh_token = None
                st.session_state.remember_me_active = False
                clear_persisted_remember_me_auth()
                st.warning(t()["session_expired"])
                return False
        
        return response.status_code in [200, 204]
        
    except Exception as e:
        print(f"更新用户资料失败: {e}")
        return False

def get_remaining_trials(user_id: str) -> int:
    """获取剩余免费次数"""
    profile = get_user_profile(user_id)
    if profile.get("subscription_tier") == "pro":
        return -1  # -1表示无限
    return profile.get("free_trials_remaining", 0)
#----------------
def consume_free_trial(user_id: str, silent: bool = True) -> bool:
    """扣减 1 次免费试用；silent=True 时不提示，用尽时仅触发升级弹窗。"""
    if user_id == "admin":
        return True
    profile = get_user_profile(user_id)
    if profile.get("subscription_tier") == "pro":
        return True
    remaining = profile.get("free_trials_remaining", 0)
    try:
        remaining = int(remaining)
    except (ValueError, TypeError):
        remaining = 0
    if remaining > 0:
        new_remaining = remaining - 1
        success = update_user_profile(user_id, {"free_trials_remaining": new_remaining})
        if success:
            updated = dict(profile)
            updated["free_trials_remaining"] = new_remaining
            _cache_user_profile(user_id, updated)
        elif not silent:
            st.error(t()["trial_update_failed"])
        return success
    st.session_state.show_paywall = True
    return False


def require_trial(action_key: str, *, dedupe: bool = True, user_id: Optional[str] = None) -> bool:
    """检查并扣减试用次数；dedupe=True 时同一会话同一 action_key 只扣一次。"""
    uid = user_id or st.session_state.get("user_id")
    if not uid or uid == "admin":
        return True
    profile = get_user_profile(uid)
    if profile.get("subscription_tier") == "pro":
        return True
    charged = st.session_state.setdefault("trial_charged_actions", set())
    if dedupe and action_key in charged:
        return True
    if not consume_free_trial(uid, silent=True):
        return False
    if dedupe:
        charged.add(action_key)
    return True


def trial_gated_checkbox(label: str, checkbox_key: str, trial_key: str) -> bool:
    """勾选时静默扣次；次数用尽则取消勾选并弹出升级。"""
    def _on_toggle() -> None:
        if st.session_state.get(checkbox_key):
            if not require_trial(trial_key):
                st.session_state[checkbox_key] = False

    st.checkbox(label, key=checkbox_key, on_change=_on_toggle)
    if not st.session_state.get(checkbox_key):
        return False
    return require_trial(trial_key)


def _section_unlock_key(state_key: str) -> str:
    return f"unlocked_{state_key}"


def _section_anchor_id(state_key: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", state_key)
    return f"sec_{safe}"


def _scroll_to_section_anchor(state_key: str) -> None:
    """展開後滾動到區塊標題，保留標題在視口內。"""
    flag = f"scroll_to_{state_key}"
    if not st.session_state.pop(flag, False):
        return
    anchor_id = _section_anchor_id(state_key)
    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        (function() {{
            function tryScroll() {{
                const doc = window.parent.document;
                const el = doc.getElementById("{anchor_id}");
                if (!el) return false;
                el.scrollIntoView({{behavior: "smooth", block: "nearest", inline: "nearest"}});
                return true;
            }}
            let n = 0;
            const timer = setInterval(function() {{
                if (tryScroll() || ++n > 30) clearInterval(timer);
            }}, 150);
        }})();
        </script>
        """,
        height=0,
    )


def _render_section_header_row(
    title: str,
    anchor_id: str,
    *,
    use_heading: bool = True,
) -> None:
    st.markdown(
        f'<div id="{anchor_id}" style="scroll-margin-top: 5rem;"></div>',
        unsafe_allow_html=True,
    )
    if use_heading:
        st.markdown(f"#### {title}")
    else:
        st.markdown(f"**{title}**")


def render_collapsible_trial_section(
    title: str,
    state_key: str,
    trial_key: str,
    render_content: Callable[[], None],
    *,
    expand_label: Optional[str] = None,
    use_heading: bool = True,
    show_expand_hint: bool = False,
) -> None:
    """可折疊區塊：標題始終可見；收起/展開按鈕緊挨標題。"""
    unlock_key = _section_unlock_key(state_key)
    expanded = bool(st.session_state.get(state_key))
    unlocked = bool(st.session_state.get(unlock_key))
    anchor_id = _section_anchor_id(state_key)
    expand_hint = expand_label if expand_label and expand_label != title else None

    def _mark_scroll() -> None:
        st.session_state[f"scroll_to_{state_key}"] = True

    def _collapse() -> None:
        st.session_state[state_key] = False

    def _reopen() -> None:
        st.session_state[state_key] = True
        _mark_scroll()

    def _first_open() -> None:
        if require_trial(trial_key):
            st.session_state[state_key] = True
            st.session_state[unlock_key] = True
            _mark_scroll()

    title_col, btn_col, _spacer = st.columns([6, 1.4, 4.6], vertical_alignment="center")
    with title_col:
        _render_section_header_row(title, anchor_id, use_heading=use_heading)
        if expand_hint and not expanded:
            st.caption(expand_hint)
        elif show_expand_hint and not expanded and not unlocked:
            st.caption(t()["click_open"])

    with btn_col:
        if expanded:
            st.button(
                t()["collapse_section"],
                key=f"collapse_{state_key}",
                on_click=_collapse,
                use_container_width=True,
            )
        elif unlocked:
            st.button(
                t()["reopen_section"],
                key=f"reopen_{state_key}",
                on_click=_reopen,
                use_container_width=True,
            )
        else:
            st.button(
                t()["expand_section_short"],
                key=f"trial_btn_{state_key}",
                on_click=_first_open,
                use_container_width=True,
            )

    if expanded:
        render_content()
        _scroll_to_section_anchor(state_key)


def trial_gated_toggle_button(
    label: str,
    state_key: str,
    trial_key: str,
    *,
    hint: Optional[str] = None,
    primary: bool = False,
    show_hint: bool = True,
) -> bool:
    """按鈕式開關：首次點擊静默扣次並展開內容；已展開時不再顯示按鈕。"""
    if st.session_state.get(state_key):
        return True

    def _on_open() -> None:
        if require_trial(trial_key):
            st.session_state[state_key] = True
            st.session_state[_section_unlock_key(state_key)] = True

    if show_hint:
        st.caption(hint or t()["click_open"])
    btn_type = "primary" if primary else "secondary"
    st.button(
        label,
        key=f"trial_btn_{state_key}",
        use_container_width=True,
        type=btn_type,
        on_click=_on_open,
    )
    return False


def _render_ai_strategy_recommendation_sections(
    current_race_key: str,
    recommendations: Dict,
    sorted_runners: List[Dict],
) -> None:
    """各推薦區塊固定順序渲染：展開內容替換同位置按鈕，避免點擊後頁面跳轉。"""
    sections = [
        {
            "label": t()["win_place_recommend"],
            "state_key": f"show_win_rec_{current_race_key}",
            "trial_key": f"rec_win:{current_race_key}",
        },
        {
            "label": t()["qin_recommend_expander"],
            "state_key": f"show_qin_rec_{current_race_key}",
            "trial_key": f"rec_qin:{current_race_key}",
        },
        {
            "label": t()["tri_recommend_expander"],
            "state_key": f"show_tri_rec_{current_race_key}",
            "trial_key": f"rec_tri:{current_race_key}",
        },
        {
            "label": t()["tce_recommend_expander"],
            "state_key": f"show_tce_rec_{current_race_key}",
            "trial_key": f"rec_tce:{current_race_key}",
        },
    ]

    def _render_win_place_body() -> None:
        if recommendations.get("win") and recommendations["win"]:
            rec = recommendations["win"][0]
            st.info(f"**{rec.description}**")
            st.write(f"{t()['win_odds_label']}: {rec.odds:.1f}x")
            st.write(f"{t()['expected_roi_label']}: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        elif recommendations.get("place") and recommendations["place"]:
            rec = recommendations["place"][0]
            st.info(f"**{rec.description}**")
            st.write(f"{t()['place_odds_label']}: {rec.odds:.1f}x")
            st.write(f"{t()['expected_roi_label']}: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        else:
            st.write(t()["no_suggestions"])

    renderers = [
        _render_win_place_body,
        lambda: _render_qin_suggestions(sorted_runners, key_prefix="qin_fold"),
        lambda: _render_tri_suggestions(sorted_runners),
        lambda: _render_tce_suggestions(sorted_runners),
    ]

    any_open = any(st.session_state.get(section["state_key"]) for section in sections)
    if not any_open:
        st.caption(t()["click_open_recommend"])

    for section, render_body in zip(sections, renderers):
        render_collapsible_trial_section(
            section["label"],
            section["state_key"],
            section["trial_key"],
            render_body,
            expand_label=section["label"],
        )
        st.markdown("")


def _render_paywall_content() -> None:
    """Paywall body (used in dialog and legacy full-page view)."""
    profile = get_user_profile(st.session_state.user_id)
    remaining = profile.get("free_trials_remaining", 0)
    tier = profile.get("subscription_tier", "free")

    if tier == "pro":
        st.session_state.show_paywall = False
        st.rerun()
        return

    if remaining > 0:
        st.info(t()["paywall_trials_remaining"].format(remaining=remaining))
        st.warning(t()["paywall_upgrade_hint"])
    else:
        st.error(t()["free_trial_used"])

    st.markdown(f"""
    ### 💎 {t()['upgrade']}

    | {t()['paywall_feature']} | {t()['paywall_free']} | {t()['paywall_pro']} |
    |------|--------|--------|
    | {t()['paywall_usage']} | {t()['paywall_usage_free']} | **{t()['unlimited']}** |
    | {t()['paywall_horse_rating']} | ✅ | ✅ |
    | {t()['paywall_smart_betting']} | ✅ | ✅ |
    | {t()['paywall_full_day']} | ✅ | ✅ |
    | {t()['paywall_backtest']} | ✅ | ✅ |
    """)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(t()["monthly"], key="paywall_monthly_btn", use_container_width=True):
            url, error = create_checkout_session(
                st.session_state.user_id,
                st.session_state.user_email,
                STRIPE_PRICE_MONTHLY,
            )
            if url:
                st.session_state.payment_url = url
                st.session_state.payment_type = "monthly"
                st.rerun()
            else:
                st.error(f"{t()['checkout_session_failed']}: {error}")

        if st.session_state.get("payment_url") and st.session_state.get("payment_type") == "monthly":
            st.markdown(
                f'''
            <a href="{st.session_state.payment_url}" target="_blank" style="
                display: block;
                width: 100%;
                padding: 0.6rem;
                background-color: #ff4b4b;
                color: white;
                text-align: center;
                text-decoration: none;
                border-radius: 0.5rem;
                font-weight: bold;
                margin-top: 0.5rem;">
                {t()['checkout_go_stripe_monthly']}
            </a>
            ''',
                unsafe_allow_html=True,
            )

    with col2:
        if st.button(t()["quarterly"], key="paywall_quarterly_btn", use_container_width=True):
            url, error = create_checkout_session(
                st.session_state.user_id,
                st.session_state.user_email,
                STRIPE_PRICE_QUARTERLY,
            )
            if url:
                st.session_state.payment_url = url
                st.session_state.payment_type = "quarterly"
                st.rerun()
            else:
                st.error(f"{t()['checkout_session_failed']}: {error}")

        if st.session_state.get("payment_url") and st.session_state.get("payment_type") == "quarterly":
            st.markdown(
                f'''
            <a href="{st.session_state.payment_url}" target="_blank" style="
                display: block;
                width: 100%;
                padding: 0.6rem;
                background-color: #ff4b4b;
                color: white;
                text-align: center;
                text-decoration: none;
                border-radius: 0.5rem;
                font-weight: bold;
                margin-top: 0.5rem;">
                {t()['checkout_go_stripe_quarterly']}
            </a>
            ''',
                unsafe_allow_html=True,
            )


def maybe_show_paywall_dialog() -> None:
    """Show upgrade pop-up when free trials are exhausted or user clicks upgrade."""
    if not st.session_state.get("show_paywall", False):
        return

    @st.dialog(t()["upgrade_pro"], width="large")
    def _paywall_dialog():
        _render_paywall_content()
        if st.button(t()["back"], key="paywall_dialog_close", use_container_width=True):
            st.session_state.show_paywall = False
            st.session_state.payment_url = None
            st.rerun()

    _paywall_dialog()


# ==================== Stripe支付 ====================
def create_checkout_session(user_id: str, user_email: str, price_id: str) -> Tuple[Optional[str], Optional[str]]:
    """创建Stripe Checkout Session"""
    if not STRIPE_SECRET_KEY:
        return None, t()["stripe_not_configured"]
    
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        
        # 使用您的实际 Streamlit Cloud 地址
        base_url = "https://share.streamlit.io/laurenceku2026/horse-racing/main/racing_app.py"
        
        success_url = f"{base_url}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}?canceled=true"
        
        session = stripe.checkout.Session.create(
            customer_email=user_email,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={'user_id': user_id, 'price_id': price_id}
        )
        return session.url, None
    except Exception as e:
        return None, str(e)
#--------------
def handle_stripe_callback():
    """使用 HTTP 请求验证 Stripe 支付（不依赖 stripe 库）"""
    import requests
    import base64
    import json
    
    query_params = st.query_params
    
    if "session_id" in query_params:
        session_id = query_params["session_id"]
        
        # 显示手动验证按钮
        st.warning(t()["stripe_session_detected"])
        st.info(f"{t()['stripe_session_id']}: {session_id[:30]}...")
        
        if st.button(t()["stripe_verify_button"], type="primary"):
            with st.spinner(t()["stripe_verifying"]):
                try:
                    # 使用 Basic 认证调用 Stripe API
                    auth_str = f"{STRIPE_SECRET_KEY}:"
                    auth_bytes = auth_str.encode('ascii')
                    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
                    
                    headers = {
                        "Authorization": f"Basic {auth_b64}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                    
                    url = f"https://api.stripe.com/v1/checkout/sessions/{session_id}"
                    response = requests.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if data.get("payment_status") == "paid":
                            # 从 metadata 获取用户信息
                            user_id = data.get("metadata", {}).get("user_id")
                            user_email = data.get("customer_email") or data.get("metadata", {}).get("user_email")
                            
                            # 如果没有 user_id，通过邮箱查找用户
                            if not user_id and user_email:
                                headers_secret = get_supabase_headers(use_secret=True)
                                url_users = f"{SUPABASE_URL}/rest/v1/user_settings_racing?email=eq.{user_email}"
                                users_resp = requests.get(url_users, headers=headers_secret)
                                if users_resp.status_code == 200 and users_resp.json():
                                    user_id = users_resp.json()[0].get("user_id")
                            
                            if user_id and user_id != "admin":
                                # 更新数据库
                                headers_patch = get_supabase_headers(use_secret=True)
                                url_patch = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
                                patch_response = requests.patch(
                                    url_patch, 
                                    headers=headers_patch, 
                                    json={"subscription_tier": "pro"}
                                )
                                
                                if patch_response.status_code in [200, 204]:
                                    st.success(t()["stripe_verify_success"])
                                    st.balloons()
                                    # 更新 session state
                                    if st.session_state.get("user_id") == user_id:
                                        st.session_state.user_tier = "pro"
                                        # 清除付费墙标志
                                        st.session_state.show_paywall = False
                                    st.query_params.clear()
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error(f"{t()['update_failed_msg']}: {patch_response.text}")
                            else:
                                st.error(t()["stripe_user_not_found"])
                        else:
                            st.warning(f"{t()['stripe_payment_incomplete']}: {data.get('payment_status')}")
                    else:
                        st.error(f"{t()['stripe_api_failed']}: {response.status_code}")
                        
                except Exception as e:
                    st.error(f"{t()['stripe_verify_failed']}: {e}")
    elif "canceled" in query_params:
        st.info(t()["stripe_payment_cancelled"])
#------------
def show_paywall():
    """Legacy full-page paywall wrapper."""
    st.markdown("---")
    _render_paywall_content()
    if st.button(t()["back"], key="paywall_page_back", use_container_width=True):
        st.session_state.show_paywall = False
        st.session_state.payment_url = None
        st.rerun()

# ==================== 管理员函数 ====================
def check_admin_login(username: str, password: str) -> bool:
    """验证管理员登录"""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD
#---------------
def get_all_users() -> List[Dict]:
    """获取当前 App（racing）的用户列表"""
    try:
        headers = get_supabase_headers(use_secret=True)
        # 只查询 app_id = 'racing' 的用户（如果表有 app_id 字段）
        # 如果表没有 app_id 字段，则查询所有用户（因为 racing 和 stock 的表已经分开）
        url = f"{SUPABASE_URL}/rest/v1/user_settings_racing"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            users = response.json()
            # 确保每个用户都有基本字段
            for user in users:
                if 'subscription_tier' not in user:
                    user['subscription_tier'] = 'free'
                if 'free_trials_remaining' not in user:
                    user['free_trials_remaining'] = FREE_TRIAL_LIMIT
            return users
        print(f"获取用户列表失败: {response.status_code} - {response.text}")
        return []
    except Exception as e:
        print(f"获取用户列表失败: {e}")
        return []

def admin_reset_user_trials(user_id: str, new_trials: int) -> Tuple[bool, str]:
    """重置用户免费次数"""
    try:
        success = update_user_profile(user_id, {"free_trials_remaining": new_trials})
        if success:
            return True, f"已重置免費次數為 {new_trials}"
        return False, "重置失敗"
    except Exception as e:
        return False, f"重置失敗: {str(e)}"

def admin_set_subscription(user_id: str, tier: str, months: int = 1) -> Tuple[bool, str]:
    """设置用户订阅等级"""
    try:
        data = {"subscription_tier": tier}
        if tier == "pro":
            expires_at = (datetime.now() + timedelta(days=30 * months)).isoformat()
            data["subscription_expires_at"] = expires_at
        else:
            data["subscription_expires_at"] = None
        
        success = update_user_profile(user_id, data)
        if success:
            return True, f"用戶訂閱已設置為 {tier}"
        return False, "設置失敗"
    except Exception as e:
        return False, f"設置失敗: {str(e)}"

# ==================== 登录/注册UI ====================
def render_login_form():
    """显示登录表单"""
    st.markdown(
        f"<div class='auth-header-wrap'><h1 class='auth-title'>{t()['app_title']}</h1></div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        with st.form("login_form", border=False):
            email = st.text_input(t()["email"], key="login_email")
            password = st.text_input(t()["password"], type="password", key="login_password")
            remember_me = st.checkbox(t()["remember_me"], value=True, key="login_remember_me")
            submitted = st.form_submit_button(t()["login_btn"], type="primary", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.warning(t()["fill_email_password"])
                else:
                    with st.spinner(t()["logging_in"]):
                        success, msg, user_id, user_email, access_token, refresh_token = sign_in(email, password)
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user_id = user_id
                            st.session_state.user_email = user_email
                            st.session_state.access_token = access_token
                            st.session_state.refresh_token = refresh_token
                            st.session_state.token_expiry = time.time() + 3600
                            st.session_state.remember_me_active = bool(remember_me)
                            st.session_state.show_paywall = False
                            st.session_state.home_section_nav = t()["nav_smart_betting"]
                            if remember_me:
                                persist_remember_me_auth(refresh_token, user_id, user_email)
                            else:
                                clear_persisted_remember_me_auth()
                            st.rerun()
                        else:
                            st.error(msg)

    if st.button(t()["register"], use_container_width=True, key="login_go_register", type="secondary"):
        st.session_state.show_register = True
        st.rerun()
    if st.button(t().get("forgot_password", "Forgot Password?"), use_container_width=True, key="login_forgot", type="secondary"):
        st.info(f"{t()['contact_admin_reset_password']}: {ADMIN_EMAIL}")

def render_register_form():
    """显示注册表单"""
    st.markdown(
        f"<div class='auth-header-wrap'><h2 class='auth-title'>{t()['register']}</h2></div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        with st.form("register_form", border=False):
            email = st.text_input(t()["email"], key="reg_email")
            password = st.text_input(t()["password"], type="password", key="reg_password")
            confirm = st.text_input(t()["confirm_password"], type="password", key="reg_confirm")
            submitted = st.form_submit_button(t()["register_btn"], type="primary", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.warning(t()["fill_email_password"])
                elif password != confirm:
                    st.warning(t()["password_mismatch"])
                elif len(password) < 6:
                    st.warning(t()["password_min_length"])
                else:
                    with st.spinner(t()["registering"]):
                        success, msg, user_id = sign_up(email, password)
                        if success:
                            st.success(msg)
                            st.session_state.show_register = False
                            st.rerun()
                        else:
                            st.error(msg)

    if st.button(t()["back_to_login"], use_container_width=True, type="secondary"):
        st.session_state.show_register = False
        st.rerun()

def render_admin_login_form():
    """显示管理员登录表单"""
    st.markdown(
        f"<div class='auth-header-wrap'><h2 class='auth-title'>{t()['admin_login_title']}</h2></div>",
        unsafe_allow_html=True,
    )

    with st.form("admin_login_form", border=True):
        username = st.text_input(t()["admin_username"], key="admin_username")
        password = st.text_input(t()["password"], type="password", key="admin_password")
        submitted = st.form_submit_button(t()["admin_login_btn"], type="primary", use_container_width=True)

        if submitted:
            if check_admin_login(username, password):
                st.session_state.admin_previous_user_id = st.session_state.get("user_id")
                st.session_state.admin_previous_user_email = st.session_state.get("user_email")
                st.session_state.admin_previous_access_token = st.session_state.get("access_token")
                st.session_state.admin_previous_refresh_token = st.session_state.get("refresh_token")

                persist_admin_session()
                activate_admin_mode(preserve_user=False)
                st.rerun()
            else:
                st.error(t()["admin_login_failed"])

    if st.button(t()["back_to_user_login"], use_container_width=True):
        st.session_state.show_admin_login = False
        st.rerun()

#---------------
def get_table_data(table_name: str, limit: int = 500) -> List[Dict]:
    """获取表数据（确保包含 id 字段）"""
    try:
        headers = get_supabase_headers(use_secret=True)
        # ⭐ 显式选择 id 字段
        url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*&order=race_date.desc&limit={limit}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"获取表数据失败: {e}")
        return []

#-------------
def save_table_data(table_name: str, data: List[Dict]) -> bool:
    """
    全量覆盖保存表数据
    注意：此操作会删除表中的所有数据，然后插入新数据
    """
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 1. 先清空表（使用 DELETE 而非 TRUNCATE，避免权限问题）
        delete_url = f"{SUPABASE_URL}/rest/v1/{table_name}"
        delete_params = ""  # 删除所有记录
        delete_response = requests.delete(delete_url, headers=headers, params=delete_params)
        
        if delete_response.status_code not in [200, 204]:
            print(f"清空表失败: {delete_response.status_code} - {delete_response.text}")
            return False
        
        print(f"已清空表 {table_name}")
        
        # 2. 批量插入新数据（分批插入，避免单次请求过大）
        batch_size = 100
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            
            # 清理每条记录中的 None 值和空字符串
            clean_batch = []
            for record in batch:
                clean_record = {}
                for k, v in record.items():
                    # 跳过 id（让数据库自动生成）
                    if k == 'id':
                        continue
                    # 处理空值
                    if v is None or v == '':
                        clean_record[k] = None
                    else:
                        clean_record[k] = v
                clean_batch.append(clean_record)
            
            insert_response = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table_name}",
                headers=headers,
                json=clean_batch
            )
            
            if insert_response.status_code not in [200, 201]:
                print(f"批量插入失败 (批次 {i//batch_size + 1}): {insert_response.status_code} - {insert_response.text}")
                return False
            
            print(f"批量插入成功: {len(clean_batch)} 条记录")
        
        # 3. 清除缓存，确保数据概览更新
        st.cache_data.clear()
        
        return True
        
    except Exception as e:
        print(f"保存失败: {e}")
        return False

#---------------
def incremental_sync_table(table_name: str, new_data: List[Dict]) -> Dict:
    """
    增量同步表数据（修复版）
    - 支持删除、更新、插入
    - 自动处理 ID 类型转换
    - 保存后清除缓存
    """
    result = {"inserted": 0, "updated": 0, "deleted": 0}
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # ==================== 1. 获取现有数据 ====================
        existing = get_table_data(table_name, limit=10000)
        
        # 提取现有 ID（统一转为字符串比较）
        existing_ids = set()
        existing_records_by_id = {}  # 用于快速查找
        for r in existing:
            rid = r.get('id')
            if rid is not None:
                rid_str = str(rid)
                existing_ids.add(rid_str)
                existing_records_by_id[rid_str] = r
        
        # 提取新数据的 ID（统一转为字符串）
        new_ids = set()
        new_records_by_id = {}
        for r in new_data:
            rid = r.get('id')
            if rid is not None and rid != '':
                rid_str = str(rid)
                new_ids.add(rid_str)
                new_records_by_id[rid_str] = r
            else:
                # 没有 ID 的记录视为新增
                new_records_by_id[f"new_{len(new_records_by_id)}"] = r
        
        print(f"现有记录数: {len(existing_ids)}, 新记录数: {len(new_ids)}")
        
        # ==================== 2. 计算差异 ====================
        # 需要删除的（在旧数据中但不在新数据中）
        to_delete = existing_ids - new_ids
        # 需要新增的（在新数据中但不在旧数据中）
        to_insert = new_ids - existing_ids
        # 需要更新的（两边都有，内容可能变化）
        to_update = existing_ids & new_ids
        
        print(f"需要删除: {len(to_delete)} 条")
        print(f"需要更新: {len(to_update)} 条")
        print(f"需要新增: {len(to_insert)} 条")
        
        # ==================== 3. 执行删除 ====================
        for record_id in to_delete:
            try:
                delete_url = f"{SUPABASE_URL}/rest/v1/{table_name}?id=eq.{record_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                if delete_response.status_code in [200, 204]:
                    result["deleted"] += 1
                else:
                    print(f"删除失败 {record_id}: {delete_response.status_code} - {delete_response.text}")
            except Exception as e:
                print(f"删除异常 {record_id}: {e}")
        
        # ==================== 4. 执行更新 ====================
        for record_id in to_update:
            try:
                new_record = new_records_by_id.get(record_id)
                if not new_record:
                    continue
                
                # 清理记录：移除 None 值和空字符串
                clean_record = {}
                for k, v in new_record.items():
                    # 跳过 id（不让更新 id）
                    if k == 'id':
                        continue
                    if v is None or v == '':
                        clean_record[k] = None
                    else:
                        clean_record[k] = v
                
                # 检查是否有实际变化（可选优化）
                old_record = existing_records_by_id.get(record_id, {})
                has_change = False
                for k in clean_record:
                    if str(old_record.get(k)) != str(clean_record[k]):
                        has_change = True
                        break
                
                if not has_change:
                    # 无变化，跳过
                    continue
                
                update_url = f"{SUPABASE_URL}/rest/v1/{table_name}?id=eq.{record_id}"
                update_response = requests.patch(update_url, headers=headers, json=clean_record)
                if update_response.status_code in [200, 204]:
                    result["updated"] += 1
                else:
                    print(f"更新失败 {record_id}: {update_response.status_code} - {update_response.text}")
            except Exception as e:
                print(f"更新异常 {record_id}: {e}")
        
        # ==================== 5. 执行新增 ====================
        for record_id in to_insert:
            try:
                new_record = new_records_by_id.get(record_id)
                if not new_record:
                    continue
                
                # 清理记录：移除 id（让数据库自动生成）和 None 值
                clean_record = {}
                for k, v in new_record.items():
                    if k == 'id':
                        continue
                    if v is None or v == '':
                        clean_record[k] = None
                    else:
                        clean_record[k] = v
                
                insert_response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/{table_name}",
                    headers=headers,
                    json=clean_record
                )
                if insert_response.status_code in [200, 201]:
                    result["inserted"] += 1
                else:
                    print(f"新增失败: {insert_response.status_code} - {insert_response.text}")
            except Exception as e:
                print(f"新增异常: {e}")
        
        # ==================== 6. 处理无 ID 的新记录 ====================
        # 查找没有 ID 的记录（纯新增）
        for key, new_record in new_records_by_id.items():
            if key.startswith("new_"):  # 这是我们标记的无 ID 记录
                try:
                    clean_record = {}
                    for k, v in new_record.items():
                        if k == 'id':
                            continue
                        if v is None or v == '':
                            clean_record[k] = None
                        else:
                            clean_record[k] = v
                    
                    insert_response = requests.post(
                        f"{SUPABASE_URL}/rest/v1/{table_name}",
                        headers=headers,
                        json=clean_record
                    )
                    if insert_response.status_code in [200, 201]:
                        result["inserted"] += 1
                    else:
                        print(f"新增失败 (无ID): {insert_response.status_code}")
                except Exception as e:
                    print(f"新增异常 (无ID): {e}")
        
        # ==================== 7. 清除缓存，确保数据概览更新 ====================
        st.cache_data.clear()
        
        print(f"增量同步完成: 新增 {result['inserted']}, 更新 {result['updated']}, 删除 {result['deleted']}")
        
        return result
        
    except Exception as e:
        print(f"增量同步失败: {e}")
        return result
#-------------
# ==================== SHAP值计算辅助函数 ====================

def compute_shap_values(model, feature_names: List[str], model_type: str, sample_limit: int = 50) -> Optional[Dict]:
    """
    计算SHAP值（使用真实的训练数据）
    """
    try:
        import shap
        import pandas as pd
        import numpy as np
        
        # 检查 shap 库是否安装
        try:
            import shap
        except ImportError:
            print("⚠️ shap 库未安装，请运行: pip install shap")
            return None
        
        # 检查是否有保存的训练数据
        X_sample = None
        if "admin_shap_train_data" in st.session_state:
            train_data = st.session_state.admin_shap_train_data
            X_sample = train_data.get('X_sample')
            if X_sample is not None and len(X_sample) > 0:
                if isinstance(X_sample, pd.DataFrame):
                    X_sample = X_sample[feature_names] if all(f in X_sample.columns for f in feature_names) else X_sample
                print(f"✅ 使用训练数据，样本数: {len(X_sample)}")
        
        # 降级方案：随机数据
        if X_sample is None:
            print("⚠️ 未找到训练数据，使用随机数据（SHAP值可能不准确）")
            np.random.seed(42)
            X_sample = pd.DataFrame(
                np.random.randn(min(sample_limit, 100), len(feature_names)),
                columns=feature_names
            )
        else:
            if len(X_sample) > sample_limit:
                X_sample = X_sample.sample(n=sample_limit, random_state=42)
        
        # ==================== 根据模型类型计算 SHAP ====================
        shap_values = None
        
        # 集成模型处理
        if model_type == "集成模型":
            shap_values_list = []
            for sub_name, sub_model in [('lightgbm', model.get('lightgbm')), ('xgboost', model.get('xgboost'))]:
                if sub_model is not None:
                    try:
                        explainer = shap.TreeExplainer(sub_model)
                        shap_vals = explainer.shap_values(X_sample)
                        # 处理多分类：取类别2（好马组）
                        if isinstance(shap_vals, list) and len(shap_vals) >= 3:
                            shap_vals = shap_vals[2]
                        elif isinstance(shap_vals, list):
                            shap_vals = shap_vals[1] if len(shap_vals) > 1 else shap_vals[0]
                        shap_values_list.append(shap_vals)
                    except Exception as e:
                        print(f"子模型 SHAP 计算失败 ({sub_name}): {e}")
                        continue
            
            if shap_values_list:
                # 平均所有子模型的 SHAP 值
                shap_values = np.mean(shap_values_list, axis=0)
            else:
                return None
        
        # LightGBM 单模型
        elif model_type == "LightGBM":
            explainer = shap.TreeExplainer(model)
            shap_vals = explainer.shap_values(X_sample)
            if isinstance(shap_vals, list) and len(shap_vals) >= 3:
                shap_vals = shap_vals[2]
            elif isinstance(shap_vals, list):
                shap_vals = shap_vals[1] if len(shap_vals) > 1 else shap_vals[0]
            shap_values = shap_vals
        
        # XGBoost 单模型
        elif model_type == "XGBoost":
            explainer = shap.TreeExplainer(model)
            shap_vals = explainer.shap_values(X_sample)
            if isinstance(shap_vals, list) and len(shap_vals) >= 3:
                shap_vals = shap_vals[2]
            elif isinstance(shap_vals, list):
                shap_vals = shap_vals[1] if len(shap_vals) > 1 else shap_vals[0]
            shap_values = shap_vals
        
        else:
            return None
        
        if shap_values is None:
            return None
        
        # ==================== 计算汇总指标 ====================
        # 1. 平均绝对 SHAP 值（衡量影响大小）
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        
        # 2. 平均 SHAP 值（带符号，用于判断方向）
        mean_shap = shap_values.mean(axis=0)
        
        # 创建 DataFrame
        summary_df = pd.DataFrame({
            '特征': feature_names,
            '平均SHAP值': mean_abs_shap,      # 影响大小（绝对值）
            '平均SHAP值(带符号)': mean_shap,  # 方向信息
        }).sort_values('平均SHAP值', ascending=False)
        
        # 过滤掉重要性为0的因子
        summary_df = summary_df[summary_df['平均SHAP值'] > 0.001]
        
        # ==================== 判断影响方向（使用带符号的平均值） ====================
        direction = []
        explanation = []
        # 阈值可调，此处设为 0.005 仍然有效，若希望更敏感可降至 0.001
        threshold = 0.005
        for _, row in summary_df.iterrows():
            avg_sign = row['平均SHAP值(带符号)']
            if avg_sign > threshold:
                direction.append("正向 ↑")
                explanation.append("该因子值增大，跑入前三名概率升高")
            elif avg_sign < -threshold:
                direction.append("负向 ↓")
                explanation.append("该因子值增大，跑入前三名概率降低")
            else:
                direction.append("中性 →")
                explanation.append("该因子影响方向不明显（正负抵消）")
        
        summary_df['影响方向'] = direction
        summary_df['说明'] = explanation
        
        # 删除辅助列（带符号的平均值不显示）
        summary_df = summary_df.drop(columns=['平均SHAP值(带符号)'])
        
        return {'summary_df': summary_df}
        
    except ImportError as e:
        print(f"SHAP 库导入失败: {e}")
        st.error("请安装 SHAP 库: pip install shap")
        return None
    except Exception as e:
        print(f"SHAP 计算失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def compute_correlation_heatmap(start_date: str, end_date: str) -> Optional[go.Figure]:
    """
    计算因子相关性热力图
    从数据库获取真实数据计算
    """
    try:
        import pandas as pd
        import numpy as np
        import plotly.graph_objects as go
        
        # 获取最近赛事的数据
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?race_date=gte.{start_date}&race_date=lte.{end_date}&limit=5000"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data:
            return None
        
        # 提取特征（简化版本）
        # 实际应使用与ML相同的特征计算逻辑
        df = pd.DataFrame(data)
        
        # 计算相关系数矩阵
        # 选择数值列
        numeric_cols = ['position', 'actual_weight', 'body_weight', 'draw', 'odds']
        available_cols = [c for c in numeric_cols if c in df.columns]
        
        if len(available_cols) < 2:
            return None
        
        corr_matrix = df[available_cols].corr()
        
        # 绘制热力图
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.columns,
            colorscale='RdBu_r',
            zmid=0,
            text=corr_matrix.values.round(2),
            texttemplate='%{text}',
            textfont={"size": 10},
            hoverongaps=False
        ))
        
        fig.update_layout(
            title="因子相关性热力图",
            height=500,
            xaxis_title="因子",
            yaxis_title="因子"
        )
        
        return fig
        
    except Exception as e:
        print(f"计算相关性热力图失败: {e}")
        return None
# ==================== 管理员专用回测（带特征重要性）====================
# ==================== 独立的特征重要性提取函数 ====================

def extract_feature_importance_from_result(result: Dict) -> Optional[pd.DataFrame]:
    """
    从回测结果中独立提取特征重要性（不影响回测逻辑）
    
    参数：
        result: run_ml_backtest 返回的结果字典
    
    返回：
        特征重要性 DataFrame 或 None
    """
    model = result.get("model")
    feature_names = result.get("feature_names")
    
    if model is None:
        print("⚠️ 模型为 None，无法提取特征重要性")
        return None
    
    if not feature_names:
        print("⚠️ 特征名称为空，无法提取特征重要性")
        return None
    
    print(f"🔍 提取特征重要性: {len(feature_names)} 个特征")
    print(f"📌 模型类型: {type(model)}")
    
    try:
        # 检查是否是集成模型（字典）
        if isinstance(model, dict):
            print("📌 检测到集成模型")
            # 集成模型：尝试提取子模型的重要性
            importance_list = []
            for sub_name, sub_model in model.items():
                if sub_model is not None and hasattr(sub_model, 'feature_importances_'):
                    imp = sub_model.feature_importances_
                    importance_list.append(imp)
                    print(f"   - {sub_name}: {len(imp)} 个重要性值")
            
            if not importance_list:
                print("⚠️ 集成模型无法提取特征重要性")
                return None
            
            # 平均所有子模型的重要性
            importance = np.mean(importance_list, axis=0)
            print(f"✅ 集成模型特征重要性已平均")
            
        elif hasattr(model, 'feature_importances_'):
            # 单模型
            importance = model.feature_importances_
            print(f"✅ 单模型特征重要性提取成功: {len(importance)} 个值")
        else:
            print(f"⚠️ 模型没有 feature_importances_ 属性: {type(model)}")
            return None
        
        # 创建 DataFrame
        import pandas as pd
        imp_df = pd.DataFrame({
            '特征': feature_names,
            '重要性': importance
        }).sort_values('重要性', ascending=False)
        
        print(f"✅ 特征重要性DataFrame创建成功: {len(imp_df)} 行")
        print(f"   Top 5: {imp_df.head(5)['特征'].tolist()}")
        
        return imp_df
        
    except Exception as e:
        print(f"❌ 提取特征重要性失败: {e}")
        import traceback
        traceback.print_exc()
        return None
#----------------
def render_admin_backtest():
    """管理员专用回测页面（包含特征重要性分析）"""
    import pandas as pd  # ⭐ 添加这一行
    lang = st.session_state.get("lang", "zh")
    
    st.markdown(f"## {t()['model_comparison']}")
    st.caption(t()["backtest_period"])
    # ⭐ 调试：显示当前状态
    st.write(f"🔍 调试: admin_backtest_completed = {st.session_state.get('admin_backtest_completed', False)}")
    st.write(f"🔍 调试: admin_backtest_results 存在 = {st.session_state.get('admin_backtest_results') is not None}")
    st.write(f"🔍 调试: _backtest_just_run = {st.session_state.get('_backtest_just_run', False)}")
    
    # 初始化 session_state 中的日期
    if "admin_backtest_start" not in st.session_state:
        st.session_state.admin_backtest_start = (datetime.now() - timedelta(days=180)).date()
    if "admin_backtest_end" not in st.session_state:
        st.session_state.admin_backtest_end = datetime.now().date()
    if "admin_backtest_force_refresh" not in st.session_state:
        st.session_state.admin_backtest_force_refresh = False
    
    # ⭐ 新增：初始化回测结果缓存（用于 SHAP/热力图保留）
    if "admin_backtest_results" not in st.session_state:
        st.session_state.admin_backtest_results = None
    if "admin_backtest_completed" not in st.session_state:
        st.session_state.admin_backtest_completed = False
    if "admin_backtest_models" not in st.session_state:
        st.session_state.admin_backtest_models = {}
    
    # 日期选择
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        backtest_start = st.date_input(
            t()["start_date"], 
            value=st.session_state.admin_backtest_start,
            key="admin_backtest_start_input"
        )
    with col2:
        backtest_end = st.date_input(
            t()["end_date"], 
            value=st.session_state.admin_backtest_end,
            key="admin_backtest_end_input"
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        col3_1, col3_2 = st.columns(2)
        with col3_1:
            run_backtest_btn = st.button(t()["run_backtest"], type="primary", use_container_width=True)
        with col3_2:
            force_refresh_btn = st.button("🔄 强制刷新", use_container_width=True, help="忽略缓存，重新训练模型")
            if force_refresh_btn:
                st.session_state.admin_backtest_force_refresh = True
                # ⭐ 清除缓存的回测结果
                st.session_state.admin_backtest_results = None
                st.session_state.admin_backtest_completed = False
                st.rerun()
    
    # 更新 session_state
    st.session_state.admin_backtest_start = backtest_start
    st.session_state.admin_backtest_end = backtest_end
    
    # 模型选择复选框
    st.markdown(t()["select_models"])
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    with col_m1:
        enable_rule = st.checkbox(t()["rating_system"], value=True, key="admin_backtest_rule")
    with col_m2:
        enable_lgb = st.checkbox("LightGBM", value=True, key="admin_backtest_lgb",
                                 disabled=not LGB_AVAILABLE)
    with col_m3:
        enable_xgb = st.checkbox("XGBoost", value=True, key="admin_backtest_xgb",
                                 disabled=not XGB_AVAILABLE)
    with col_m4:
        enable_ensemble = st.checkbox("集成模型", value=True, key="admin_backtest_ensemble",
                                      disabled=(not LGB_AVAILABLE and not XGB_AVAILABLE))
    
    st.markdown("---")
    #--------------
    # ==================== 运行回测 ====================
    if run_backtest_btn or st.session_state.admin_backtest_force_refresh:
        # ⭐ 管理员无限免费（后台静默）
        force_refresh = st.session_state.admin_backtest_force_refresh
        st.session_state.admin_backtest_force_refresh = False
        
        if backtest_start > backtest_end:
            st.error("開始日期不能晚於結束日期")
        else:
            days_diff = (backtest_end - backtest_start).days
            st.info(f"📊 回測期間: {backtest_start} 至 {backtest_end} (共 {days_diff} 天)")
            
            if force_refresh:
                st.info("🔄 强制刷新模式：将忽略缓存，重新训练所有模型")
            
            results = []
            
            # 运行回测（管理员模式：force_refresh=True）
            with st.spinner("正在運行回測..."):
                if enable_lgb and LGB_AVAILABLE:
                    result = run_ml_backtest(
                        start_date=backtest_start.strftime("%Y-%m-%d"),
                        end_date=backtest_end.strftime("%Y-%m-%d"),
                        model_type="lightgbm",
                        force_refresh=force_refresh
                    )
                    results.append(result)
                
                if enable_xgb and XGB_AVAILABLE:
                    result = run_ml_backtest(
                        start_date=backtest_start.strftime("%Y-%m-%d"),
                        end_date=backtest_end.strftime("%Y-%m-%d"),
                        model_type="xgboost",
                        force_refresh=force_refresh
                    )
                    results.append(result)
                
                if enable_ensemble and (LGB_AVAILABLE or XGB_AVAILABLE):
                    result = run_ml_backtest(
                        start_date=backtest_start.strftime("%Y-%m-%d"),
                        end_date=backtest_end.strftime("%Y-%m-%d"),
                        model_type="ensemble",
                        force_refresh=force_refresh
                    )
                    results.append(result)
                
                if enable_rule:
                    result = run_backtest_for_model(
                        start_date=backtest_start.strftime("%Y-%m-%d"),
                        end_date=backtest_end.strftime("%Y-%m-%d"),
                        model_type="rule"
                    )
                    results.append(result)
            #--------------
            if results:
                # ⭐ 保存回测结果到 session_state
                st.session_state.admin_backtest_results = results
                st.session_state.admin_backtest_completed = True
                st.session_state.admin_backtest_force_refresh = False
                st.session_state._backtest_just_run = True   # 标记刚运行过回测
                
                # ⭐ 清除旧的 SHAP/热力图缓存（如果有）
                if "admin_shap_results" in st.session_state:
                    st.session_state.admin_shap_results = None
                
                st.markdown("#### 📈 模型對比結果")
                # ... 后续显示代码保持不变 ...
                
                # 显示对比表格
                completed_results = [r for r in results if not r.get("cancelled", False)]
                
                if completed_results:
                    compare_df = pd.DataFrame(completed_results)
                    display_columns = ["模型", "测试场次", "独赢正确率", 
                                      "前三名命中匹数率", "前三名命中场次率",
                                      "前三名全中率", "前三名顺序正确率",
                                      "总投入", "总回报", "ROI",
                                      "位置ROI", "综合ROI"]
                    available_cols = [c for c in display_columns if c in compare_df.columns]
                    compare_df = compare_df[available_cols]
                    #-----
                    st.dataframe(
                        compare_df.style.format({
                            '独赢正确率': '{:.1f}%',
                            '前三名命中匹数率': '{:.1f}%',
                            '前三名命中场次率': '{:.1f}%',
                            '前三名全中率': '{:.1f}%',
                            '前三名顺序正确率': '{:.1f}%',
                            'ROI': '{:+.1f}%',
                            '位置ROI': '{:+.1f}%',      # ← 添加
                            '综合ROI': '{:+.1f}%',      # ← 添加
                            '总回报': '${:.0f}',
                            '总投入': '${:.0f}'
                        }),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "模型": st.column_config.TextColumn("模型", width="small"),
                            "测试场次": st.column_config.NumberColumn("场次", width="small"),
                            "独赢正确率": st.column_config.NumberColumn("独赢", width="small", format="%.1f%%"),
                            "前三名命中匹数率": st.column_config.NumberColumn("匹数率", width="small", format="%.1f%%"),
                            "前三名命中场次率": st.column_config.NumberColumn("场次率", width="small", format="%.1f%%"),
                            "前三名全中率": st.column_config.NumberColumn("全中率", width="small", format="%.1f%%"),
                            "前三名顺序正确率": st.column_config.NumberColumn("顺序率", width="small", format="%.1f%%"),
                            "总投入": st.column_config.NumberColumn("投入", width="small", format="$%.0f"),
                            "总回报": st.column_config.NumberColumn("回报", width="small", format="$%.0f"),
                            "ROI": st.column_config.NumberColumn("ROI", width="small", format="%+.1f%%"),
                            "位置ROI": st.column_config.NumberColumn("位置ROI", width="small", format="%+.1f%%"),
                            "综合ROI": st.column_config.NumberColumn("综合ROI", width="small", format="%+.1f%%"),
                        }
                    )
                    #-----------
                    # ==================== ⭐ 特征重要性展示（使用独立函数） ====================
                    st.markdown("---")
                    st.markdown("#### 📊 特征重要性分析 (Feature Importance)")
                    st.caption("显示每个因子对ML模型预测的贡献度")
                    
                    # 为每个ML模型显示特征重要性
                    for result in completed_results:
                        model_name = result.get("模型", "")
                        # 只对ML模型显示（排除评分系统）
                        if model_name in ["LightGBM", "XGBoost", "集成模型"]:
                            
                            # ⭐ 使用独立的特征重要性提取函数
                            feature_importance = extract_feature_importance_from_result(result)
                            
                            if feature_importance is not None and not feature_importance.empty:
                                with st.expander(f"📈 {model_name} - 特征重要性", expanded=True):
                                    
                                    # 创建带中文名称的DataFrame
                                    import pandas as pd
                                    
                                    # 因子名称映射（英文 → 中文）
                                    feature_name_map = {
                                        # 基础往绩（11个）
                                        'win_rate_3': '近3场胜率',
                                        'win_rate_10': '近10场胜率',
                                        'place_rate_10': '近10场入Q率',
                                        'show_rate_10': '近10场入T率',
                                        'win_rate_5': '近5场胜率',
                                        'win_rate': '胜率',
                                        'place_rate': '入Q率',
                                        'show_rate': '入T率',
                                        'distance_rating': '路程评分',
                                        'trend': '名次趋势',
                                        'avg_weight': '平均负磅',
                                        # 场次因素（4个）
                                        'same_course': '同场地',
                                        'same_distance': '同路程',
                                        'draw': '档位',
                                        'weight': '负磅变化',
                                        # 赔率因素（3个）
                                        'odds': '赔率',
                                        'odds_trend': '赔率趋势',
                                        'ev': '期望值',
                                        # 状态因素（4个）
                                        'age': '马龄',
                                        'weight_change': '体重变化',
                                        'incident': '事件报告',
                                        'burst': '冲刺能力',
                                        # 骑师/练马师
                                        'jockey': '骑师',
                                        'trainer': '练马师',
                                        'jockey_win_rate': '骑师胜率',
                                        # 额外字段
                                        'data_used_count': '数据量',
                                        'actual_weight': '负磅',
                                        'distance': '路程',
                                        'rating_score': '评分系统',
                                        'same_venue': '同场地',
                                    }
                                    
                                    # 创建带中文列名的DataFrame
                                    display_df = feature_importance.copy()
                                    display_df['中文名'] = display_df['特征'].map(lambda x: feature_name_map.get(x, x))
                                    
                                    # 只保留重要性 > 0 的因子
                                    display_df = display_df[display_df['重要性'] > 0]
                                    display_df = display_df[['中文名', '特征', '重要性']]
                                    
                                    # 显示表格
                                    st.dataframe(
                                        display_df,
                                        use_container_width=True,
                                        hide_index=True,
                                        column_config={
                                            "中文名": st.column_config.TextColumn("因子", width="small"),
                                            "特征": st.column_config.TextColumn("英文", width="small"),
                                            "重要性": st.column_config.NumberColumn("贡献度", width="small", format="%.4f"),
                                        }
                                    )
                                    
                                    # 显示横向条形图
                                    if len(display_df) > 0:
                                        import plotly.express as px
                                        fig = px.bar(
                                            display_df,
                                            x='重要性',
                                            y='中文名',
                                            orientation='h',
                                            title=f'{model_name} - 因子重要性排名',
                                            color='重要性',
                                            color_continuous_scale='Blues',
                                            text='重要性'
                                        )
                                        fig.update_layout(
                                            height=max(300, len(display_df) * 30),
                                            xaxis_title="重要性",
                                            yaxis_title="因子",
                                            yaxis={'categoryorder': 'total ascending'}
                                        )
                                        fig.update_traces(texttemplate='%{text:.4f}', textposition='outside')
                                        st.plotly_chart(fig, use_container_width=True)
                                        
                                        if len(display_df) < 5:
                                            st.warning("⚠️ 只有少数因子有重要性值，建议检查数据源或特征工程逻辑")
                                    else:
                                        st.info("所有因子的重要性都为0，请检查训练数据是否有效")
                                    
                                    # 缓存状态提示
                                    if result.get("from_cache", False):
                                        st.info("💡 该结果来自缓存（权重和日期范围未变化）")
                                    else:
                                        st.success("✅ 该结果来自全新训练")
                            else:
                                st.info(f"{model_name}: 无特征重要性数据")
                    #----------
                    # ==================== SHAP值分析（按需加载）====================
                    st.markdown("---")
                    st.markdown("#### 🔬 SHAP值分析（深度解释）")
                    st.caption('SHAP值可以显示每个因子是"正向"还是"负向"影响预测结果')
                    
                    # 检查是否有可用的ML模型（检查 feature_importance 是否存在）
                    has_ml_model = any(
                        r.get("模型") in ["LightGBM", "XGBoost", "集成模型"] 
                        and r.get("feature_importance") is not None 
                        for r in completed_results
                    )
                    
                    if has_ml_model:
                        # ⭐ 使用 form 防止页面刷新
                        with st.form(key="shap_form"):
                            col_shap_btn, col_shap_info = st.columns([1, 3])
                            with col_shap_btn:
                                compute_shap_btn = st.form_submit_button("🔬 计算SHAP值（最近50场）", type="secondary", use_container_width=True)
                            with col_shap_info:
                                st.caption("⏱️ 预计耗时 2-5 分钟，仅计算最近50场比赛的SHAP值")
                            
                            if compute_shap_btn:
                                # ⭐ 使用 st.spinner
                                with st.spinner("正在计算SHAP值，请稍候..."):
                                    # 选择第一个可用的ML模型
                                    ml_result = None
                                    for r in completed_results:
                                        if r.get("模型") in ["LightGBM", "XGBoost", "集成模型"] and r.get("model") is not None:
                                            ml_result = r
                                            break
                                    
                                    if ml_result:
                                        shap_results = compute_shap_values(
                                            ml_result.get("model"),
                                            ml_result.get("feature_names", []),
                                            model_type=ml_result.get("模型"),
                                            sample_limit=50
                                        )
                                        
                                        if shap_results:
                                            st.success("✅ SHAP值计算完成！")
                                            
                                            # 显示SHAP条形图
                                            st.markdown("**SHAP值汇总（因子方向性）**")
                                            
                                            shap_df = shap_results.get("summary_df")
                                            if shap_df is not None and not shap_df.empty:
                                                import plotly.express as px
                                                
                                                # 只显示有影响的因子
                                                shap_df_display = shap_df[shap_df['平均SHAP值'] > 0.001]
                                                
                                                if not shap_df_display.empty:
                                                    color_map = {
                                                        '正向 ↑': 'green',
                                                        '负向 ↓': 'red',
                                                        '中性 →': 'gray'
                                                    }
                                                    
                                                    fig = px.bar(
                                                        shap_df_display,
                                                        x='平均SHAP值',
                                                        y='特征',
                                                        orientation='h',
                                                        title='SHAP值 - 因子影响方向',
                                                        color='影响方向',
                                                        color_discrete_map=color_map,
                                                        text='平均SHAP值'
                                                    )
                                                    fig.update_layout(
                                                        height=max(300, len(shap_df_display) * 30),
                                                        xaxis_title="平均SHAP值",
                                                        yaxis_title="因子"
                                                    )
                                                    fig.update_traces(texttemplate='%{text:.4f}', textposition='outside')
                                                    st.plotly_chart(fig, use_container_width=True)
                                                    
                                                    # 显示表格
                                                    st.dataframe(
                                                        shap_df_display,
                                                        use_container_width=True,
                                                        hide_index=True,
                                                        column_config={
                                                            "特征": st.column_config.TextColumn("因子", width="medium"),
                                                            "平均SHAP值": st.column_config.NumberColumn("SHAP值", format="%.4f"),
                                                            "影响方向": st.column_config.TextColumn("方向", width="small"),
                                                            "说明": st.column_config.TextColumn("说明", width="medium"),
                                                        }
                                                    )
                                                else:
                                                    st.info("所有因子的SHAP值都很小，可能模型未学到有效特征")
                                            else:
                                                st.warning("SHAP数据为空")
                                        else:
                                            st.warning("SHAP值计算失败，请检查模型是否支持")
                                    else:
                                        st.warning("未找到可用的ML模型")
                    else:
                        st.info("请先运行LightGBM或XGBoost回测，然后才能计算SHAP值")
                    
                    # ==================== 相关性热力图 ====================
                    st.markdown("---")
                    st.markdown('#### 🔥 因子相关性热力图')
                    st.caption('显示18个因子之间的相关关系（帮助识别冗余因子）')
                    
                    if st.button("📊 计算相关性热力图", use_container_width=True):
                        with st.spinner("正在计算相关性..."):
                            # 从回测数据中提取特征
                            # 这里需要从训练数据中提取，由于回测函数没有返回训练数据
                            # 我们直接从数据库获取最近的数据计算相关性
                            correlation_fig = compute_correlation_heatmap(
                                start_date.strftime("%Y-%m-%d"),
                                end_date.strftime("%Y-%m-%d")
                            )
                            if correlation_fig:
                                st.plotly_chart(correlation_fig, use_container_width=True)
                            else:
                                st.warning("无法计算相关性，请确保有足够的数据")
                    
                    # ==================== 免责声明 ====================
                    st.markdown("---")
                    st.caption("📌 回測結果基於歷史數據，不構成投資建議")
                else:
                    st.warning("所有回测均被取消或失败")
            else:
                st.warning("請至少選擇一個模型")
#-----------------
# ==================== 显示缓存的回测结果（用于 SHAP/热力图后保留） ====================
    if st.session_state.get("admin_backtest_completed", False):
        # 如果是刚刚运行回测，已经显示过了，跳过缓存显示并重置标记
        if st.session_state.get("_backtest_just_run", False):
            st.session_state._backtest_just_run = False
        else:
            cached_results = st.session_state.admin_backtest_results
            if cached_results:
                completed_results = [r for r in cached_results if not r.get("cancelled", False)]
                if completed_results:
                    st.markdown("#### 📈 模型對比結果")
                    
                    # ---- 显示对比表格 ----
                    compare_df = pd.DataFrame(completed_results)
                    display_columns = ["模型", "测试场次", "独赢正确率", 
                                      "前三名命中匹数率", "前三名命中场次率",
                                      "前三名全中率", "前三名顺序正确率",
                                      "总投入", "总回报", "ROI",
                                      "位置ROI", "综合ROI"]
                    available_cols = [c for c in display_columns if c in compare_df.columns]
                    compare_df = compare_df[available_cols]
                    
                    st.dataframe(
                        compare_df.style.format({
                            '独赢正确率': '{:.1f}%',
                            '前三名命中匹数率': '{:.1f}%',
                            '前三名命中场次率': '{:.1f}%',
                            '前三名全中率': '{:.1f}%',
                            '前三名顺序正确率': '{:.1f}%',
                            'ROI': '{:+.1f}%',
                            '位置ROI': '{:+.1f}%',
                            '综合ROI': '{:+.1f}%',
                            '总回报': '${:.0f}',
                            '总投入': '${:.0f}'
                        }),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "模型": st.column_config.TextColumn("模型", width="small"),
                            "测试场次": st.column_config.NumberColumn("场次", width="small"),
                            "独赢正确率": st.column_config.NumberColumn("独赢", width="small", format="%.1f%%"),
                            "前三名命中匹数率": st.column_config.NumberColumn("匹数率", width="small", format="%.1f%%"),
                            "前三名命中场次率": st.column_config.NumberColumn("场次率", width="small", format="%.1f%%"),
                            "前三名全中率": st.column_config.NumberColumn("全中率", width="small", format="%.1f%%"),
                            "前三名顺序正确率": st.column_config.NumberColumn("顺序率", width="small", format="%.1f%%"),
                            "总投入": st.column_config.NumberColumn("投入", width="small", format="$%.0f"),
                            "总回报": st.column_config.NumberColumn("回报", width="small", format="$%.0f"),
                            "ROI": st.column_config.NumberColumn("ROI", width="small", format="%+.1f%%"),
                            "位置ROI": st.column_config.NumberColumn("位置ROI", width="small", format="%+.1f%%"),
                            "综合ROI": st.column_config.NumberColumn("综合ROI", width="small", format="%+.1f%%"),
                        }
                    )
                    
                    # ---- 特征重要性展示 ----
                    st.markdown("---")
                    st.markdown("#### 📊 特征重要性分析 (Feature Importance)")
                    st.caption("显示每个因子对ML模型预测的贡献度")
                    
                    for result in completed_results:
                        model_name = result.get("模型", "")
                        if model_name in ["LightGBM", "XGBoost", "集成模型"]:
                            feature_importance = extract_feature_importance_from_result(result)
                            if feature_importance is not None and not feature_importance.empty:
                                with st.expander(f"📈 {model_name} - 特征重要性", expanded=True):
                                    feature_name_map = {
                                        'win_rate_3': '近3场胜率', 'win_rate_10': '近10场胜率',
                                        'place_rate_10': '近10场入Q率', 'show_rate_10': '近10场入T率',
                                        'win_rate_5': '近5场胜率', 'win_rate': '胜率',
                                        'place_rate': '入Q率', 'show_rate': '入T率',
                                        'distance_rating': '路程评分', 'trend': '名次趋势',
                                        'avg_weight': '平均负磅', 'same_course': '同场地',
                                        'same_distance': '同路程', 'draw': '档位',
                                        'weight': '负磅变化', 'odds': '赔率',
                                        'odds_trend': '赔率趋势', 'ev': '期望值',
                                        'age': '马龄', 'weight_change': '体重变化',
                                        'incident': '事件报告', 'burst': '冲刺能力',
                                        'jockey': '骑师', 'trainer': '练马师',
                                        'jockey_win_rate': '骑师胜率', 'data_used_count': '数据量',
                                        'actual_weight': '负磅', 'distance': '路程',
                                        'rating_score': '评分系统', 'same_venue': '同场地',
                                    }
                                    display_df = feature_importance.copy()
                                    display_df['中文名'] = display_df['特征'].map(lambda x: feature_name_map.get(x, x))
                                    display_df = display_df[display_df['重要性'] > 0]
                                    display_df = display_df[['中文名', '特征', '重要性']]
                                    st.dataframe(display_df, use_container_width=True, hide_index=True,
                                                column_config={
                                                    "中文名": st.column_config.TextColumn("因子", width="small"),
                                                    "特征": st.column_config.TextColumn("英文", width="small"),
                                                    "重要性": st.column_config.NumberColumn("贡献度", width="small", format="%.4f"),
                                                })
                                    if len(display_df) > 0:
                                        import plotly.express as px
                                        fig = px.bar(display_df, x='重要性', y='中文名', orientation='h',
                                                     title=f'{model_name} - 因子重要性排名', color='重要性',
                                                     color_continuous_scale='Blues', text='重要性')
                                        fig.update_layout(height=max(300, len(display_df)*30), yaxis={'categoryorder': 'total ascending'})
                                        fig.update_traces(texttemplate='%{text:.4f}', textposition='outside')
                                        st.plotly_chart(fig, use_container_width=True)
                                    if result.get("from_cache", False):
                                        st.info("💡 该结果来自缓存（权重和日期范围未变化）")
                                    else:
                                        st.success("✅ 该结果来自全新训练")
                            else:
                                st.info(f"{model_name}: 无特征重要性数据")
                    
                    # ---- SHAP值分析 ----
                    st.markdown("---")
                    st.markdown("#### 🔬 SHAP值分析（深度解释）")
                    st.caption('SHAP值可以显示每个因子是"正向"还是"负向"影响预测结果')
                    
                    has_ml_model = any(r.get("模型") in ["LightGBM", "XGBoost", "集成模型"] and r.get("model") is not None for r in completed_results)
                    if has_ml_model:
                        with st.form(key="shap_form_cached"):
                            col_shap_btn, col_shap_info = st.columns([1, 3])
                            with col_shap_btn:
                                compute_shap_btn = st.form_submit_button("🔬 计算SHAP值（最近50场）", type="secondary", use_container_width=True)
                            with col_shap_info:
                                st.caption("⏱️ 预计耗时 2-5 分钟，仅计算最近50场比赛的SHAP值")
                            
                            if compute_shap_btn:
                                with st.spinner("正在计算SHAP值，请稍候..."):
                                    ml_result = None
                                    for r in completed_results:
                                        if r.get("模型") in ["LightGBM", "XGBoost", "集成模型"] and r.get("model") is not None:
                                            ml_result = r
                                            break
                                    if ml_result:
                                        shap_results = compute_shap_values(
                                            ml_result.get("model"),
                                            ml_result.get("feature_names", []),
                                            model_type=ml_result.get("模型"),
                                            sample_limit=50
                                        )
                                        if shap_results:
                                            st.success("✅ SHAP值计算完成！")
                                            shap_df = shap_results.get("summary_df")
                                            if shap_df is not None and not shap_df.empty:
                                                shap_df_display = shap_df[shap_df['平均SHAP值'] > 0.001]
                                                if not shap_df_display.empty:
                                                    import plotly.express as px
                                                    color_map = {'正向 ↑': 'green', '负向 ↓': 'red', '中性 →': 'gray'}
                                                    fig = px.bar(shap_df_display, x='平均SHAP值', y='特征', orientation='h',
                                                                 title='SHAP值 - 因子影响方向', color='影响方向',
                                                                 color_discrete_map=color_map, text='平均SHAP值')
                                                    fig.update_layout(height=max(300, len(shap_df_display)*30))
                                                    fig.update_traces(texttemplate='%{text:.4f}', textposition='outside')
                                                    st.plotly_chart(fig, use_container_width=True)
                                                    st.dataframe(shap_df_display, use_container_width=True, hide_index=True)
                                                else:
                                                    st.info("所有因子的SHAP值都很小")
                                            else:
                                                st.warning("SHAP数据为空")
                                        else:
                                            st.warning("SHAP值计算失败")
                                    else:
                                        st.warning("未找到可用的ML模型")
                    else:
                        st.info("请先运行LightGBM或XGBoost回测，然后才能计算SHAP值")
                    
                    # ---- 相关性热力图 ----
                    st.markdown("---")
                    st.markdown('#### 🔥 因子相关性热力图')
                    st.caption('显示18个因子之间的相关关系（帮助识别冗余因子）')
                    
                    if st.button("📊 计算相关性热力图", use_container_width=True, key="corr_heatmap_cached"):
                        with st.spinner("正在计算相关性..."):
                            correlation_fig = compute_correlation_heatmap(
                                backtest_start.strftime("%Y-%m-%d"),
                                backtest_end.strftime("%Y-%m-%d")
                            )
                            if correlation_fig:
                                st.plotly_chart(correlation_fig, use_container_width=True)
                            else:
                                st.warning("无法计算相关性，请确保有足够的数据")
                    
                    st.markdown("---")
                    st.caption("📌 回測結果基於歷史數據，不構成投資建議")

    render_rank_calibration_backtest_section()
# ==================== 管理员：赔率采集监控 ====================
ODDS_KEY_MINUTES_ADMIN = [
    90, 80, 70, 60, 50, 45, 40, 35, 30, 27, 24, 21,
    18, 15, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0,
]


@st.cache_data(ttl=60, show_spinner=False)
def get_odds_collection_logs(limit: int = 15) -> Tuple[List[Dict], Optional[str]]:
    if not SUPABASE_URL:
        return [], "Supabase 未配置"
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/odds_collection_log?select=*&order=run_at.desc&limit={limit}"
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 404:
            return [], "请先执行 scripts/odds_collection_log.sql 创建 odds_collection_log 表"
        if response.status_code != 200:
            return [], f"查询失败 HTTP {response.status_code}"
        return response.json() or [], None
    except Exception as exc:
        return [], str(exc)


@st.cache_data(ttl=120, show_spinner=False)
def get_future_odds_snapshot_coverage() -> pd.DataFrame:
    """未来赛日每场已采集的关键分钟数（WIN）。"""
    if not SUPABASE_URL:
        return pd.DataFrame()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        headers = get_supabase_headers(use_secret=True)
        url = (
            f"{SUPABASE_URL}/rest/v1/odds_history"
            f"?select=race_date,venue,race_no,odds_type,minutes_before_race,horse_no"
            f"&race_date=gte.{today}"
            f"&odds_type=in.(WIN,PLA)"
            f"&limit=50000"
        )
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return pd.DataFrame()
        rows = response.json() or []
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df = df[df["horse_no"].notna()]
        df = df[df["horse_no"] != 0]
        if df.empty:
            return pd.DataFrame()

        grouped = (
            df.groupby(["race_date", "venue", "race_no", "odds_type"])["minutes_before_race"]
            .nunique()
            .reset_index(name="time_points")
        )
        pivot = grouped.pivot_table(
            index=["race_date", "venue", "race_no"],
            columns="odds_type",
            values="time_points",
            fill_value=0,
        ).reset_index()
        pivot.columns.name = None
        if "WIN" not in pivot.columns:
            pivot["WIN"] = 0
        if "PLA" not in pivot.columns:
            pivot["PLA"] = 0
        pivot["target_points"] = len(ODDS_KEY_MINUTES_ADMIN)
        pivot = pivot.sort_values(["race_date", "venue", "race_no"])
        return pivot
    except Exception as exc:
        print(f"get_future_odds_snapshot_coverage failed: {exc}")
        return pd.DataFrame()


def render_admin_odds_collection() -> None:
    lang = get_lang()
    st.markdown("### 📡 赔率采集状态" if lang == "zh" else "### 📡 Odds Collection Status")
    st.caption(
        "开赛前 90→0 分钟共 26 个关键时间点，Node 服务每 15 分钟采集 WIN/PLA"
        if lang == "zh"
        else "26 key minutes (90→0 before post); Node server collects WIN/PLA every 15 minutes"
    )

    api_base = st.secrets.get("HKJC_API_URL", "").rstrip("/")
    collect_url = (
        f"{api_base}/collect/auto"
        if api_base.endswith("/api")
        else f"{api_base}/api/collect/auto"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 立即触发采集" if lang == "zh" else "🔄 Run collection now", use_container_width=True):
            if not api_base:
                st.error("HKJC_API_URL 未配置")
            else:
                with st.spinner("Calling Node API..."):
                    try:
                        resp = requests.post(collect_url, timeout=120)
                        if resp.status_code == 200:
                            summary = resp.json().get("summary", {})
                            st.success(
                                tx(
                                    f"完成：检查 {summary.get('racesChecked', 0)} 场，"
                                    f"写入 {summary.get('rowsSaved', 0)} 条，"
                                    f"跳过 {summary.get('rowsSkipped', 0)} 条",
                                    f"Done: checked {summary.get('racesChecked', 0)} races, "
                                    f"saved {summary.get('rowsSaved', 0)} rows, "
                                    f"skipped {summary.get('rowsSkipped', 0)} rows",
                                )
                            )
                            get_odds_collection_logs.clear()
                            get_future_odds_snapshot_coverage.clear()
                            fetch_race_odds_history.clear()
                        else:
                            st.error(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    except Exception as exc:
                        st.error(str(exc))
    with col_b:
        if st.button("♻️ 刷新状态" if lang == "zh" else "♻️ Refresh", use_container_width=True):
            get_odds_collection_logs.clear()
            get_future_odds_snapshot_coverage.clear()
            st.rerun()

    st.markdown("---")
    st.markdown("**最近一次采集**" if lang == "zh" else "**Latest collection run**")
    logs, log_err = get_odds_collection_logs(limit=1)
    if log_err:
        st.warning(log_err)
    elif logs:
        last = logs[0]
        run_at = (last.get("run_at") or "")[:19].replace("T", " ")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("时间" if lang == "zh" else "Time", run_at or "-")
        with c2:
            st.metric("来源" if lang == "zh" else "Source", last.get("source", "-"))
        with c3:
            st.metric("写入行数" if lang == "zh" else "Rows saved", last.get("rows_saved", 0))
        with c4:
            st.metric("检查场次" if lang == "zh" else "Races checked", last.get("races_checked", 0))
        if last.get("error_message"):
            st.error(last.get("error_message"))
    else:
        st.info("尚无采集日志（部署新 Node 服务并执行 SQL 迁移后会出现）" if lang == "zh" else "No collection logs yet")

    st.markdown("---")
    st.markdown("**未来赛日快照覆盖（目标 26 点）**" if lang == "zh" else "**Upcoming race snapshot coverage (target 26)**")
    coverage = get_future_odds_snapshot_coverage()
    if coverage.empty:
        st.warning("暂无未来赛日 WIN/PLA 快照" if lang == "zh" else "No upcoming WIN/PLA snapshots")
    else:
        st.dataframe(coverage, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**最近采集记录**" if lang == "zh" else "**Recent collection runs**")
    all_logs, _ = get_odds_collection_logs(limit=15)
    if all_logs:
        log_df = pd.DataFrame(all_logs)
        show_cols = [
            c for c in [
                "run_at", "source", "races_checked", "races_collected",
                "rows_saved", "rows_skipped", "duration_ms", "error_message",
            ]
            if c in log_df.columns
        ]
        st.dataframe(log_df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.caption("—")

    st.markdown("---")
    st.markdown("**最近 7 天 odds_history 写入量**" if lang == "zh" else "**odds_history writes (last 7 days)**")
    try:
        headers = get_supabase_headers(use_secret=True)
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = (
            f"{SUPABASE_URL}/rest/v1/odds_history"
            f"?select=recorded_at,odds_type,race_date"
            f"&recorded_at=gte.{since}T00:00:00"
            f"&odds_type=in.(WIN,PLA)&limit=10000"
        )
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200 and response.json():
            df_stats = pd.DataFrame(response.json())
            df_stats["recorded_at"] = pd.to_datetime(
                df_stats["recorded_at"], format="ISO8601", errors="coerce"
            )
            df_stats["collect_date"] = df_stats["recorded_at"].dt.date
            pivot_stats = df_stats.groupby(["collect_date", "odds_type"]).size().unstack(fill_value=0)
            st.dataframe(pivot_stats, use_container_width=True)
        else:
            st.warning("最近 7 天无 WIN/PLA 写入" if lang == "zh" else "No WIN/PLA writes in last 7 days")
    except Exception as exc:
        st.error(str(exc))


@st.cache_data(ttl=600, show_spinner=False)
def _load_incident_context_maps(supabase_url: str) -> Dict:
    if not build_incident_context_maps or not supabase_url:
        return {"by_hash": {}, "by_race_key": {}, "horse_names": {}}
    hdrs = get_supabase_headers(use_secret=True)
    return build_incident_context_maps(supabase_url, hdrs)


def _render_incident_cache_browser(headers: Dict, lang: str) -> None:
    """管理员：分页查阅 incident LLM 缓存。"""
    if not search_incident_llm_cache:
        return

    st.markdown("**事件缓存查阅**" if lang == "zh" else "**Browse incident LLM cache**")
    st.caption(
        "可按赛日、场地、关键词翻查历史事件；马名优先读缓存字段，缺失时从往绩表按事件文本/赛日键补全。"
        " 综合评分按每匹马往绩中的事件文本查 LLM 缓存，不依赖本表是否显示马名。"
        if lang == "zh"
        else "Filter by race date, venue, keyword; horse names from cache or past performances. "
        "Horse scores use incident text from performances, not this table's horse name column."
    )

    today = datetime.now().date()
    default_from = today - timedelta(days=90)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        date_from = st.date_input(
            "赛日起" if lang == "zh" else "Race date from",
            value=default_from,
            key="admin_incident_browse_from",
        )
    with c2:
        date_to = st.date_input(
            "赛日止" if lang == "zh" else "Race date to",
            value=today,
            key="admin_incident_browse_to",
        )
    with c3:
        venue_filter = st.selectbox(
            "场地" if lang == "zh" else "Venue",
            options=["", "ST", "HV"],
            format_func=lambda v: {"": "全部" if lang == "zh" else "All", "ST": "沙田 ST" if lang == "zh" else "ST", "HV": "跑馬地 HV" if lang == "zh" else "HV"}.get(v, v),
            key="admin_incident_browse_venue",
        )
    with c4:
        keyword = st.text_input(
            "事件关键词" if lang == "zh" else "Keyword",
            value="",
            key="admin_incident_browse_kw",
        )

    c5, c6, c7 = st.columns([1, 1, 2])
    with c5:
        page_size = st.selectbox(
            "每页条数" if lang == "zh" else "Page size",
            options=[50, 100, 200],
            index=0,
            key="admin_incident_browse_page_size",
        )
    with c6:
        sort_by = st.selectbox(
            "排序" if lang == "zh" else "Sort",
            options=["created_at.desc", "race_date.desc.nullslast", "race_date.asc"],
            format_func=lambda x: {
                "created_at.desc": "写入时间↓" if lang == "zh" else "Created↓",
                "race_date.desc.nullslast": "赛日↓" if lang == "zh" else "Race date↓",
                "race_date.asc": "赛日↑" if lang == "zh" else "Race date↑",
            }.get(x, x),
            key="admin_incident_browse_sort",
        )
    with c7:
        browse_all_dates = st.checkbox(
            "不限赛日（查全部历史）" if lang == "zh" else "All dates (full history)",
            value=True,
            key="admin_incident_browse_all_dates",
        )

    page = int(st.session_state.get("admin_incident_browse_page", 1))
    nav1, nav2, nav3 = st.columns([1, 1, 4])
    with nav1:
        if st.button("◀ 上一页" if lang == "zh" else "◀ Prev", key="admin_incident_prev") and page > 1:
            st.session_state["admin_incident_browse_page"] = page - 1
            st.rerun()
    with nav2:
        if st.button("下一页 ▶" if lang == "zh" else "Next ▶", key="admin_incident_next"):
            st.session_state["admin_incident_browse_page"] = page + 1
            st.rerun()
    with nav3:
        jump_page = st.number_input(
            "页码" if lang == "zh" else "Page",
            min_value=1,
            value=page,
            step=1,
            key="admin_incident_browse_page_input",
        )
        if jump_page != page:
            st.session_state["admin_incident_browse_page"] = int(jump_page)
            st.rerun()

    race_from = "" if browse_all_dates else str(date_from)
    race_to = "" if browse_all_dates else str(date_to)
    search_result = search_incident_llm_cache(
        SUPABASE_URL,
        headers,
        race_date_from=race_from,
        race_date_to=race_to,
        venue=venue_filter,
        keyword=keyword.strip(),
        page=page,
        page_size=page_size,
        order=sort_by,
    )
    rows = search_result.get("rows") or []
    total = int(search_result.get("total") or 0)
    st.session_state["admin_incident_browse_total"] = total
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages and total > 0:
        st.session_state["admin_incident_browse_page"] = total_pages
        st.rerun()

    ctx = _load_incident_context_maps(SUPABASE_URL)

    show_rows = []
    for row in rows:
        text = row.get("incident_text") or ""
        if resolve_incident_cache_display:
            disp = resolve_incident_cache_display(row, ctx, lang=lang)
        else:
            by_hash = ctx.get("by_hash") or {}
            horse_names = ctx.get("horse_names") or {}
            h = row.get("incident_text_hash") or ""
            if not h and text and incident_text_hash_fn:
                h = incident_text_hash_fn(text)
            meta = by_hash.get(h, {})
            horse_id = str(row.get("horse_id") or meta.get("horse_id") or "")
            disp = {
                "race_date": (row.get("race_date") or meta.get("race_date") or "")[:10] or "-",
                "venue_label": format_venue_label(row.get("venue") or meta.get("venue") or "", lang),
                "race_label": f"第{row.get('race_no') or meta.get('race_no')}场" if lang == "zh" else f"R{row.get('race_no') or meta.get('race_no') or '-'}",
                "horse_no": row.get("horse_no") or meta.get("horse_no") or "-",
                "horse_name": (row.get("horse_name") or meta.get("horse_name") or horse_names.get(horse_id, "") or "-"),
                "incident_text": text,
            }
        show_rows.append({
            "赛日" if lang == "zh" else "Race date": disp["race_date"],
            "场地" if lang == "zh" else "Venue": disp["venue_label"],
            "场次" if lang == "zh" else "Race": disp["race_label"],
            "马号" if lang == "zh" else "Horse #": disp["horse_no"],
            "马名" if lang == "zh" else "Horse": disp["horse_name"],
            "LLM分" if lang == "zh" else "LLM": row.get("llm_impact_score"),
            "规则分" if lang == "zh" else "Rule": row.get("rule_score"),
            "类型" if lang == "zh" else "Type": row.get("incident_type"),
            "建议" if lang == "zh" else "Tip": row.get("suggestion") or "",
            "Token" if lang == "zh" else "Tokens": row.get("total_tokens") or 0,
            "写入(HKT)" if lang == "zh" else "Saved (HKT)": format_datetime_hkt(row.get("created_at") or ""),
            "事件报告" if lang == "zh" else "Incident": disp["incident_text"],
        })

    st.caption(
        f"共 {total} 条，第 {min(page, total_pages)} / {total_pages} 页"
        if lang == "zh"
        else f"{total} rows, page {min(page, total_pages)} / {total_pages}"
    )
    if show_rows:
        st.dataframe(
            pd.DataFrame(show_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                ("事件报告" if lang == "zh" else "Incident"): st.column_config.TextColumn(
                    "事件报告" if lang == "zh" else "Incident",
                    width="large",
                ),
                ("建议" if lang == "zh" else "Tip"): st.column_config.TextColumn(
                    "建议" if lang == "zh" else "Tip",
                    width="medium",
                ),
            },
        )
    else:
        st.info("没有符合条件的事件缓存。" if lang == "zh" else "No incident cache rows match filters.")


def _get_deepseek_secrets() -> Dict:
    return {
        "DEEPSEEK_API_KEY": st.secrets.get("DEEPSEEK_API_KEY", ""),
        "DEEPSEEK_BASE_URL": st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "DEEPSEEK_MODEL": st.secrets.get("DEEPSEEK_MODEL", "deepseek-chat"),
    }


def _run_admin_incident_backfill(
    headers: Dict,
    *,
    max_calls: int,
    fill_all: bool,
    lang: str,
) -> Optional[Dict]:
    if not batch_cache_missing_incidents or not fetch_past_incident_texts:
        st.error("补全功能不可用，请重新部署最新版 incident_llm_service.py。" if lang == "zh" else "Backfill unavailable; redeploy latest incident_llm_service.py.")
        return None

    texts, _ = fetch_past_incident_texts(SUPABASE_URL, headers, limit=INCIDENT_SCAN_LIMIT)
    progress = st.progress(0.0)
    status = st.empty()
    target = max_calls

    def on_progress(run_stats: Dict) -> None:
        done = int(run_stats.get("analyzed", 0) or 0)
        planned = int(run_stats.get("planned_calls", 0) or target or 1)
        denom = planned if planned > 0 else max(done, 1)
        progress.progress(min(done / denom, 1.0))
        status.caption(
            f"正在分析 {done} / {planned} ..." if lang == "zh" else f"Analyzing {done} / {planned} ..."
        )

    with st.spinner(
        "正在补全全部未缓存 incident，请勿关闭页面..." if fill_all and lang == "zh"
        else "Backfilling all missing incidents, keep this page open..." if fill_all
        else "正在批量分析未缓存 incident..." if lang == "zh"
        else "Backfilling incidents..."
    ):
        result = batch_cache_missing_incidents(
            texts,
            SUPABASE_URL,
            headers,
            _get_deepseek_secrets(),
            max_new_calls=max_calls,
            fill_all=fill_all,
            progress_callback=on_progress,
        )
    progress.progress(1.0)
    status.empty()
    return result


def _show_admin_backfill_result(result: Dict, lang: str) -> None:
    remaining_after = result.get("remaining_missing", 0)
    session_tokens = result.get("total_tokens", 0)
    _load_missing_incident_stats.clear()
    st.success(
        f"完成：新分析 {result.get('analyzed', 0)} 条，已有缓存 {result.get('cached', 0)}，"
        f"跳过 {result.get('skipped', 0)}，错误 {result.get('errors', 0)}，"
        f"本次 Token {session_tokens:,}。"
        f"**剩余未缓存约 {remaining_after} 条**。"
        if lang == "zh"
        else (
            f"Done: analyzed {result.get('analyzed', 0)}, cached {result.get('cached', 0)}, "
            f"skipped {result.get('skipped', 0)}, errors {result.get('errors', 0)}, "
            f"tokens {session_tokens:,}. ~{remaining_after} still uncached."
        )
    )
    if remaining_after > 0:
        st.info(
            f"仍有约 {remaining_after} 条未缓存；可再次使用一键补全或分批补全。"
            if lang == "zh"
            else f"~{remaining_after} still uncached; run fill-all again or backfill in batches."
        )
    elif lang == "zh":
        st.success("历史 incident 已全部写入缓存；今后只会对新 incident 调用 DeepSeek。")
    else:
        st.success("All scanned incidents are cached; future API calls are for new incidents only.")
    trim_info = result.get("trim") or {}
    trim_deleted = int(trim_info.get("deleted") or 0)
    if trim_deleted > 0:
        st.info(
            f"incident_llm_cache 已清理最旧 {trim_deleted} 条，当前上限 15,000 条。"
            if lang == "zh"
            else f"Trimmed {trim_deleted} oldest incident_llm_cache row(s); cap is 15,000."
        )


def render_admin_deepseek_usage() -> None:
    """管理员：DeepSeek / incident LLM 用量与补缓存。"""
    lang = st.session_state.get("lang", "zh")
    st.markdown("### 🤖 DeepSeek 用量监控" if lang == "zh" else "### 🤖 DeepSeek Usage Monitor")
    st.caption(
        "热路径（智能投注单场、全马评分榜、ML 特征）**只读 Supabase 缓存，不自动调 API**。"
        "每条 incident_llm_cache 记录 ≈ 曾调用一次 DeepSeek 分析；缓存最多保留 **15,000** 条（超出删最旧）。"
        "时间均为 **香港时间 (UTC+8)**。"
        if lang == "zh"
        else "Hot paths read Supabase cache only. Each incident_llm_cache row ≈ one DeepSeek API call; cache capped at **15,000** rows (oldest trimmed). Times are HKT (UTC+8)."
    )

    if not INCIDENT_LLM_OK:
        st.warning(
            f"incident_llm_service 未加载：{INCIDENT_LLM_IMPORT_ERROR or 'ImportError'}"
            if lang == "zh"
            else f"incident_llm_service failed to load: {INCIDENT_LLM_IMPORT_ERROR or 'ImportError'}"
        )
        st.caption("请确认仓库已部署 `incident_llm_service.py`，并重新启动 Streamlit 应用。" if lang == "zh" else "Ensure incident_llm_service.py is deployed and restart the app.")
        return
    if not SUPABASE_URL:
        st.warning("Supabase 未配置：请在 secrets 中设置 SUPABASE_STOCK_URL。" if lang == "zh" else "Supabase not configured: set SUPABASE_STOCK_URL in secrets.")
        return
    if not fetch_incident_llm_usage_stats:
        st.warning("fetch_incident_llm_usage_stats 不可用。" if lang == "zh" else "fetch_incident_llm_usage_stats unavailable.")
        return

    headers = get_supabase_headers(use_secret=True)
    try:
        stats = fetch_incident_llm_usage_stats(SUPABASE_URL, headers)
    except Exception as exc:
        st.error(f"读取 DeepSeek 统计失败：{exc}" if lang == "zh" else f"Failed to load DeepSeek stats: {exc}")
        return

    missing_stats: Dict = {}
    remaining = 0
    total_unique = 0
    cached_unique = 0
    if count_missing_incident_cache:
        try:
            missing_stats = _load_missing_incident_stats(SUPABASE_URL)
            remaining = missing_stats.get("missing_unique", 0)
            total_unique = missing_stats.get("total_unique", 0)
            cached_unique = missing_stats.get("cached_unique", 0)
        except Exception as exc:
            st.warning(f"统计未缓存 incident 失败：{exc}" if lang == "zh" else f"Failed to count missing incidents: {exc}")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("缓存总数" if lang == "zh" else "Cache rows", stats.get("cache_total", 0))
    with c2:
        st.metric("近 24h 新增" if lang == "zh" else "Added 24h", stats.get("cache_24h", 0))
    with c3:
        st.metric("近 7 天新增" if lang == "zh" else "Added 7d", stats.get("cache_7d", 0))
    with c4:
        st.metric(
            "最近写入 (HKT)" if lang == "zh" else "Latest write (HKT)",
            stats.get("latest_at") or "-",
        )

    tokens_total = stats.get("tokens_total") or {}
    tokens_24h = stats.get("tokens_24h") or {}
    tokens_7d = stats.get("tokens_7d") or {}
    t1, t2, t3 = st.columns(3)
    with t1:
        st.metric(
            "累计 Token" if lang == "zh" else "Total tokens",
            f"{tokens_total.get('total_tokens', 0):,}",
        )
    with t2:
        st.metric(
            "近 24h Token" if lang == "zh" else "Tokens 24h",
            f"{tokens_24h.get('total_tokens', 0):,}",
        )
    with t3:
        st.metric(
            "近 7 天 Token" if lang == "zh" else "Tokens 7d",
            f"{tokens_7d.get('total_tokens', 0):,}",
        )

    if tokens_total.get("columns_available") is False:
        st.info(
            "Token 列尚未创建：请在 Supabase 执行 `scripts/incident_llm_cache_tokens.sql` 后刷新。"
            if lang == "zh"
            else "Token columns missing: run scripts/incident_llm_cache_tokens.sql in Supabase."
        )
    elif tokens_total.get("rows_with_tokens", 0) < stats.get("cache_total", 0):
        st.caption(
            f"其中 {tokens_total.get('rows_with_tokens', 0)} / {stats.get('cache_total', 0)} 条缓存有 Token 记录；"
            f"历史补全在升级前写入的记录无 Token 数据。"
            if lang == "zh"
            else f"{tokens_total.get('rows_with_tokens', 0)} / {stats.get('cache_total', 0)} cache rows have token data."
        )

    if count_missing_incident_cache and remaining > 0:
        st.warning(
            f"**剩余未缓存约 {remaining} 条**（已扫描 {total_unique} 条唯一 incident，已缓存 {cached_unique} 条）。"
            f"每次补全最多处理滑块设定的条数；重复点击会继续消耗 DeepSeek API。"
            if lang == "zh"
            else f"**~{remaining} incidents still uncached** ({cached_unique}/{total_unique} unique cached in scan). Each run uses API quota."
        )
    elif count_missing_incident_cache:
        st.success(
            "当前扫描范围内 incident 已全部缓存（或无可分析事件）。" if lang == "zh"
            else "All scanned incidents are cached (or none to analyze)."
        )

    if missing_stats.get("truncated"):
        st.caption(
            f"统计基于 past_performances_v2 最近 {INCIDENT_SCAN_LIMIT} 条含 incident 的往绩；若数据库更大，实际未缓存数可能更高。"
            if lang == "zh"
            else f"Stats scan up to {INCIDENT_SCAN_LIMIT} performance rows with incidents; actual backlog may be higher."
        )

    st.markdown("**不会自动调用 DeepSeek 的功能**" if lang == "zh" else "**Does NOT auto-call DeepSeek**")
    st.markdown(
        """
- 全马基础评分榜（读 `horse_scores_cache`；仅无缓存时本地重算，用规则 incident）
- 智能投注 · 单场分析 / LightGBM（只读 `incident_llm_cache`）
- 回测 / Top1 / 排名校准（规则 incident 或缓存）
"""
        if lang == "zh"
        else """
- Horse rating leaderboard (`horse_scores_cache`; rule-based incident if rebuild)
- Smart betting single-race / LightGBM (reads `incident_llm_cache` only)
- Backtests / Top1 / rank calibration (rules or cache)
"""
    )

    recent = stats.get("recent_rows") or []
    if stats.get("cache_total", 0) > 0:
        _render_incident_cache_browser(headers, lang)
    elif recent:
        st.info("incident_llm_cache 暂无数据；请执行 scripts/incident_llm_cache.sql" if lang == "zh" else "No incident_llm_cache rows yet.")
    else:
        st.info("incident_llm_cache 暂无数据；请执行 scripts/incident_llm_cache.sql" if lang == "zh" else "No incident_llm_cache rows yet.")

    st.markdown("---")
    st.markdown("**手动补全未缓存 incident（会调用 DeepSeek API）**" if lang == "zh" else "**Backfill missing incidents (calls DeepSeek API)**")
    max_calls = st.slider(
        "本次最多 API 调用数（分批补全）" if lang == "zh" else "Max API calls this run (batch mode)",
        min_value=0,
        max_value=100,
        value=20,
        step=5,
        key="admin_deepseek_max_calls",
    )
    col_partial, col_fill_all = st.columns(2)
    with col_partial:
        if st.button("▶️ 补全未缓存 incident" if lang == "zh" else "▶️ Backfill missing incidents", key="admin_deepseek_backfill"):
            if max_calls <= 0:
                st.warning("请将最多调用数设为大于 0。" if lang == "zh" else "Set max calls above 0.")
            else:
                result = _run_admin_incident_backfill(headers, max_calls=max_calls, fill_all=False, lang=lang)
                if result:
                    _show_admin_backfill_result(result, lang)
                    st.rerun()

    with col_fill_all:
        if remaining <= 0:
            st.caption("当前无未缓存 backlog，无需一键补全。" if lang == "zh" else "No uncached backlog; fill-all not needed.")
        elif st.button("🚀 一键补全全部未缓存" if lang == "zh" else "🚀 Fill all uncached", key="admin_deepseek_fill_all_start"):
            st.session_state["admin_deepseek_fill_all_confirm"] = True

    if st.session_state.get("admin_deepseek_fill_all_confirm") and remaining > 0:
        est = (
            estimate_backfill_tokens(remaining, tokens_total)
            if estimate_backfill_tokens
            else {
                "remaining_calls": remaining,
                "avg_tokens_per_call": 450,
                "estimated_total_tokens": remaining * 450,
            }
        )
        st.warning(
            f"**费用确认**：将调用 DeepSeek API **约 {est['remaining_calls']} 次**，"
            f"预计 Token **约 {est['estimated_total_tokens']:,}**"
            f"（按历史均值约 {est['avg_tokens_per_call']} / 次估算，仅供参考）。"
            if lang == "zh"
            else (
                f"**Cost confirm**: ~{est['remaining_calls']} API calls, "
                f"~{est['estimated_total_tokens']:,} tokens estimated "
                f"({est['avg_tokens_per_call']}/call avg)."
            )
        )
        st.caption(
            "补全期间请保持此页面打开；耗时可能较长。完成后同一 incident 永久缓存，不会重复扣费。"
            if lang == "zh"
            else "Keep this page open during backfill. Cached incidents are never billed again."
        )
        confirm_cost = st.checkbox(
            f"我确认消耗约 {est['remaining_calls']} 次 DeepSeek API 调用" if lang == "zh"
            else f"I confirm ~{est['remaining_calls']} DeepSeek API calls",
            key="admin_deepseek_fill_all_ack",
        )
        c_ok, c_cancel = st.columns(2)
        with c_ok:
            if st.button("✅ 确认开始全部补全" if lang == "zh" else "✅ Confirm fill all", key="admin_deepseek_fill_all_go"):
                if not confirm_cost:
                    st.warning("请先勾选费用确认。" if lang == "zh" else "Please check the cost confirmation box.")
                else:
                    result = _run_admin_incident_backfill(
                        headers,
                        max_calls=remaining,
                        fill_all=True,
                        lang=lang,
                    )
                    st.session_state["admin_deepseek_fill_all_confirm"] = False
                    if result:
                        _show_admin_backfill_result(result, lang)
                        st.rerun()
        with c_cancel:
            if st.button("取消" if lang == "zh" else "Cancel", key="admin_deepseek_fill_all_cancel"):
                st.session_state["admin_deepseek_fill_all_confirm"] = False
                st.rerun()

    st.markdown("---")
    st.markdown("**赛日自动补全（仅管理员 / GitHub Actions）**" if lang == "zh" else "**Scheduled race-day auto backfill (admin / GitHub Actions)**")
    st.caption(
        "每天 **17:30 / 23:30 香港时间** 由 GitHub Actions 自动检查近 7 天赛日 + 本地新赛期相关 incident，"
        "仅补未缓存项（每次最多 500 条 API）。**普通用户界面不会调用 DeepSeek。**"
        if lang == "zh"
        else "GitHub Actions runs at 17:30/23:30 HKT; max 500 API calls per run. Users never trigger DeepSeek."
    )
    if run_auto_incident_backfill and st.button(
        "🔄 立即运行赛日自动补全" if lang == "zh" else "🔄 Run race-day auto backfill now",
        key="admin_deepseek_auto_run",
    ):
        auto_max = st.session_state.get("admin_deepseek_auto_max", 500)
        with st.spinner("正在执行赛日自动补全..." if lang == "zh" else "Running auto backfill..."):
            auto_result = run_auto_incident_backfill(
                SUPABASE_URL,
                headers,
                _get_deepseek_secrets(),
                max_new_calls=auto_max,
                fill_all=False,
            )
        _load_missing_incident_stats.clear()
        dates = auto_result.get("target_dates") or []
        st.success(
            f"自动补全完成：赛日 {', '.join(dates) or '-'}；"
            f"新分析 {auto_result.get('analyzed', 0)} 条，"
            f"剩余未缓存约 {auto_result.get('remaining_missing', 0)} 条，"
            f"Token {auto_result.get('total_tokens', 0):,}。"
            if lang == "zh"
            else (
                f"Auto backfill done for {dates}; analyzed {auto_result.get('analyzed', 0)}, "
                f"remaining {auto_result.get('remaining_missing', 0)}, "
                f"tokens {auto_result.get('total_tokens', 0):,}."
            )
        )
        st.rerun()


# ==================== 管理员面板 ====================
def render_admin_panel():
    """管理员面板 - 数据编辑器 + 回测 + 用户管理 + 马名映射"""
    st.markdown(f"## ⚙️ {t()['admin_panel']}")
    
    # 创建选项卡
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 数据编辑器",
        "📈 回测",
        "👥 用户管理",
        "⚙️ 评分权重设置",
        "📡 赔率采集",
        "🤖 DeepSeek",
    ])
    
    # ==================== Tab1: 数据编辑器 ====================
    with tab1:
        st.markdown("### 📋 数据库编辑器")
        st.caption("💡 双击单元格编辑 | 表格底部有 '+' 按钮添加新行 | 支持 Excel/CSV 上传")
        
        # 加载当前数据
        current_data = get_table_data("past_performances_v2", limit=500)
        
        # 定义表格列
        columns = [
            "id", "race_date", "venue", "race_no", "position", "horse_no",
            "horse_name", "horse_id", "jockey", "trainer", "actual_weight",
            "body_weight", "draw", "lbw_raw", "running_position", "finish_time",
            "finish_seconds", "odds", "closing_profile", "incident", "race_class",
            "distance", "going", "sectional_times"
        ]
        
        # 构建 DataFrame
        if current_data:
            df = pd.DataFrame(current_data)
            df = df[[c for c in columns if c in df.columns]]
        else:
            df = pd.DataFrame(columns=columns)
        
        st.info(f"📊 当前数据量: {len(df)} 条记录")
        
        col_refresh, _ = st.columns([1, 5])
        with col_refresh:
            if st.button("🔄 从数据库重新加载", use_container_width=True):
                st.rerun()
        
        st.markdown("---")
        
        with st.form(key="data_editor_form"):
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                height=500,
                num_rows="dynamic",
                key="racing_data_editor"
            )
            
            col_save1, col_save2, col_spacer = st.columns([1, 1, 3])
            
            with col_save1:
                overwrite_submitted = st.form_submit_button("💾 全量覆盖保存", type="primary", use_container_width=True)
            with col_save2:
                incremental_submitted = st.form_submit_button("🔄 增量同步保存", use_container_width=True)
            
            if overwrite_submitted:
                if edited_df is None or len(edited_df) == 0:
                    st.error("没有数据可保存")
                else:
                    with st.spinner("正在执行全量覆盖保存..."):
                        new_data = []
                        errors = 0
                        
                        for idx, row in edited_df.iterrows():
                            try:
                                if pd.isna(row['race_date']):
                                    continue
                                
                                record = {
                                    "race_date": row['race_date'].strftime('%Y-%m-%d') if hasattr(row['race_date'], 'strftime') else str(row['race_date']),
                                    "venue": str(row['venue']) if pd.notna(row['venue']) else None,
                                    "race_no": int(row['race_no']) if pd.notna(row['race_no']) else None,
                                    "position": int(row['position']) if pd.notna(row['position']) else None,
                                    "horse_no": str(row['horse_no']) if pd.notna(row['horse_no']) else None,
                                    "horse_name": str(row['horse_name']) if pd.notna(row['horse_name']) else None,
                                    "horse_id": str(row['horse_id']) if pd.notna(row['horse_id']) else None,
                                    "jockey": str(row['jockey']) if pd.notna(row['jockey']) else None,
                                    "trainer": str(row['trainer']) if pd.notna(row['trainer']) else None,
                                    "actual_weight": int(row['actual_weight']) if pd.notna(row['actual_weight']) else None,
                                    "body_weight": int(row['body_weight']) if pd.notna(row['body_weight']) else None,
                                    "draw": int(row['draw']) if pd.notna(row['draw']) else None,
                                    "lbw_raw": str(row['lbw_raw']) if pd.notna(row['lbw_raw']) else None,
                                    "running_position": str(row['running_position']) if pd.notna(row['running_position']) else None,
                                    "finish_time": str(row['finish_time']) if pd.notna(row['finish_time']) else None,
                                    "finish_seconds": float(row['finish_seconds']) if pd.notna(row['finish_seconds']) else None,
                                    "odds": float(row['odds']) if pd.notna(row['odds']) else None,
                                    "closing_profile": str(row['closing_profile']) if pd.notna(row['closing_profile']) else None,
                                    "incident": str(row['incident']) if pd.notna(row['incident']) else None,
                                    "race_class": str(row['race_class']) if pd.notna(row['race_class']) else None,
                                    "distance": int(row['distance']) if pd.notna(row['distance']) else None,
                                    "going": str(row['going']) if pd.notna(row['going']) else None,
                                    "sectional_times": str(row['sectional_times']) if pd.notna(row['sectional_times']) else None,
                                }
                                new_data.append(record)
                            except Exception as e:
                                errors += 1
                        
                        if errors > 0:
                            st.warning(f"跳过 {errors} 行无效数据")
                        
                        if new_data:
                            success = save_table_data("past_performances_v2", new_data)
                            if success:
                                st.success(f"全量覆盖保存 {len(new_data)} 条记录成功！")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("保存失败")
                        else:
                            st.error("没有有效数据可保存")
            
            if incremental_submitted:
                if edited_df is None or len(edited_df) == 0:
                    st.error("没有数据可同步")
                else:
                    with st.spinner("正在执行增量同步..."):
                        new_data = []
                        errors = 0
                        
                        for idx, row in edited_df.iterrows():
                            try:
                                if pd.isna(row['race_date']):
                                    continue
                                
                                record = {
                                    "race_date": row['race_date'].strftime('%Y-%m-%d') if hasattr(row['race_date'], 'strftime') else str(row['race_date']),
                                    "venue": str(row['venue']) if pd.notna(row['venue']) else None,
                                    "race_no": int(row['race_no']) if pd.notna(row['race_no']) else None,
                                    "position": int(row['position']) if pd.notna(row['position']) else None,
                                    "horse_no": str(row['horse_no']) if pd.notna(row['horse_no']) else None,
                                    "horse_name": str(row['horse_name']) if pd.notna(row['horse_name']) else None,
                                    "horse_id": str(row['horse_id']) if pd.notna(row['horse_id']) else None,
                                    "jockey": str(row['jockey']) if pd.notna(row['jockey']) else None,
                                    "trainer": str(row['trainer']) if pd.notna(row['trainer']) else None,
                                    "actual_weight": int(row['actual_weight']) if pd.notna(row['actual_weight']) else None,
                                    "body_weight": int(row['body_weight']) if pd.notna(row['body_weight']) else None,
                                    "draw": int(row['draw']) if pd.notna(row['draw']) else None,
                                    "lbw_raw": str(row['lbw_raw']) if pd.notna(row['lbw_raw']) else None,
                                    "running_position": str(row['running_position']) if pd.notna(row['running_position']) else None,
                                    "finish_time": str(row['finish_time']) if pd.notna(row['finish_time']) else None,
                                    "finish_seconds": float(row['finish_seconds']) if pd.notna(row['finish_seconds']) else None,
                                    "odds": float(row['odds']) if pd.notna(row['odds']) else None,
                                    "closing_profile": str(row['closing_profile']) if pd.notna(row['closing_profile']) else None,
                                    "incident": str(row['incident']) if pd.notna(row['incident']) else None,
                                    "race_class": str(row['race_class']) if pd.notna(row['race_class']) else None,
                                    "distance": int(row['distance']) if pd.notna(row['distance']) else None,
                                    "going": str(row['going']) if pd.notna(row['going']) else None,
                                    "sectional_times": str(row['sectional_times']) if pd.notna(row['sectional_times']) else None,
                                }
                                new_data.append(record)
                            except Exception as e:
                                errors += 1
                        
                        if errors > 0:
                            st.warning(f"跳过 {errors} 行无效数据")
                        
                        if new_data:
                            result = incremental_sync_table("past_performances_v2", new_data)
                            st.success(f"增量同步完成：新增 {result['inserted']} 条，更新 {result['updated']} 条，删除 {result['deleted']} 条")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("没有有效数据可同步")
        
        st.markdown("---")
        
        # Excel/CSV 上传区域
        st.markdown("### 📎 Excel/CSV 文件上传")
        st.caption("格式：CSV 或 Excel，列名需与数据库字段匹配")
        
        uploaded_file = st.file_uploader(
            "选择文件",
            type=['csv', 'xlsx', 'xls'],
            key="racing_uploader",
            help="上传 CSV 或 Excel 文件"
        )
        
        if uploaded_file is not None:
            import io
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_upload = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                else:
                    df_upload = pd.read_excel(uploaded_file)
                
                st.success(f"成功解析 {len(df_upload)} 行数据")
                st.dataframe(df_upload.head(10), use_container_width=True)
                
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("✅ 确认导入并覆盖", type="primary"):
                        upload_data = df_upload.to_dict(orient='records')
                        success = save_table_data("past_performances_v2", upload_data)
                        if success:
                            st.success(f"导入 {len(upload_data)} 条记录成功！")
                            st.rerun()
                        else:
                            st.error("导入失败")
                with col_cancel:
                    if st.button("❌ 取消"):
                        st.rerun()
            except Exception as e:
                st.error(f"文件解析失败: {e}")
    
    # ==================== Tab2: 回测 ====================
    with tab2:
        # ⭐ 替换为管理员专用回测（带特征重要性）
        render_admin_backtest()
    
    # ==================== Tab3: 用户管理 ====================
    with tab3:
        render_user_management()
    #-----------------
    # ==================== Tab4: 评分设置 ====================
    with tab4:
        st.markdown('### ⚙️ 评分权重设置')
        st.caption('设置各级评分因子的权重（所有权重总和必须为100%）')
        
        # 获取当前语言
        lang = st.session_state.get("lang", "zh")
        
        # 从数据库加载当前配置
        @st.cache_data(ttl=60, show_spinner=False)
        def load_scoring_config():
            try:
                headers = get_supabase_headers(use_secret=True)
                url = f"{SUPABASE_URL}/rest/v1/scoring_config?id=eq.1"
                response = requests.get(url, headers=headers)
                if response.status_code == 200 and response.json():
                    return response.json()[0]
                return None
            except Exception as e:
                st.error(f"加载配置失败: {e}")
                return None
        
        # 保存配置到数据库
        def save_scoring_config(config_data):
            try:
                headers = get_supabase_headers(use_secret=True)
                url = f"{SUPABASE_URL}/rest/v1/scoring_config?id=eq.1"
                response = requests.patch(url, headers=headers, json=config_data)
                if response.status_code in [200, 204]:
                    # 清除缓存，重新加载
                    st.cache_data.clear()
                    return True
                else:
                    st.error(f"保存失败: {response.text}")
                    return False
            except Exception as e:
                st.error(f"保存失败: {e}")
                return False
        
        # 加载当前配置
        config = load_scoring_config()
        
        if config is None:
            st.error("无法加载评分配置，请检查数据库表 scoring_config 是否存在")
            return
        
        # 初始化 session_state 中的临时配置
        if "admin_scoring_config" not in st.session_state:
            st.session_state.admin_scoring_config = {
                "level1_weights": config.get("level1_weights", {}),
                "basic_weights": config.get("basic_weights", {}),
                "race_weights": config.get("race_weights", {}),
                "odds_weights": config.get("odds_weights", {}),
                "status_weights": config.get("status_weights", {})
            }
        
        # 获取当前编辑的配置
        level1 = st.session_state.admin_scoring_config["level1_weights"].copy()
        basic_w = st.session_state.admin_scoring_config["basic_weights"].copy()
        race_w = st.session_state.admin_scoring_config["race_weights"].copy()
        odds_w = st.session_state.admin_scoring_config["odds_weights"].copy()
        status_w = st.session_state.admin_scoring_config["status_weights"].copy()
        
        # 辅助函数：检查一级因子总和
        def check_level1_sum():
            total = level1.get("basic", 0) + level1.get("race", 0) + level1.get("odds", 0) + level1.get("status", 0)
            return total
        #-----------
        # ==================== 一级因子设置 ====================
        if lang == "zh":
            st.markdown('#### 📊 一级因子权重')
            st.caption("调整各主要维度的权重，总和必须为100%")
        else:
            st.markdown("#### 📊 Level 1 Weights")
            st.caption("Adjust main dimension weights, total must be 100%")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            basic_val = st.number_input(
                "基础往绩" if lang == "zh" else "Basic Performance",
                min_value=0, max_value=100, value=int(level1.get("basic", 0.30) * 100),
                step=1, key="admin_basic_weight"
            )
            level1["basic"] = basic_val / 100
        
        with col2:
            race_val = st.number_input(
                "场次因素" if lang == "zh" else "Race Factors",
                min_value=0, max_value=100, value=int(level1.get("race", 0.35) * 100),
                step=1, key="admin_race_weight"
            )
            level1["race"] = race_val / 100
        
        with col3:
            odds_val = st.number_input(
                "赔率因素" if lang == "zh" else "Odds Factors",
                min_value=0, max_value=100, value=int(level1.get("odds", 0.20) * 100),
                step=1, key="admin_odds_weight"
            )
            level1["odds"] = odds_val / 100
        
        with col4:
            status_val = st.number_input(
                "状态因素" if lang == "zh" else "Status Factors",
                min_value=0, max_value=100, value=int(level1.get("status", 0.15) * 100),
                step=1, key="admin_status_weight"
            )
            level1["status"] = status_val / 100
        
        # ✅ 计算总和（百分比）
        total_level1 = (level1.get("basic", 0) + level1.get("race", 0) + 
                        level1.get("odds", 0) + level1.get("status", 0)) * 100
        
        # ✅ 显示总和校验（使用 abs 处理浮点数精度）
        if abs(total_level1 - 100) < 0.01:
            st.success(f"✅ 当前总和: {round(total_level1)}%" if lang == "zh" else f"✅ Total: {round(total_level1)}%")
        else:
            st.error(f"❌ 当前总和: {total_level1:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_level1:.0f}%, must be 100%")
        
        st.markdown("---")
        
        # ==================== 基础往绩二级因子 ====================
        with st.expander("📈 基础往绩 - 二级因子权重" if lang == "zh" else "📈 Basic Performance - Level 2 Weights", expanded=False):
            st.caption("调整基础往绩内部的子因子权重，总和必须为100%" if lang == "zh" else "Adjust sub-factor weights, total must be 100%")
            
            col1, col2 = st.columns(2)
            with col1:
                win3 = st.number_input(
                    "近3场胜率" if lang == "zh" else "Win Rate (Last 3)",
                    min_value=0, max_value=100, value=int(basic_w.get("win_rate_3", 0.20) * 100),
                    step=1, key="admin_win3"
                )
                win10 = st.number_input(
                    "近10场胜率" if lang == "zh" else "Win Rate (Last 10)",
                    min_value=0, max_value=100, value=int(basic_w.get("win_rate_10", 0.20) * 100),
                    step=1, key="admin_win10"
                )
                place10 = st.number_input(
                    "近10场入Q率" if lang == "zh" else "Place Rate (Last 10)",
                    min_value=0, max_value=100, value=int(basic_w.get("place_rate_10", 0.15) * 100),
                    step=1, key="admin_place10"
                )
            with col2:
                show10 = st.number_input(
                    "近10场入T率" if lang == "zh" else "Show Rate (Last 10)",
                    min_value=0, max_value=100, value=int(basic_w.get("show_rate_10", 0.15) * 100),
                    step=1, key="admin_show10"
                )
                distance_rating = st.number_input(
                    "同程表现评分" if lang == "zh" else "Distance Rating",
                    min_value=0, max_value=100, value=int(basic_w.get("distance_rating", 0.15) * 100),
                    step=1, key="admin_distance"
                )
                trend = st.number_input(
                    "名次趋势" if lang == "zh" else "Ranking Trend",
                    min_value=0, max_value=100, value=int(basic_w.get("trend", 0.15) * 100),
                    step=1, key="admin_trend"
                )
            
            # 更新权重字典
            basic_w["win_rate_3"] = win3 / 100
            basic_w["win_rate_10"] = win10 / 100
            basic_w["place_rate_10"] = place10 / 100
            basic_w["show_rate_10"] = show10 / 100
            basic_w["distance_rating"] = distance_rating / 100
            basic_w["trend"] = trend / 100
            
            total_basic = sum(basic_w.values()) * 100
            if abs(total_basic - 100) < 0.1:
                st.success(f"✅ 当前总和: {total_basic:.0f}%" if lang == "zh" else f"✅ Total: {total_basic:.0f}%")
            else:
                st.error(f"❌ 当前总和: {total_basic:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_basic:.0f}%, must be 100%")
        
        # ==================== 场次因素二级因子 ====================
        with st.expander("🏟️ 场次因素 - 二级因子权重" if lang == "zh" else "🏟️ Race Factors - Level 2 Weights", expanded=False):
            st.caption("调整场次因素内部的子因子权重，总和必须为100%" if lang == "zh" else "Adjust sub-factor weights, total must be 100%")
            
            col1, col2 = st.columns(2)
            with col1:
                same_course = st.number_input(
                    "同场地胜率" if lang == "zh" else "Same Course",
                    min_value=0, max_value=100, value=int(race_w.get("same_course", 0.25) * 100),
                    step=1, key="admin_same_course"
                )
                same_distance = st.number_input(
                    "同路程胜率" if lang == "zh" else "Same Distance",
                    min_value=0, max_value=100, value=int(race_w.get("same_distance", 0.25) * 100),
                    step=1, key="admin_same_distance"
                )
                draw = st.number_input(
                    "档位优势" if lang == "zh" else "Draw Advantage",
                    min_value=0, max_value=100, value=int(race_w.get("draw", 0.15) * 100),
                    step=1, key="admin_draw"
                )
            with col2:
                weight = st.number_input(
                    "负磅变化" if lang == "zh" else "Weight Change",
                    min_value=0, max_value=100, value=int(race_w.get("weight", 0.10) * 100),
                    step=1, key="admin_weight"
                )
                jockey = st.number_input(
                    "骑师配合" if lang == "zh" else "Jockey",
                    min_value=0, max_value=100, value=int(race_w.get("jockey", 0.15) * 100),
                    step=1, key="admin_jockey"
                )
                trainer = st.number_input(
                    "练马师状态" if lang == "zh" else "Trainer",
                    min_value=0, max_value=100, value=int(race_w.get("trainer", 0.10) * 100),
                    step=1, key="admin_trainer"
                )
            
            race_w["same_course"] = same_course / 100
            race_w["same_distance"] = same_distance / 100
            race_w["draw"] = draw / 100
            race_w["weight"] = weight / 100
            race_w["jockey"] = jockey / 100
            race_w["trainer"] = trainer / 100
            
            total_race = sum(race_w.values()) * 100
            if abs(total_race - 100) < 0.1:
                st.success(f"✅ 当前总和: {total_race:.0f}%" if lang == "zh" else f"✅ Total: {total_race:.0f}%")
            else:
                st.error(f"❌ 当前总和: {total_race:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_race:.0f}%, must be 100%")
        
        # ==================== 赔率因素二级因子 ====================
        with st.expander("💰 赔率因素 - 二级因子权重" if lang == "zh" else "💰 Odds Factors - Level 2 Weights", expanded=False):
            st.caption("调整赔率因素内部的子因子权重，总和必须为100%" if lang == "zh" else "Adjust sub-factor weights, total must be 100%")
            
            col1, col2 = st.columns(2)
            with col1:
                win_odds = st.number_input(
                    "独赢赔率" if lang == "zh" else "Win Odds",
                    min_value=0, max_value=100, value=int(odds_w.get("win_odds", 0.60) * 100),
                    step=1, key="admin_win_odds"
                )
            with col2:
                odds_trend = st.number_input(
                    "赔率变动趋势" if lang == "zh" else "Odds Trend",
                    min_value=0, max_value=100, value=int(odds_w.get("odds_trend", 0.40) * 100),
                    step=1, key="admin_odds_trend"
                )
            
            odds_w["win_odds"] = win_odds / 100
            odds_w["odds_trend"] = odds_trend / 100
            
            total_odds = sum(odds_w.values()) * 100
            if abs(total_odds - 100) < 0.1:
                st.success(f"✅ 当前总和: {total_odds:.0f}%" if lang == "zh" else f"✅ Total: {total_odds:.0f}%")
            else:
                st.error(f"❌ 当前总和: {total_odds:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_odds:.0f}%, must be 100%")
        
        # ==================== 状态因素二级因子 ====================
        with st.expander("🩺 状态因素 - 二级因子权重" if lang == "zh" else "🩺 Status Factors - Level 2 Weights", expanded=False):
            st.caption("调整状态因素内部的子因子权重，总和必须为100%" if lang == "zh" else "Adjust sub-factor weights, total must be 100%")
            
            col1, col2 = st.columns(2)
            with col1:
                age = st.number_input(
                    "马龄因子" if lang == "zh" else "Age Factor",
                    min_value=0, max_value=100, value=int(status_w.get("age", 0.30) * 100),
                    step=1, key="admin_age"
                )
                weight_change = st.number_input(
                    "体重变化" if lang == "zh" else "Weight Change",
                    min_value=0, max_value=100, value=int(status_w.get("weight_change", 0.25) * 100),
                    step=1, key="admin_weight_change"  # ← 改为 admin_weight_change
                )
            with col2:
                incident = st.number_input(
                    "事件报告" if lang == "zh" else "Incident",
                    min_value=0, max_value=100, value=int(status_w.get("incident", 0.25) * 100),
                    step=1, key="admin_incident"
                )
                burst = st.number_input(
                    "冲刺能力" if lang == "zh" else "Burst",
                    min_value=0, max_value=100, value=int(status_w.get("burst", 0.20) * 100),
                    step=1, key="admin_burst"
                )
            
            status_w["age"] = age / 100
            status_w["weight_change"] = weight_change / 100
            status_w["incident"] = incident / 100
            status_w["burst"] = burst / 100
            
            total_status = sum(status_w.values()) * 100
            # ✅ 使用 round() 解决浮点数精度问题
            if abs(total_status - 100) < 0.01:
                st.success(f"✅ 当前总和: {round(total_status)}%" if lang == "zh" else f"✅ Total: {round(total_status)}%")
            else:
                st.error(f"❌ 当前总和: {total_status:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_status:.0f}%, must be 100%")
        
        st.markdown("---")
        #----------------
        # ==================== ML 模型参数设置 ====================
        with st.expander("🤖 ML 模型参数" if lang == "zh" else "🤖 ML Model Parameters", expanded=False):
            st.caption("调整机器学习模型的训练参数（修改后需重新运行回测生效）" if lang == "zh" else "Adjust ML model training parameters (restart backtest to apply)")
            
            # 获取当前 ML 配置
            from scoring_engine import get_ml_config, update_ml_config
            ml_config = get_ml_config()
            
            # 数据配置
            if lang == "zh":
                st.markdown("**📊 数据配置**")
            else:
                st.markdown("**📊 Data Configuration**")
            
            col1, col2 = st.columns(2)
            with col1:
                recent_games = st.number_input(
                    "最近比赛场数" if lang == "zh" else "Recent Games",
                    min_value=10, max_value=100, value=int(ml_config.get("recent_games", 30)),
                    step=5, key="admin_ml_recent_games"
                )
            with col2:
                top_n_horses = st.number_input(
                    "关注前N名马" if lang == "zh" else "Top N Horses",
                    min_value=2, max_value=6, value=int(ml_config.get("top_n_horses", 4)),
                    step=1, key="admin_ml_top_n"
                )
            
            # LightGBM 参数
            if lang == "zh":
                st.markdown("**🌳 LightGBM 参数**")
            else:
                st.markdown("**🌳 LightGBM Parameters**")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                lgb_n_estimators = st.number_input(
                    "树数量" if lang == "zh" else "Trees",
                    min_value=10, max_value=200, value=int(ml_config.get("lgb_n_estimators", 50)),
                    step=10, key="admin_lgb_trees"
                )
                lgb_max_depth = st.number_input(
                    "最大深度" if lang == "zh" else "Max Depth",
                    min_value=2, max_value=10, value=int(ml_config.get("lgb_max_depth", 4)),
                    step=1, key="admin_lgb_depth"
                )
            with col2:
                lgb_learning_rate = st.number_input(
                    "学习率" if lang == "zh" else "Learning Rate",
                    min_value=0.01, max_value=0.5, value=float(ml_config.get("lgb_learning_rate", 0.1)),
                    step=0.01, format="%.2f", key="admin_lgb_lr"
                )
                lgb_num_leaves = st.number_input(
                    "叶子数" if lang == "zh" else "Leaves",
                    min_value=4, max_value=64, value=int(ml_config.get("lgb_num_leaves", 16)),
                    step=2, key="admin_lgb_leaves"
                )
            with col3:
                lgb_subsample = st.number_input(
                    "子采样" if lang == "zh" else "Subsample",
                    min_value=0.5, max_value=1.0, value=float(ml_config.get("lgb_subsample", 0.7)),
                    step=0.05, format="%.2f", key="admin_lgb_subsample"
                )
                lgb_colsample = st.number_input(
                    "特征采样" if lang == "zh" else "Colsample",
                    min_value=0.5, max_value=1.0, value=float(ml_config.get("lgb_colsample_bytree", 0.7)),
                    step=0.05, format="%.2f", key="admin_lgb_colsample"
                )
            
            # XGBoost 参数
            if lang == "zh":
                st.markdown("**🌲 XGBoost 参数**")
            else:
                st.markdown("**🌲 XGBoost Parameters**")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                xgb_n_estimators = st.number_input(
                    "树数量" if lang == "zh" else "Trees",
                    min_value=10, max_value=200, value=int(ml_config.get("xgb_n_estimators", 80)),
                    step=10, key="admin_xgb_trees"
                )
                xgb_max_depth = st.number_input(
                    "最大深度" if lang == "zh" else "Max Depth",
                    min_value=2, max_value=10, value=int(ml_config.get("xgb_max_depth", 6)),
                    step=1, key="admin_xgb_depth"
                )
            with col2:
                xgb_learning_rate = st.number_input(
                    "学习率" if lang == "zh" else "Learning Rate",
                    min_value=0.01, max_value=0.5, value=float(ml_config.get("xgb_learning_rate", 0.08)),
                    step=0.01, format="%.2f", key="admin_xgb_lr"
                )
            with col3:
                xgb_subsample = st.number_input(
                    "子采样" if lang == "zh" else "Subsample",
                    min_value=0.5, max_value=1.0, value=float(ml_config.get("xgb_subsample", 0.8)),
                    step=0.05, format="%.2f", key="admin_xgb_subsample"
                )
                xgb_colsample = st.number_input(
                    "特征采样" if lang == "zh" else "Colsample",
                    min_value=0.5, max_value=1.0, value=float(ml_config.get("xgb_colsample_bytree", 0.8)),
                    step=0.05, format="%.2f", key="admin_xgb_colsample"
                )
            
            # 保存按钮
            if st.button("💾 保存 ML 参数" if lang == "zh" else "💾 Save ML Parameters", use_container_width=True):
                new_ml_config = {
                    "recent_games": int(recent_games),
                    "top_n_horses": int(top_n_horses),
                    "min_races_for_train": 100,
                    "lgb_n_estimators": int(lgb_n_estimators),
                    "lgb_max_depth": int(lgb_max_depth),
                    "lgb_learning_rate": float(lgb_learning_rate),
                    "lgb_num_leaves": int(lgb_num_leaves),
                    "lgb_subsample": float(lgb_subsample),
                    "lgb_colsample_bytree": float(lgb_colsample),
                    "xgb_n_estimators": int(xgb_n_estimators),
                    "xgb_max_depth": int(xgb_max_depth),
                    "xgb_learning_rate": float(xgb_learning_rate),
                    "xgb_subsample": float(xgb_subsample),
                    "xgb_colsample_bytree": float(xgb_colsample),
                }
                update_ml_config(new_ml_config)
                st.success("✅ ML 参数已保存" if lang == "zh" else "✅ ML Parameters saved")
                # 清空模型缓存
                clear_model_cache()
                st.info("🔄 模型缓存已清空，下次回测将使用新参数" if lang == "zh" else "🔄 Model cache cleared, new parameters will be used")
            
            # 重置按钮
            if st.button("🔄 重置 ML 参数为默认" if lang == "zh" else "🔄 Reset ML Parameters", use_container_width=True):
                from scoring_engine import reset_ml_config
                reset_ml_config()
                st.success("✅ ML 参数已重置" if lang == "zh" else "✅ ML Parameters reset")
                clear_model_cache()
                st.rerun()
            
            # 显示当前参数摘要
            if lang == "zh":
                st.caption(f"💡 当前: LightGBM(树={lgb_n_estimators}, 深度={lgb_max_depth}) | XGBoost(树={xgb_n_estimators}, 深度={xgb_max_depth})")
            else:
                st.caption(f"💡 Current: LightGBM(trees={lgb_n_estimators}, depth={lgb_max_depth}) | XGBoost(trees={xgb_n_estimators}, depth={xgb_max_depth})")
        # ==================== 保存按钮 ====================
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💾 保存配置" if lang == "zh" else "💾 Save Config", type="primary", use_container_width=True):
                # 检查一级因子总和
                if check_level1_sum() != 100:
                    st.error("一级因子总和必须为100%，请调整后重试" if lang == "zh" else "Level 1 weights must sum to 100%")
                elif abs(sum(basic_w.values()) - 1) > 0.01:
                    st.error("基础往绩二级因子总和必须为100%，请调整后重试" if lang == "zh" else "Basic weights must sum to 100%")
                elif abs(sum(race_w.values()) - 1) > 0.01:
                    st.error("场次因素二级因子总和必须为100%，请调整后重试" if lang == "zh" else "Race weights must sum to 100%")
                elif abs(sum(odds_w.values()) - 1) > 0.01:
                    st.error("赔率因素二级因子总和必须为100%，请调整后重试" if lang == "zh" else "Odds weights must sum to 100%")
                elif abs(sum(status_w.values()) - 1) > 0.01:
                    st.error("状态因素二级因子总和必须为100%，请调整后重试" if lang == "zh" else "Status weights must sum to 100%")
                else:
                    config_data = {
                        "level1_weights": level1,
                        "basic_weights": basic_w,
                        "race_weights": race_w,
                        "odds_weights": odds_w,
                        "status_weights": status_w,
                        "updated_by": st.session_state.user_email,
                        "updated_at": datetime.now().isoformat()
                    }
                    if save_scoring_config(config_data):
                        st.success("配置已保存" if lang == "zh" else "Config saved")
                        st.cache_data.clear()
                        st.rerun()
        
        with col2:
            if st.button("🔄 重置为默认" if lang == "zh" else "🔄 Reset to Default", use_container_width=True):
                # 重置为默认值
                st.session_state.admin_scoring_config = {
                    "level1_weights": {"basic": 0.30, "race": 0.35, "odds": 0.20, "status": 0.15},
                    "basic_weights": {"win_rate_3": 0.20, "win_rate_10": 0.20, "place_rate_10": 0.15, "show_rate_10": 0.15, "distance_rating": 0.15, "trend": 0.15},
                    "race_weights": {"same_course": 0.25, "same_distance": 0.25, "draw": 0.15, "weight": 0.10, "jockey": 0.15, "trainer": 0.10},
                    "odds_weights": {"win_odds": 0.60, "odds_trend": 0.40},
                    "status_weights": {"age": 0.30, "weight_change": 0.25, "incident": 0.25, "burst": 0.20}
                }
                st.rerun()
        
        st.caption("💡 提示：修改权重后需要点击「保存配置」才会生效，所有用户将使用新配置" if lang == "zh" else "💡 Hint: Click 'Save Config' after modification, all users will use the new configuration")

        st.markdown("---")
        with st.expander("⚡ 预计算评分（加速智能投注）", expanded=False):
            st.markdown("预计算未来赛事的评分，保存到缓存，大幅提升智能投注页面加载速度")

            col1, col2 = st.columns(2)
            with col1:
                precompute_date = st.date_input(
                    "选择日期",
                    value=datetime.now(),
                    key="precompute_date"
                )
            with col2:
                precompute_venue = st.selectbox(
                    "选择场地",
                    options=["全部", "ST", "HV"],
                    key="precompute_venue"
                )

            if st.button("🚀 开始预计算", type="primary", use_container_width=True):
                with st.spinner(f"正在预计算 {precompute_date} 的赛事评分..."):
                    venue = None if precompute_venue == "全部" else precompute_venue
                    user_weights = {"basic": 0.30, "race": 0.40, "odds": 0.30}
                    result = precompute_all_races_for_date(
                        precompute_date.strftime("%Y-%m-%d"),
                        venue,
                        user_weights
                    )
                    st.success(f"预计算完成：成功 {result['success']} 场，失败 {result['failed']} 场，共 {result['total']} 场")

        with st.expander("🗑️ 清除缓存", expanded=False):
            if st.button("清除评分缓存", use_container_width=True):
                get_cached_race_scores.clear()
                st.success("缓存已清除")
                st.rerun()

    with tab5:
        render_admin_odds_collection()

    with tab6:
        render_admin_deepseek_usage()

    st.markdown("---")
    if st.button("退出管理员模式", use_container_width=True):
        admin_sign_out()
        st.rerun()
#-------
def render_user_management():
    """用户管理界面（完整版：系统统计 + 用户列表 + 用户管理 + 操作 + 批量操作）"""
    
    # ==================== 辅助函数 ====================
    def get_all_users_from_auth() -> List[Dict]:
        """从 Supabase Auth 获取所有用户列表（管理员用）"""
        try:
            url = f"{SUPABASE_URL}/auth/v1/admin/users"
            headers = get_supabase_headers(use_secret=True)
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                users = response.json().get("users", [])
                return users
            return []
        except Exception as e:
            print(f"获取用户列表失败: {e}")
            return []
    
    def get_user_auth_details_from_api(user_id: str) -> Dict:
        """获取单个用户的认证详细信息"""
        try:
            url = f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}"
            headers = get_supabase_headers(use_secret=True)
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "created_at": data.get("created_at", ""),
                    "last_sign_in_at": data.get("last_sign_in_at", ""),
                    "email_confirmed_at": data.get("email_confirmed_at", "")
                }
        except Exception as e:
            print(f"获取用户认证信息失败: {e}")
        
        return {"created_at": "", "last_sign_in_at": "", "email_confirmed_at": ""}
    
    def get_user_stock_summary_racing(user_id: str) -> Dict:
        """获取用户的股票池摘要（针对赛马App）"""
        try:
            headers = get_supabase_headers(use_secret=True)
            
            # 查询用户设置
            settings_url = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
            settings_response = requests.get(settings_url, headers=headers)
            
            return {
                "has_settings": 1 if settings_response.status_code == 200 and settings_response.json() else 0,
                "recommended_count": 0,  # 赛马App没有推荐池
                "backtest_count": 0,     # 赛马App没有回测池
                "live_count": 0          # 赛马App没有实操池
            }
        except Exception as e:
            print(f"获取用户摘要失败: {e}")
            return {"has_settings": 0, "recommended_count": 0, "backtest_count": 0, "live_count": 0}
    
    def admin_send_password_reset(email: str) -> Tuple[bool, str]:
        """发送密码重置邮件"""
        try:
            url = f"{SUPABASE_URL}/auth/v1/recover"
            headers = {
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Content-Type": "application/json"
            }
            data = {"email": email}
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return True, f"密码重置邮件已发送至 {email}"
            else:
                return False, f"发送失败: {response.text}"
        except Exception as e:
            return False, f"发送失败: {str(e)}"
    
    def admin_delete_user_from_auth(user_id: str, user_email: str) -> Tuple[bool, str]:
        """管理员删除用户（Auth + 相关表）"""
        try:
            headers = get_supabase_headers(use_secret=True)
            
            # 1. 删除 user_settings_racing 记录
            settings_url = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
            requests.delete(settings_url, headers=headers)
            
            # 2. 删除用户预设板块（如果有）
            preset_url = f"{SUPABASE_URL}/rest/v1/user_preset_sectors?user_id=eq.{user_id}"
            requests.delete(preset_url, headers=headers)
            
            # 3. 删除用户热点板块缓存
            hot_url = f"{SUPABASE_URL}/rest/v1/user_hot_sectors?user_id=eq.{user_id}"
            requests.delete(hot_url, headers=headers)
            
            # 4. 删除用户龙头股缓存
            leader_url = f"{SUPABASE_URL}/rest/v1/user_leader_stocks_cache?user_id=eq.{user_id}"
            requests.delete(leader_url, headers=headers)
            
            # 5. 删除用户板块成分股
            stocks_url = f"{SUPABASE_URL}/rest/v1/user_sector_stocks?user_id=eq.{user_id}"
            requests.delete(stocks_url, headers=headers)
            
            # 6. 删除 Auth 用户
            auth_url = f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}"
            auth_response = requests.delete(auth_url, headers=headers)
            
            if auth_response.status_code in [200, 204]:
                return True, f"用户 {user_email} 已删除"
            else:
                return False, f"删除Auth用户失败: {auth_response.text}"
                
        except Exception as e:
            return False, f"删除失败: {str(e)}"
    
    def admin_reset_user_trials_racing(user_id: str, new_trials: int = FREE_TRIAL_LIMIT) -> Tuple[bool, str]:
        """重置用户的免费次数"""
        try:
            success = update_user_profile(user_id, {"free_trials_remaining": new_trials})
            if success:
                return True, f"已重置免费次数为 {new_trials}"
            return False, "重置失败"
        except Exception as e:
            return False, f"重置失败: {str(e)}"
    
    def admin_set_subscription_racing(user_id: str, tier: str, months: int = 1) -> Tuple[bool, str]:
        """设置用户订阅等级"""
        try:
            data = {"subscription_tier": tier}
            if tier == "pro":
                expires_at = (datetime.now() + timedelta(days=30 * months)).isoformat()
                data["subscription_expires_at"] = expires_at
            else:
                data["subscription_expires_at"] = None
            
            success = update_user_profile(user_id, data)
            if success:
                return True, f"用户订阅已设置为 {tier}"
            return False, "设置失败"
        except Exception as e:
            return False, f"设置失败: {str(e)}"
    
    # ==================== 主界面 ====================
    st.markdown("### 👥 用户管理")
    
    # 获取所有用户（从 user_settings_racing 表获取已注册赛马App的用户）
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/user_settings_racing"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            db_users = response.json()
        else:
            st.error(f"获取用户数据失败: {response.status_code}")
            db_users = []
    except Exception as e:
        st.error(f"获取用户数据失败: {e}")
        db_users = []
    
    if not db_users:
        st.info("暂无用户数据")
        return
    
    # 获取 Auth 用户详细信息
    auth_users = get_all_users_from_auth()
    auth_user_map = {u.get("id"): u for u in auth_users}
    
    # 构建用户详细列表
    users_with_details = []
    for user in db_users:
        user_id = user.get("user_id")
        auth_info = auth_user_map.get(user_id, {})
        stock_summary = get_user_stock_summary_racing(user_id)
        
        users_with_details.append({
            "id": user_id,
            "email": user.get("email", ""),
            "subscription_tier": user.get("subscription_tier", "free"),
            "free_trials_remaining": user.get("free_trials_remaining", FREE_TRIAL_LIMIT),
            "subscription_expires_at": user.get("subscription_expires_at", "")[:10] if user.get("subscription_expires_at") else "-",
            "created_at": auth_info.get("created_at", "")[:10] if auth_info.get("created_at") else "-",
            "last_sign_in_at": auth_info.get("last_sign_in_at", "")[:10] if auth_info.get("last_sign_in_at") else "-",
            "email_confirmed": "✅" if auth_info.get("email_confirmed_at") else "❌",
            "has_settings": stock_summary["has_settings"]
        })
    
    # ==================== 系统统计 ====================
    st.markdown("#### 📊 系统统计")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总用户数", len(users_with_details))
    with col2:
        pro_count = sum(1 for u in users_with_details if u["subscription_tier"] == "pro")
        st.metric("专业版用户", pro_count)
    with col3:
        free_count = len(users_with_details) - pro_count
        st.metric("免费版用户", free_count)
    with col4:
        total_settings = sum(u["has_settings"] for u in users_with_details)
        st.metric("已配置用户", total_settings)
    
    st.markdown("---")
    
    # ==================== 用户列表 ====================
    st.markdown("#### 📋 用户列表")
    
    df_users = pd.DataFrame(users_with_details)
    display_columns = ["email", "subscription_tier", "free_trials_remaining", 
                       "subscription_expires_at", "created_at", "last_sign_in_at",
                       "email_confirmed"]
    
    # 确保所有列都存在
    available_cols = [c for c in display_columns if c in df_users.columns]
    
    st.dataframe(
        df_users[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "email": "邮箱",
            "subscription_tier": "订阅等级",
            "free_trials_remaining": "剩余次数",
            "subscription_expires_at": "到期时间",
            "created_at": "注册时间",
            "last_sign_in_at": "最后登录",
            "email_confirmed": "邮箱确认"
        }
    )
    
    st.caption(f"共 {len(users_with_details)} 位用户")
    
    st.markdown("---")
    
    # ==================== 用户管理 ====================
    st.markdown("#### 🔧 用户管理")
    
    user_options = [f"{u['email']} ({u['subscription_tier']})" for u in users_with_details]
    selected_user_str = st.selectbox("选择用户", user_options, key="admin_select_user")
    selected_email = selected_user_str.split(" ")[0]
    selected_user = next((u for u in users_with_details if u["email"] == selected_email), None)
    
    if selected_user:
        st.markdown(f"**当前用户**: {selected_user['email']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📝 修改订阅**")
            new_tier = st.selectbox(
                "订阅等级", 
                ["free", "pro"], 
                index=0 if selected_user["subscription_tier"] == "free" else 1, 
                key="admin_new_tier"
            )
            pro_months = 1
            if new_tier == "pro":
                pro_months = st.number_input("月数", min_value=1, max_value=12, value=1, key="admin_months")
            
            if st.button("更新订阅", key="admin_update_subscription", use_container_width=True):
                success, msg = admin_set_subscription_racing(selected_user["id"], new_tier, pro_months)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        with col2:
            st.markdown("**🎫 免费次数**")
            new_trials = st.number_input(
                "设置剩余次数", 
                min_value=0, 
                max_value=100, 
                value=int(selected_user["free_trials_remaining"]), 
                key="admin_new_trials"
            )
            if st.button("重置次数", key="admin_reset_trials", use_container_width=True):
                success, msg = admin_reset_user_trials_racing(selected_user["id"], new_trials)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        st.markdown("**⚙️ 操作**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📧 发送重置邮件", key="admin_send_reset", use_container_width=True):
                success, msg = admin_send_password_reset(selected_user["email"])
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
        
        with col2:
            if st.button("🔑 删除用户", key="admin_delete_user", use_container_width=True):
                success, msg = admin_delete_user_from_auth(selected_user["id"], selected_user["email"])
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        with col3:
            if st.button("🔄 刷新数据", key="admin_refresh_user", use_container_width=True):
                st.rerun()
    
    st.markdown("---")
    
    # ==================== 批量操作 ====================
    st.markdown("#### 🔄 批量操作")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("重置所有免费用户次数", key="admin_reset_all_free", use_container_width=True):
            count = 0
            for user in users_with_details:
                if user["subscription_tier"] == "free":
                    admin_reset_user_trials_racing(user["id"], FREE_TRIAL_LIMIT)
                    count += 1
            st.success(f"已重置 {count} 位免费用户的次数")
            st.rerun()
    
    with col2:
        if st.button("导出用户数据(CSV)", key="admin_export_csv", use_container_width=True):
            export_df = df_users[["email", "subscription_tier", "free_trials_remaining", 
                                   "subscription_expires_at", "created_at", "last_sign_in_at"]]
            csv = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="下载CSV", 
                data=csv, 
                file_name=f"users_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv", 
                key="admin_download_csv"
            )
    
    st.markdown("---")
    st.caption("💡 提示：删除用户将同时删除该用户的所有相关数据（设置、板块、缓存等）")
#----------------------------
#-------------------------------
def admin_sign_out():
    """管理员退出"""
    prev_user_id = st.session_state.get("admin_previous_user_id")
    prev_user_email = st.session_state.get("admin_previous_user_email")
    prev_access_token = st.session_state.get("admin_previous_access_token")
    prev_refresh_token = st.session_state.get("admin_previous_refresh_token")
    
    if prev_user_id and prev_user_email:
        st.session_state.authenticated = True
        st.session_state.user_id = prev_user_id
        st.session_state.user_email = prev_user_email
        st.session_state.access_token = prev_access_token
        st.session_state.refresh_token = prev_refresh_token
        st.session_state.token_expiry = time.time() + 3600
    else:
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.user_email = None
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.token_expiry = 0
    
    st.session_state.admin_mode = False
    st.session_state.admin_previous_user_id = None
    st.session_state.admin_previous_user_email = None
    st.session_state.admin_previous_access_token = None
    st.session_state.admin_previous_refresh_token = None
    st.rerun()
# ==================== 侧边栏 ====================
def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        # 获取当前语言
        lang = st.session_state.get("lang", "zh")
        st.markdown(f"## {t()['app_title']}")
        st.markdown("---")
        #-------------
        if st.session_state.authenticated and not st.session_state.admin_mode:
            user_email = st.session_state.user_email
            username = user_email.split('@')[0] if user_email else user_email
            user_id = st.session_state.user_id
            
            profile = get_user_profile(user_id)
            
            tier = profile.get("subscription_tier", "free")
            remaining = profile.get("free_trials_remaining", 0)
            
            tier_display = t()["tier_pro"] if tier == "pro" else t()["tier_free"]
            
            # 专业版显示无限，免费版显示剩余次数
            if tier == "pro":
                remaining_display = "∞"
            else:
                remaining_display = str(remaining)
            
            st.markdown(f"""
            <div class="sidebar-user-info">
                <strong>👤 {username}</strong><br>
                📋 {t()['subscription']}: {tier_display}<br>
                🎫 {t()['remaining']}: {remaining_display}
            </div>
            """, unsafe_allow_html=True)
            
            if tier == "free":
                if st.button("💎 " + t()["upgrade"], key="sidebar_upgrade", use_container_width=True):
                    st.session_state.show_paywall = True
                    st.rerun()
            
            st.markdown("---")
        
        with st.expander(t()["about_header"], expanded=True):
            st.markdown(t()["about_text"])
        
        with st.expander(t()["guide_header"], expanded=False):
            st.markdown(t()["guide_text"])
        #---------------
                # ==================== 评分系统介绍 ====================
        with st.expander("📊 评分系统" if lang == "zh" else "📊 Rating System", expanded=False):
            if lang == "zh":
                st.markdown("""
                **一级因子权重**
                
                | 一级因子 | 权重 | 说明 |
                |---------|------|------|
                | 基础往绩 | 0-100% | 历史表现评估实力与稳定性 |
                | 场次因素 | 0-100% | 本场条件适配度 |
                | 赔率因素 | 0-100% | 市场赔率与资金动向 |
                | 状态因素 | 0-100% | 即时状态综合评估 |
                
                **二级因子详解**
                
                | 一级因子 | 二级因子 | 权重 | 评分逻辑 |
                |---------|---------|------|---------|
                | 基础往绩 | 近3场胜率 | 20% | 近期状态最重要 |
                | | 近10场胜率 | 20% | 长期实力评估 |
                | | 近10场入Q率 | 15% | 稳定性指标 |
                | | 近10场入T率 | 15% | 整体水平反映 |
                | | 同程表现评分 | 15% | 路程适配度 |
                | | 名次趋势 | 15% | 进步/退步趋势 |
                | 场次因素 | 同场地胜率 | 25% | 场地专长适应性 |
                | | 同路程胜率 | 25% | 路程专长适应性 |
                | | 档位优势 | 15% | 起步位置优劣 |
                | | 负磅变化 | 10% | 重量影响评估 |
                | | 骑师配合 | 15% | 骑师胜率反映 |
                | | 练马师状态 | 10% | 马房状态评估 |
                | 赔率因素 | 独赢赔率 | 60% | 市场看好程度 |
                | | 赔率变动趋势 | 40% | 资金流向反映 |
                | 状态因素 | 马龄因子 | 30% | 4-6岁黄金期 |
                | | 体重变化 | 25% | 与上赛比较 |
                | | 事件报告 | 25% | 受阻/健康影响 |
                | | 冲刺能力 | 20% | 后劲走位分析 |
                
                **评分流程**：四维评分 → 加权综合 → Softmax转换 → 胜率概率
                """)
            else:
                st.markdown("""
                **Level 1 Weights**
                
                | Level 1 Factor | Weight | Description |
                |---------------|--------|-------------|
                | Basic Performance | 0-100% | Historical performance evaluation |
                | Race Factors | 0-100% | Race condition adaptability |
                | Odds Factors | 0-100% | Market odds & money flow |
                | Status Factors | 0-100% | Current condition assessment |
                
                **Level 2 Factors**
                
                | Level 1 | Level 2 | Weight | Scoring Logic |
                |---------|---------|--------|---------------|
                | Basic | Win Rate (L3) | 20% | Recent form is most important |
                | | Win Rate (L10) | 20% | Long-term ability assessment |
                | | Place Rate (L10) | 15% | Consistency indicator |
                | | Show Rate (L10) | 15% | Overall level reflection |
                | | Distance Rating | 15% | Distance adaptability |
                | | Ranking Trend | 15% | Progress/decline trend |
                | Race | Same Course Rate | 25% | Course adaptability |
                | | Same Distance Rate | 25% | Distance adaptability |
                | | Draw Advantage | 15% | Starting position |
                | | Weight Change | 10% | Weight impact assessment |
                | | Jockey | 15% | Jockey win rate |
                | | Trainer | 10% | Stable form assessment |
                | Odds | Win Odds | 60% | Market favorability |
                | | Odds Trend | 40% | Money flow reflection |
                | Status | Age Factor | 30% | 4-6yo golden period |
                | | Weight Change | 25% | Compare with last run |
                | | Incident | 25% | Interference/health impact |
                | | Burst Ability | 20% | Finishing position analysis |
                
                **Scoring Flow**: 4D Score → Weighted Combine → Softmax → Win Probability
                """)
        # ==================== 新增：彩池玩法 ====================
        with st.expander(t()["betting_pools"], expanded=False):
            if st.session_state.get("lang", "zh") == "zh":
                st.markdown("""
                **單場彩池**
                | 彩池 | 玩法 | 中獎條件 |
                |------|------|----------|
                | 獨贏 | 選1匹 | 跑第1名 |
                | 位置 | 選1匹 | 跑入前3名 |
                | 連贏 | 選2匹 | 前2名(不限順序) |
                | 位置Q | 選2匹 | 前3名(不限順序) |
                | 單T | 選3匹 | 前3名(不限順序) |
                | 三重彩 | 選3匹 | 前3名(順序固定) |
                | 四連環 | 選4匹 | 前4名(不限順序) |
                | 四重彩 | 選4匹 | 前4名(順序固定) |
                
                **多場彩池**
                | 彩池 | 玩法 | 中獎條件 |
                |------|------|----------|
                | 孖寶 | 指定2場 | 兩場都第1名 |
                | 三寶 | 指定3場 | 三場都第1名 |
                | 孖T | 指定2場 | 兩場前3名(不限順序) |
                | 三T | 指定3場 | 三場前3名(不限順序) |
                | 六環彩 | 指定6場 | 每場第1或第2名 |
                """)
            else:
                st.markdown("""
                **Single Race Pools**
                | Pool | How to Play | Winning Condition |
                |------|-------------|-------------------|
                | Win | Pick 1 horse | Finish 1st |
                | Place | Pick 1 horse | Finish Top 3 |
                | Quinella | Pick 2 horses | 1st & 2nd (any order) |
                | Quinella Place | Pick 2 horses | 1st, 2nd or 3rd (any order) |
                | Trio | Pick 3 horses | 1st, 2nd & 3rd (any order) |
                | Tierce | Pick 3 horses | 1st, 2nd & 3rd (exact order) |
                | First 4 | Pick 4 horses | 1st, 2nd, 3rd & 4th (any order) |
                | Quartet | Pick 4 horses | 1st, 2nd, 3rd & 4th (exact order) |
                
                **Multi-Race Pools**
                | Pool | How to Play | Winning Condition |
                |------|-------------|-------------------|
                | Double | 2 specified races | Win both races |
                | Treble | 3 specified races | Win all 3 races |
                | Double Trio | 2 specified races | Top 3 in both races (any order) |
                | Triple Trio | 3 specified races | Top 3 in all 3 races (any order) |
                | Six Up | 6 specified races | 1st or 2nd in each race |
                """)
        
        with st.expander(t()["contact_header"], expanded=False):
            st.markdown(t()["contact_email"])
        
        st.markdown("---")
        st.caption("v1.0 | TechLife")
        st.caption(t()["data_source_footer"])

def inject_auth_mobile_body_class():
    """未登录手机页标记，用于隐藏侧边栏而不影响已登录页面。"""
    st.markdown(
        """
<script>
(function () {
  document.body.classList.add("auth-mobile-login");
  document.body.classList.remove("auth-mobile-ready");
})();
</script>
""",
        unsafe_allow_html=True,
    )


def inject_sidebar_mobile_support():
    """手机端：默认展开侧边栏，并提供可靠的打开菜单按钮与提示。"""
    hint = t().get("sidebar_expand_hint", "点击打开")
    menu_label = t().get("sidebar_open_menu", "☰ 打开菜单")
    st.markdown(
        f"""
<style>
    #equi-mobile-sidebar-btn {{
        display: none;
        position: fixed;
        top: max(0.55rem, env(safe-area-inset-top));
        left: max(0.55rem, env(safe-area-inset-left));
        z-index: 999992;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.84rem;
        font-weight: 600;
        color: #31333f;
        background: rgba(255, 255, 255, 0.98);
        border: 1px solid #c9ced6;
        border-radius: 0.65rem;
        padding: 0.45rem 0.7rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
        cursor: pointer;
    }}
    #equi-sidebar-expand-hint {{
        display: none;
        position: fixed;
        z-index: 999991;
        font-size: 0.82rem;
        font-weight: 600;
        color: #31333f;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid #d5dae0;
        border-radius: 0.5rem;
        padding: 0.35rem 0.65rem;
        white-space: nowrap;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        line-height: 1.2;
        cursor: pointer;
    }}
    @media screen and (max-width: 768px) {{
        body:not(.auth-mobile-login) #equi-mobile-sidebar-btn.is-visible {{
            display: inline-flex;
        }}
        #equi-sidebar-expand-hint {{
            font-size: 0.78rem;
            padding: 0.3rem 0.55rem;
        }}
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{
            z-index: 999993 !important;
            pointer-events: auto !important;
        }}
    }}
</style>
<button type="button" id="equi-mobile-sidebar-btn" aria-label="{menu_label}">{menu_label}</button>
<span id="equi-sidebar-expand-hint" role="button" tabindex="0">{hint}</span>
<script>
(function () {{
    document.body.classList.remove("auth-mobile-login");
    document.body.classList.add("auth-mobile-ready");

    var hint = document.getElementById("equi-sidebar-expand-hint");
    var menuBtn = document.getElementById("equi-mobile-sidebar-btn");
    if (!hint || !menuBtn) return;

    function isMobile() {{
        return window.matchMedia("(max-width: 768px)").matches;
    }}

    function findExpandButton() {{
        return document.querySelector('[data-testid="stSidebarCollapsedControl"]')
            || document.querySelector('[data-testid="collapsedControl"]')
            || document.querySelector('[data-testid="stSidebarCollapseButton"]');
    }}

    function isVisible(el) {{
        if (!el) return false;
        var style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return false;
        var rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }}

    function isSidebarOpen() {{
        var sidebar = document.querySelector('[data-testid="stSidebar"]');
        if (!sidebar || !isVisible(sidebar)) return false;
        var rect = sidebar.getBoundingClientRect();
        return rect.width > 64;
    }}

    function openSidebar() {{
        if (isSidebarOpen()) return;
        var expandBtn = findExpandButton();
        if (expandBtn) {{
            expandBtn.click();
            return;
        }}
        var headerBtn = document.querySelector('[data-testid="stHeader"] button');
        if (headerBtn) headerBtn.click();
    }}

    function syncSidebarUi() {{
        if (!isMobile()) {{
            hint.style.display = "none";
            menuBtn.classList.remove("is-visible");
            return;
        }}
        var expandBtn = findExpandButton();
        var open = isSidebarOpen();
        menuBtn.classList.toggle("is-visible", !open);

        if (!open && isVisible(expandBtn)) {{
            var rect = expandBtn.getBoundingClientRect();
            hint.style.display = "block";
            hint.style.left = (rect.right + 8) + "px";
            hint.style.top = (rect.top + rect.height / 2 - hint.offsetHeight / 2) + "px";
        }} else {{
            hint.style.display = "none";
        }}
    }}

    function scheduleSync() {{
        if (window.__equiSidebarSyncScheduled) return;
        window.__equiSidebarSyncScheduled = true;
        window.requestAnimationFrame(function () {{
            window.__equiSidebarSyncScheduled = false;
            syncSidebarUi();
        }});
    }}

    if (!menuBtn.dataset.equiBound) {{
        menuBtn.dataset.equiBound = "1";
        menuBtn.addEventListener("click", function (event) {{
            event.preventDefault();
            event.stopPropagation();
            openSidebar();
            setTimeout(scheduleSync, 120);
        }});
    }}
    if (!hint.dataset.equiBound) {{
        hint.dataset.equiBound = "1";
        hint.addEventListener("click", function (event) {{
            event.preventDefault();
            event.stopPropagation();
            openSidebar();
            setTimeout(scheduleSync, 120);
        }});
    }}

    if (!window.__equiSidebarObserverReady) {{
        window.__equiSidebarObserverReady = true;
        new MutationObserver(scheduleSync).observe(document.body, {{
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["style", "class", "aria-expanded", "aria-hidden"],
        }});
        window.addEventListener("resize", scheduleSync);

        if (isMobile() && !sessionStorage.getItem("equi_mobile_sidebar_opened")) {{
            setTimeout(function () {{
                openSidebar();
                sessionStorage.setItem("equi_mobile_sidebar_opened", "1");
                scheduleSync();
            }}, 450);
        }}
    }}

    scheduleSync();
}})();
</script>
""",
        unsafe_allow_html=True,
    )

# ==================== 右上角按钮 ====================
def render_top_buttons():
    """渲染右上角按钮"""
    col1, col2, col3, col4, col5 = st.columns([8, 1.2, 1.2, 1.2, 1])
    
    with col2:
        if st.button("中文", key="zh_btn", use_container_width=True):
            if st.session_state.lang != "zh":
                st.session_state.lang = "zh"
                st.rerun()
    
    with col3:
        if st.button("English", key="en_btn", use_container_width=True):
            if st.session_state.lang != "en":
                st.session_state.lang = "en"
                st.rerun()
    
    with col4:
        if st.button("⚙️", key="gear_btn", help=t()["admin_login_help"], use_container_width=True):
            if is_admin_session_valid():
                activate_admin_mode(preserve_user=True)
            else:
                st.session_state.show_admin_login = True
                st.session_state.try_admin_local_restore = True
            st.rerun()
    
    with col5:
        if st.session_state.authenticated:
            if st.session_state.admin_mode:
                if st.button(t()["back_to_user"], key="back_to_user_btn", help=t()["exit_admin_mode"], use_container_width=True):
                    admin_sign_out()
                    st.rerun()
            else:
                if st.button("🚪", key="logout_btn", help=t()["logout_help"], use_container_width=True):
                    sign_out()
                    st.rerun()

# ==================== 占位页面（后续代码填充） ====================
# ============================================================
# 第3次代码：主页 + 全马评分榜
# 包含：数据概览、手动更新按钮、全马基础评分榜
# 版本：v1.0
# 说明：替换原有的 render_home() 函数
# ============================================================
# ==================== 评分缓存函数 ====================

def save_horse_scores_to_cache(df: pd.DataFrame) -> bool:
    """
    将评分结果保存到缓存表
    参数：
        df: 评分DataFrame（列名与显示一致）
    返回：
        是否保存成功
    """
    if df.empty:
        return False
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 清空旧缓存
        delete_url = f"{SUPABASE_URL}/rest/v1/horse_scores_cache"
        delete_response = requests.delete(delete_url, headers=headers)
        
        if delete_response.status_code not in [200, 204]:
            print(f"清空缓存失败: {delete_response.status_code}")
        
        # 准备数据
        records = []
        for _, row in df.iterrows():
            # 安全提取各字段
            horse_id = row.get("Horse_ID", "")
            name_zh = row.get("馬名(中)", row.get("Name (CN)", ""))
            name_en = row.get("馬名(英)", row.get("Name (EN)", ""))
            sex = row.get("性別", row.get("Sex", ""))
            age = str(row.get("年齡", row.get("Age", "")))
            avg_weight = str(row.get("平均體重", row.get("Avg Weight", "")))
            
            # 处理百分比字符串
            win_rate_raw = row.get("勝率", row.get("Win Rate", "0%"))
            if isinstance(win_rate_raw, str):
                win_rate = float(win_rate_raw.replace("%", ""))
            else:
                win_rate = float(win_rate_raw) if win_rate_raw else 0
            
            place_rate_raw = row.get("入Q率", row.get("Place Rate", "0%"))
            if isinstance(place_rate_raw, str):
                place_rate = float(place_rate_raw.replace("%", ""))
            else:
                place_rate = float(place_rate_raw) if place_rate_raw else 0
            
            show_rate_raw = row.get("入T率", row.get("Show Rate", "0%"))
            if isinstance(show_rate_raw, str):
                show_rate = float(show_rate_raw.replace("%", ""))
            else:
                show_rate = float(show_rate_raw) if show_rate_raw else 0
            
            basic_score = float(row.get("綜合評分", row.get("Overall Score", 0)))
            races_count = int(row.get("出賽場次", row.get("Races", 0)))
            
            record = {
                "horse_id": horse_id,
                "name_zh": name_zh,
                "name_en": name_en,
                "sex": sex,
                "age": age,
                "avg_weight": avg_weight,
                "win_rate": win_rate,
                "place_rate": place_rate,
                "show_rate": show_rate,
                "basic_score": basic_score,
                "races_count": races_count,
                "calculated_at": datetime.now().isoformat()
            }
            records.append(record)
        
        if not records:
            return False
        
        # 批量插入
        insert_url = f"{SUPABASE_URL}/rest/v1/horse_scores_cache"
        response = requests.post(insert_url, headers=headers, json=records)
        
        if response.status_code in [200, 201]:
            print(f"✅ 缓存保存成功: {len(records)} 条记录")
            return True
        else:
            print(f"❌ 缓存保存失败: {response.text}")
            return False
        
    except Exception as e:
        print(f"保存缓存异常: {e}")
        return False
# ==================== 辅助函数：获取所有马匹基础评分 ====================
@st.cache_data(ttl=600, show_spinner=False)
def _load_horse_scores_cache_df(limit: int, lang: str) -> pd.DataFrame:
    """只读 Supabase horse_scores_cache（不触发全量重算）。"""
    try:
        headers = get_supabase_headers(use_secret=True)
        cache_check_url = f"{SUPABASE_URL}/rest/v1/horse_scores_cache?select=horse_id&limit=1"
        cache_check = requests.get(cache_check_url, headers=headers, timeout=20)
        if cache_check.status_code != 200 or not cache_check.json():
            return pd.DataFrame()

        cache_url = f"{SUPABASE_URL}/rest/v1/horse_scores_cache?order=basic_score.desc&limit={limit}"
        response = requests.get(cache_url, headers=headers, timeout=30)
        if response.status_code != 200 or not response.json():
            return pd.DataFrame()

        cache_data = response.json()
        df = pd.DataFrame(cache_data)
        if lang == "zh":
            df_display = df.rename(columns={
                "horse_id": "Horse_ID",
                "name_zh": "馬名(中)",
                "name_en": "馬名(英)",
                "sex": "性別",
                "age": "年齡",
                "avg_weight": "平均體重",
                "win_rate": "勝率",
                "place_rate": "入Q率",
                "show_rate": "入T率",
                "basic_score": "綜合評分",
                "races_count": "出賽場次",
            })
            column_order = [
                "Horse_ID", "馬名(中)", "馬名(英)", "性別", "年齡", "平均體重",
                "勝率", "入Q率", "入T率", "綜合評分", "出賽場次",
            ]
        else:
            df_display = df.rename(columns={
                "horse_id": "Horse_ID",
                "name_zh": "Name (CN)",
                "name_en": "Name (EN)",
                "sex": "Sex",
                "age": "Age",
                "avg_weight": "Avg Weight",
                "win_rate": "Win Rate",
                "place_rate": "Place Rate",
                "show_rate": "Show Rate",
                "basic_score": "Overall Score",
                "races_count": "Races",
            })
            column_order = [
                "Horse_ID", "Name (EN)", "Sex", "Age", "Avg Weight",
                "Win Rate", "Place Rate", "Show Rate", "Overall Score", "Races",
            ]

        for col in ["勝率", "入Q率", "入T率", "Win Rate", "Place Rate", "Show Rate"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(
                    lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x
                )

        df_display = df_display[[c for c in column_order if c in df_display.columns]]
        if lang == "en" and "Sex" in df_display.columns:
            df_display["Sex"] = df_display["Sex"].apply(lambda x: format_sex(x, "en"))

        calc_time = cache_data[0].get("calculated_at", "")
        if calc_time:
            calc_time = calc_time[:16].replace("T", " ")
        df_display.attrs["cache_time"] = calc_time
        df_display.attrs["from_cache"] = True
        return df_display
    except Exception as exc:
        print(f"读取 horse_scores_cache 失败: {exc}")
        return pd.DataFrame()


def get_all_horses_base_score(limit: int = 500, recent_games: int = 10) -> pd.DataFrame:
    """
    获取所有马匹的基础评分（使用新评分引擎）
    包含：基础往绩 + 场次因素 + 赔率因素 + 状态因素
    支持缓存：优先从 horse_scores_cache 表读取
    """
    try:
        lang = st.session_state.get("lang", "zh")
        cached_df = _load_horse_scores_cache_df(limit, lang)
        if not cached_df.empty:
            cache_time = getattr(cached_df, "attrs", {}).get("cache_time", "")
            if cache_time:
                st.caption(
                    f"📊 共 {len(cached_df)} 匹馬 (緩存於 {cache_time})"
                    if lang == "zh"
                    else f"📊 Total {len(cached_df)} horses (cached at {cache_time})"
                )
            return cached_df

        headers = get_supabase_headers(use_secret=True)
        
        # ==================== 缓存不存在：执行完整计算（不调 DeepSeek） ====================
        # ==================== 1. 获取马匹基本信息 ====================
        horses_url = f"{SUPABASE_URL}/rest/v1/horses_v2?select=*"
        horses_response = requests.get(horses_url, headers=headers)
        
        horse_info = {}
        if horses_response.status_code == 200:
            for h in horses_response.json():
                horse_id = h.get('horse_id')
                if horse_id:
                    horse_info[horse_id] = {
                        'name_zh': h.get('name_zh', ''),
                        'name_en': h.get('name_en', ''),
                        'sex': h.get('sex', '-'),
                        'birth_year': h.get('birth_year')
                    }
        else:
            error_msg = "获取马匹信息失败" if lang == "zh" else "Failed to get horse info"
            st.error(f"{error_msg}: {horses_response.status_code}")
            return pd.DataFrame()
        
        # ==================== 2. 获取所有成绩记录 ====================
        perf_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=horse_id,position,body_weight,race_date,venue,distance,draw,actual_weight,jockey,trainer,odds,incident,running_position&limit=50000"
        perf_response = requests.get(perf_url, headers=headers)
        
        if perf_response.status_code != 200:
            error_msg = "获取成绩数据失败" if lang == "zh" else "Failed to get performance data"
            st.error(f"{error_msg}: {perf_response.status_code}")
            return pd.DataFrame()
        
        data = perf_response.json()
        
        if not data:
            info_msg = "暂无成绩数据" if lang == "zh" else "No performance data available"
            st.info(info_msg)
            return pd.DataFrame()
        
        # ==================== 3. 按 horse_id 分组 ====================
        from collections import defaultdict
        horse_records = defaultdict(list)
        
        for p in data:
            horse_id = p.get("horse_id")
            if not horse_id:
                continue
            horse_records[horse_id].append({
                "position": p.get("position"),
                "body_weight": p.get("body_weight"),
                "race_date": p.get("race_date"),
                "venue": p.get("venue"),
                "distance": p.get("distance"),
                "draw": p.get("draw"),
                "actual_weight": p.get("actual_weight"),
                "jockey": p.get("jockey"),
                "trainer": p.get("trainer"),
                "odds": p.get("odds"),
                "incident": p.get("incident", ""),
                "running_position": p.get("running_position", "")
            })

        # 评分榜状态分只用每匹马「最近一场」的 incident，勿扫全库 5 万条往绩
        latest_incidents: List[str] = []
        for records in horse_records.values():
            records.sort(key=lambda x: x.get("race_date", ""), reverse=True)
            scope_records = records if recent_games == 0 else records[:recent_games]
            if scope_records:
                latest_incidents.append(scope_records[0].get("incident", ""))
        incident_llm_map = _build_incident_llm_map(latest_incidents)
        
        # ==================== 4. 加载评分配置 ====================
        from scoring_engine import get_scoring_config
        config = get_scoring_config()
        level1 = config.get('level1', {})
        basic_w = config.get('basic', {})
        race_w = config.get('race', {})
        odds_w = config.get('odds', {})
        status_w = config.get('status', {})
        #------------
        # ==================== 5. 计算每匹马的评分 ====================
        from scoring_engine import (
            calculate_basic_score,
            calculate_race_score,
            calculate_odds_score,
            calculate_status_score,
            calculate_overall_score,
            get_horse_weight_comfort_range_from_cache
        )
        
        current_year = datetime.now().year
        results = []
        
        # ✅ 创建进度条（替换 st.caption）
        total_horses = len(horse_records)
        progress_bar = None
        if total_horses > 0:
            progress_text = f"正在计算 {total_horses} 匹马的评分..." if lang == "zh" else f"Calculating scores for {total_horses} horses..."
            progress_bar = st.progress(0, text=progress_text)
        
        for idx, (horse_id, records) in enumerate(horse_records.items()):
            # ✅ 更新进度条（每5匹更新一次，减少刷新开销）
            if progress_bar and (idx % 5 == 0 or idx == total_horses - 1):
                progress_pct = min((idx + 1) / total_horses, 1.0)
                progress_bar.progress(progress_pct, text=f"{progress_text} ({idx+1}/{total_horses})")
            
            # 按日期排序（最新的在前）
            records.sort(key=lambda x: x.get("race_date", ""), reverse=True)
            
            # 取最近 N 场
            if recent_games == 0:
                selected = records
            else:
                selected = records[:recent_games]
            
            total = len(selected)
            
            # 获取马匹信息
            info = horse_info.get(horse_id, {})
            name_zh = info.get('name_zh', horse_id)
            name_en = info.get('name_en', '')
            sex = info.get('sex', '-')
            if lang == "en":
                sex = format_sex(sex, "en")
            birth_year = info.get('birth_year')
            
            # 计算年龄
            age = '-'
            if birth_year and isinstance(birth_year, int):
                age_val = current_year - birth_year
                age = age_val if 2 <= age_val <= 12 else '-'
            
            # ========== 新马处理（出赛不足3场） ==========
            if total < 3:
                base_score = 50.0
                if age != '-' and isinstance(age, int):
                    if 4 <= age <= 5:
                        base_score += 12      # 黄金年龄
                    elif age == 3 or age == 6:
                        base_score += 5       # 接近黄金期
                    elif age >= 7:
                        base_score -= 10      # 老龄马
                    elif age == 2:
                        base_score -= 5       # 太年轻
                
                # 限制范围
                base_score = max(25, min(80, base_score))
                
                # 新马备注
                note_text = f"仅出赛{total}场，评分基于年龄评估" if lang == "zh" else f"Only {total} races, score based on age assessment"
                
                results.append({
                    "horse_id": horse_id,
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "sex": sex,
                    "age": age,
                    "avg_weight": '-',
                    "win_rate": 0.0,
                    "place_rate": 0.0,
                    "show_rate": 0.0,
                    "basic_score": round(base_score, 1),
                    "races_count": total,
                    "note": note_text
                })
                continue
            
            # ========== 出赛3场以上：计算完整评分 ==========
            # 提取往绩数据
            past_performances = []
            for r in selected:
                past_performances.append({
                    "position": r.get("position"),
                    "body_weight": r.get("body_weight"),
                    "race_date": r.get("race_date"),
                    "venue": r.get("venue"),
                    "distance": r.get("distance"),
                    "draw": r.get("draw"),
                    "actual_weight": r.get("actual_weight"),
                    "jockey": r.get("jockey"),
                    "trainer": r.get("trainer"),
                    "odds": r.get("odds"),
                    "incident": r.get("incident", ""),
                    "running_position": r.get("running_position", "")
                })
            
            # 获取最近一场的数据（用于场次和状态评分）
            latest = selected[0]
            
            # 计算负磅舒适区
            weight_comfort_range = get_horse_weight_comfort_range_from_cache(horse_id, past_performances)
            
            # 计算各维度评分
            basic_score = calculate_basic_score(
                past_performances,
                latest.get('distance', 1200),
                basic_w
            )
            
            race_score = calculate_race_score(
                horse_id,
                latest.get('venue', 'ST'),
                latest.get('distance', 1200),
                latest.get('draw'),
                latest.get('actual_weight'),
                latest.get('jockey'),
                latest.get('trainer'),
                weight_comfort_range,
                past_performances,
                race_w
            )
            
            odds_win = latest.get('odds', 10.0)
            if odds_win is None or odds_win == '':
                odds_win = 10.0
            try:
                odds_win = float(odds_win)
            except (ValueError, TypeError):
                odds_win = 10.0
            
            odds_score = calculate_odds_score(odds_win, 50.0, odds_w)

            latest_incident = latest.get('incident', '')
            llm_overlay = incident_llm_map.get(latest_incident, 0.0) if latest_incident else 0.0
            
            status_score = calculate_status_score(
                birth_year,
                latest.get('body_weight'),
                [r.get('body_weight') for r in past_performances if r.get('body_weight')],
                latest_incident,
                latest.get('running_position', ''),
                latest.get('position'),
                status_w,
                llm_incident_overlay=llm_overlay,
            )
            
            overall_score = calculate_overall_score(
                basic_score,
                race_score,
                odds_score,
                status_score,
                level1
            )
            
            # 计算传统指标（用于显示）
            wins = sum(1 for r in selected if r.get('position') == 1)
            places = sum(1 for r in selected if r.get('position') in [1, 2])
            shows = sum(1 for r in selected if r.get('position') in [1, 2, 3])
            
            win_rate = wins / total * 100
            place_rate = places / total * 100
            show_rate = shows / total * 100
            
            weights = [r.get("body_weight") for r in selected if r.get("body_weight")]
            avg_weight = sum(weights) / len(weights) if weights else 0
            
            results.append({
                "horse_id": horse_id,
                "name_zh": name_zh,
                "name_en": name_en,
                "sex": sex,
                "age": age,
                "avg_weight": round(avg_weight, 0) if avg_weight > 0 else '-',
                "win_rate": round(win_rate, 1),
                "place_rate": round(place_rate, 1),
                "show_rate": round(show_rate, 1),
                "basic_score": overall_score,
                "races_count": total
            })
        
        # ✅ 进度条完成
        if progress_bar:
            progress_bar.progress(1.0, text="✅ 计算完成!" if lang == "zh" else "✅ Complete!")
        
        # 按评分排序
        results.sort(key=lambda x: x["basic_score"], reverse=True)
        
        # 创建 DataFrame
        df = pd.DataFrame(results[:limit])
        
        if df.empty:
            info_msg = "暂无马匹数据" if lang == "zh" else "No horse data available"
            st.info(info_msg)
            return df
        
        # ==================== 保存到缓存 ====================
        try:
            save_horse_scores_to_cache(df)
        except Exception as e:
            print(f"缓存保存失败: {e}")
        
        # 重命名列（双语）
        if lang == "zh":
            df_display = df.rename(columns={
                "horse_id": "Horse_ID",
                "name_zh": "馬名(中)",
                "name_en": "馬名(英)",
                "sex": "性別",
                "age": "年齡",
                "avg_weight": "平均體重",
                "win_rate": "勝率",
                "place_rate": "入Q率",
                "show_rate": "入T率",
                "basic_score": "綜合評分",
                "races_count": "出賽場次"
            })
        else:
            df_display = df.rename(columns={
                "horse_id": "Horse_ID",
                "name_zh": "Name (CN)",
                "name_en": "Name (EN)",
                "sex": "Sex",
                "age": "Age",
                "avg_weight": "Avg Weight",
                "win_rate": "Win Rate",
                "place_rate": "Place Rate",
                "show_rate": "Show Rate",
                "basic_score": "Overall Score",
                "races_count": "Races"
            })
        
        # 格式化百分比
        pct_cols = (
            ["勝率", "入Q率", "入T率"]
            if lang == "zh"
            else ["Win Rate", "Place Rate", "Show Rate"]
        )
        for col in pct_cols:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(
                    lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x
                )
        
        # 调整列顺序
        if lang == "zh":
            column_order = ["Horse_ID", "馬名(中)", "馬名(英)", "性別", "年齡", "平均體重", "勝率", "入Q率", "入T率", "綜合評分", "出賽場次"]
        else:
            column_order = ["Horse_ID", "Name (EN)", "Sex", "Age", "Avg Weight", "Win Rate", "Place Rate", "Show Rate", "Overall Score", "Races"]
        
        df_display = df_display[[c for c in column_order if c in df_display.columns]]
        
        if lang == "en" and "Sex" in df_display.columns:
            df_display["Sex"] = df_display["Sex"].apply(lambda x: format_sex(x, "en"))
        
        return df_display
        
    except Exception as e:
        error_msg = f"获取马匹评分失败: {e}" if lang == "zh" else f"Failed to get horse scores: {e}"
        st.error(error_msg)
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
#------------
def render_horse_rating_table(df: pd.DataFrame):
    """渲染马匹评分表格（列宽最小化）"""
    lang = get_lang()
    if df.empty:
        st.info(tx("暫無馬匹數據，請點擊「更新數據」同步馬匹資料", "No horse data. Click Update Data to sync."))
        return

    if lang == "en":
        column_config = {
            "Horse_ID": st.column_config.TextColumn("ID", width="90px"),
            "Name (EN)": st.column_config.TextColumn("Name", width="140px"),
            "Sex": st.column_config.TextColumn("Sex", width="40px"),
            "Age": st.column_config.TextColumn("Age", width="40px"),
            "Avg Weight": st.column_config.TextColumn("Weight", width="60px"),
            "Win Rate": st.column_config.TextColumn("Win%", width="55px"),
            "Place Rate": st.column_config.TextColumn("Place%", width="55px"),
            "Show Rate": st.column_config.TextColumn("Show%", width="55px"),
            "Overall Score": st.column_config.NumberColumn("Score", width="60px", format="%.0f"),
            "Races": st.column_config.TextColumn("Races", width="50px"),
        }
    else:
        column_config = {
            "Horse_ID": st.column_config.TextColumn("ID", width="90px"),
            "馬名(中)": st.column_config.TextColumn("中文名", width="100px"),
            "馬名(英)": st.column_config.TextColumn("英文名", width="120px"),
            "性別": st.column_config.TextColumn("性別", width="40px"),
            "年齡": st.column_config.TextColumn("年齡", width="40px"),
            "平均體重": st.column_config.TextColumn("體重", width="60px"),
            "勝率": st.column_config.TextColumn("勝率", width="55px"),
            "入Q率": st.column_config.TextColumn("入Q率", width="55px"),
            "入T率": st.column_config.TextColumn("入T率", width="55px"),
            "綜合評分": st.column_config.NumberColumn("評分", width="60px", format="%.0f"),
            "出賽場次": st.column_config.TextColumn("場次", width="50px"),
        }

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )
    
    st.caption(tx(f"📊 共 {len(df)} 匹馬", f"📊 Total {len(df)} horses"))


def _supabase_exact_count(table: str, select: str = "horse_id") -> int:
    """使用 PostgREST count=exact 获取行数，避免拉取全表。"""
    try:
        headers = get_supabase_headers(use_secret=True)
        headers["Prefer"] = "count=exact"
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
        response = requests.get(url, headers=headers, params={"limit": 1})
        if response.status_code not in (200, 206):
            return 0
        content_range = response.headers.get("Content-Range", "")
        if "/" in content_range:
            total = content_range.split("/")[-1]
            if total.isdigit():
                return int(total)
        return len(response.json())
    except Exception as e:
        print(f"统计 {table} 失败: {e}")
        return 0


@st.cache_data(ttl=600, show_spinner=False)
def get_dashboard_stats() -> Dict:
    """缓存首页统计数据，避免每次交互重复查询 Supabase。"""
    stats = {
        "horse_count": 0,
        "race_count": 0,
        "perf_count": 0,
        "jockey_count": 0,
        "trainer_count": 0,
        "oldest_date": "N/A",
        "latest_date": "N/A",
    }
    try:
        headers = get_supabase_headers(use_secret=True)
        stats["horse_count"] = _supabase_exact_count("horses_v2", "horse_id")
        stats["perf_count"] = _supabase_exact_count("past_performances_v2", "horse_id")

        perf_races_url = (
            f"{SUPABASE_URL}/rest/v1/past_performances_v2"
            f"?select=race_date,venue,race_no,jockey,trainer&limit=50000"
        )
        perf_races_response = requests.get(perf_races_url, headers=headers, timeout=30)
        if perf_races_response.status_code == 200:
            unique_races = {
                (p.get("race_date"), p.get("venue"), p.get("race_no"))
                for p in perf_races_response.json()
            }
            stats["race_count"] = len(unique_races)

            jockeys = set()
            trainers = set()
            for p in perf_races_response.json():
                jockey_name = p.get("jockey")
                if jockey_name and str(jockey_name).strip():
                    jockeys.add(str(jockey_name).strip())
                trainer_name = p.get("trainer")
                if trainer_name and str(trainer_name).strip():
                    trainers.add(str(trainer_name).strip())
            stats["jockey_count"] = len(jockeys)
            stats["trainer_count"] = len(trainers)

        perf_url_latest = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=race_date&order=race_date.desc&limit=1"
        perf_response_latest = requests.get(perf_url_latest, headers=headers, timeout=15)
        if perf_response_latest.status_code == 200 and perf_response_latest.json():
            stats["latest_date"] = perf_response_latest.json()[0]["race_date"]

        perf_url_oldest = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=race_date&order=race_date.asc&limit=1"
        perf_response_oldest = requests.get(perf_url_oldest, headers=headers, timeout=15)
        if perf_response_oldest.status_code == 200 and perf_response_oldest.json():
            stats["oldest_date"] = perf_response_oldest.json()[0]["race_date"]
    except Exception as e:
        print(f"获取首页统计失败: {e}")
    return stats


# ==================== 主页函数（替换原有的render_home） ====================
def render_home():
    """主页：按模块懒加载，避免每次点击重跑全部功能"""
    
    # 直接获取语言
    lang = st.session_state.get("lang", "zh")
    texts = TEXTS[lang] if lang in TEXTS else TEXTS["zh"]
    
    # ==================== 页面标题 ====================
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1>🐎 {texts['app_title']}</h1>
        <p style="color: #666; font-size: 1.1rem;">{texts.get('home_subtitle', '基於AI技術，智能預測馬匹勝率，優化投注策略')}</p>
    </div>
    """, unsafe_allow_html=True)

    section_labels = (
        [t()["nav_data_ratings"], t()["nav_smart_betting"], t()["nav_backtest"]]
    )
    if "home_section_nav" not in st.session_state:
        st.session_state.home_section_nav = t()["nav_smart_betting"]
    section = st.radio(
        t()["nav_label"],
        section_labels,
        horizontal=True,
        key="home_section_nav",
        label_visibility="collapsed",
    )
    st.markdown("---")

    show_data_and_ratings = section == section_labels[0]
    show_smart_betting = section == section_labels[1]
    show_backtest = section == section_labels[2]
   
    # ==================== Tab1：数据概览 + 数据更新 + 全马评分 ====================
    if show_data_and_ratings:
        st.markdown(f"## {texts.get('data_overview', '📊 數據概覽')}")
        stats = get_dashboard_stats()
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric(f"🐎 {texts['horse_count']}", stats["horse_count"])
        with col2:
            st.metric(f"🏆 {texts['race_count']}", stats["race_count"])
        with col3:
            st.metric(f"📊 {texts['record_count']}", stats["perf_count"])
        with col4:
            st.metric(f"🤠 {texts['jockey_count']}", stats["jockey_count"])
        with col5:
            st.metric(f"🏋️ {texts['trainer_count']}", stats["trainer_count"])

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.metric(
                texts.get("date_range", "📅 數據日期範圍"),
                f"{stats['oldest_date']} ~ {stats['latest_date']}",
                help="基于历史成绩数据的日期范围",
            )
        st.markdown("---")

        st.markdown(f"### {texts.get('data_update', '🔄 數據更新')}")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            update_btn = st.button(
                f"🔄 {texts.get('update_all_data', '更新所有数据')}",
                type="primary",
                use_container_width=True,
            )

        if update_btn:
            with st.spinner(texts.get('checking_update', '正在检查并更新数据...')):
                result = sync_all_data()
                new_races = result.get('new_races', 0)
                new_records = result.get('new_records', 0)

                if result.get("success") and (new_races > 0 or new_records > 0):
                    try:
                        with st.spinner("正在更新评分缓存..."):
                            headers = get_supabase_headers(use_secret=True)
                            delete_url = f"{SUPABASE_URL}/rest/v1/horse_scores_cache"
                            requests.delete(delete_url, headers=headers)

                            df = get_all_horses_base_score(limit=500, recent_games=10)
                            if not df.empty:
                                save_horse_scores_to_cache(df)

                            st.success(
                                texts.get(
                                    'update_complete',
                                    '✅ 更新完成！新增 {new_races} 场赛事，{new_records} 条成绩记录，評分緩存已刷新',
                                ).format(new_races=new_races, new_records=new_records)
                            )
                            st.cache_data.clear()
                            _load_horse_scores_cache_df.clear()
                            st.rerun()
                    except Exception as e:
                        st.warning(f"数据同步成功，但缓存刷新失败: {e}")
                        st.rerun()
                elif result.get("success"):
                    st.info("✅ 数据已是最新，无需更新评分缓存")
                else:
                    st.error(f"{texts.get('update_failed', '更新失败')}: {result.get('error', '未知错误')}")
        st.markdown("---")

        st.markdown(f"### 🐎 {texts['horse_rating_title']}")
        st.caption(texts["horse_rating_desc"])

        col1, col2 = st.columns([1, 4])
        with col1:
            recent_games = st.selectbox(
                texts["calculate_games"],
                options=[3, 5, 8, 10, 12, 15, 20, 0],
                format_func=lambda x: texts["all_games"] if x == 0 else texts["recent_n_games_format"].format(n=x),
                index=3,
                key="recent_games",
            )
        with col2:
            rating_limit = st.selectbox(
                texts["display_limit"],
                options=[50, 100, 200, 300, 500],
                index=1,
                key="rating_limit",
            )

        scope = texts["all_games"] if recent_games == 0 else texts["recent_n_games_format"].format(n=recent_games)
        lang = st.session_state.get("lang", "zh")
        cached_rating_df = _load_horse_scores_cache_df(rating_limit, lang)
        if not cached_rating_df.empty:
            cache_time = getattr(cached_rating_df, "attrs", {}).get("cache_time", "")
            if cache_time:
                st.caption(
                    f"📊 共 {len(cached_rating_df)} 匹馬 (緩存於 {cache_time})"
                    if lang == "zh"
                    else f"📊 Total {len(cached_rating_df)} horses (cached at {cache_time})"
                )
            render_horse_rating_table(cached_rating_df)
        else:
            with st.spinner(texts["rating_calculating"].format(scope=scope)):
                rating_df = get_all_horses_base_score(limit=rating_limit, recent_games=recent_games)
                render_horse_rating_table(rating_df)
        st.markdown("---")
    
    # ==================== 模块3：智能投注 ====================
    if show_smart_betting:
        render_smart_betting(show_title=True)
        st.markdown("---")
    
    # ==================== 模块4：回测 ====================
    if show_backtest:
        render_backtest_page(show_title=False)
        st.markdown("---")

    st.caption(texts.get('data_source', '📅 數據來源：香港賽馬會 | 更新頻率：賽日自動更新'))


# ==================== 第3次代码结束 ====================
# ============================================================
# 第4次代码：智能投注 + 全天优化
# 包含：单场分析、全天投注分配、过关组合、Bankroll管理
# 版本：v1.0
# 说明：替换原有的 render_smart_betting() 函数
# ============================================================

# ==================== 辅助函数：获取赛日所有赛事 ====================
# ==================== 缓存版本的数据获取函数 ====================

def _race_schedule_key(race: Dict) -> str:
    return f"{race.get('race_date')}_{race.get('venue')}_{race.get('race_no')}"


def _race_has_post_time(race: Dict) -> bool:
    return bool(
        _format_post_time(
            race.get("post_time")
            or race.get("postTime")
            or race.get("scheduledStart")
            or race.get("startTime")
            or race.get("race_time")
        )
    )


def _race_has_schedule_metadata(race: Dict) -> bool:
    try:
        distance = int(race.get("distance") or race.get("distanceMeters") or 0)
    except (TypeError, ValueError):
        distance = 0
    surface = (race.get("surface") or race.get("race_track") or "").strip()
    if not surface and isinstance(race.get("raceTrack"), dict):
        rt = race["raceTrack"]
        surface = (rt.get("description_ch") or rt.get("description_en") or "").strip()
    going = (race.get("going") or "").strip()
    return distance > 0 and bool(surface) and bool(going)


def _merge_api_schedule_fields(metadata_races: List[Dict], base_races: List[Dict]) -> List[Dict]:
    """以 base_races 为完整场次列表，用 metadata_races（DB 或 detailed API）补全字段。"""
    if not base_races:
        return metadata_races

    meta_map = {_race_schedule_key(r): r for r in metadata_races}
    merged: List[Dict] = []
    for base_race in base_races:
        if base_race.get("race_no", 0) <= 0:
            continue
        item = dict(base_race)
        meta_row = meta_map.get(_race_schedule_key(item))
        if not meta_row:
            merged.append(item)
            continue

        if not _race_has_post_time(item):
            item["post_time"] = (
                meta_row.get("post_time")
                or meta_row.get("postTime")
                or meta_row.get("scheduledStart")
                or meta_row.get("startTime")
                or item.get("post_time")
                or item.get("postTime")
                or ""
            )
        for field in ("surface", "going", "distance", "race_class", "raceTrack", "raceCourse", "race_course_code"):
            if (not item.get(field)) and meta_row.get(field):
                item[field] = meta_row[field]
        merged.append(item)
    return merged


@st.cache_data(ttl=600, show_spinner=False)
def get_cached_upcoming_races() -> List[Dict]:
    """API 提供完整场次；detailed API / Supabase 补全距离、跑道、场地等 metadata。"""
    api_races = get_upcoming_races_from_api(detailed=False)
    if not api_races:
        api_races = get_upcoming_races_from_api(detailed=True)
    elif any(
        r.get("race_no", 0) > 0 and not _race_has_schedule_metadata(r)
        for r in api_races
    ):
        detailed_races = get_upcoming_races_from_api(detailed=True)
        if detailed_races:
            api_races = _merge_api_schedule_fields(detailed_races, api_races)

    db_races = get_upcoming_races_from_db()
    if api_races:
        schedule = _merge_api_schedule_fields(db_races, api_races) if db_races else api_races
        return _enrich_upcoming_races_from_db(schedule)

    if db_races:
        return _enrich_upcoming_races_from_db(db_races)
    return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_historical_race_summaries() -> List[Dict]:
    """缓存历史赛日列表，避免智能投注页每次交互拉取 5 万条记录。"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=race_date,venue,race_no,distance&order=race_date.desc&limit=50000"
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return []

        unique_races = {}
        for p in response.json():
            key = f"{p.get('race_date')}_{p.get('venue')}_{p.get('race_no')}"
            if key not in unique_races:
                unique_races[key] = {
                    "race_date": p.get("race_date"),
                    "venue": p.get("venue", "ST"),
                    "race_no": p.get("race_no", 0),
                    "distance": p.get("distance", 1200),
                }

        historical_races = sorted(
            unique_races.values(),
            key=lambda x: x.get("race_date", ""),
            reverse=True,
        )
        return historical_races[:60]
    except Exception as e:
        print(f"获取历史赛事缓存失败: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_race_runners(race_date: str, venue: str, race_no: int) -> List[Dict]:
    """缓存出赛马匹数据"""
    runners = get_race_runners_with_details(race_date, venue, race_no)
    return _enrich_runner_horse_names([dict(r) for r in runners]) if runners else []
#-----------
def get_upcoming_races_from_api(detailed: bool = True) -> List[Dict]:
    """
    从 Node.js API 获取未来赛程（直接调用 getActiveMeetings）
    这是获取赛程的主要数据源
    """
    try:
        API_BASE_URL = st.secrets.get("HKJC_API_URL", "")
        if not API_BASE_URL:
            print("⚠️ API地址未配置")
            return []

        detail_flag = "1" if detailed else "0"
        url = f"{API_BASE_URL.rstrip('/')}/meetings?detailed={detail_flag}"
        timeout = 300 if detailed else 45
        response = requests.get(url, timeout=timeout)
        
        if response.status_code != 200:
            print(f"❌ API返回错误: {response.status_code}")
            return []
        
        data = response.json()
        
        if not data.get("success"):
            print(f"❌ API返回失败: {data.get('error')}")
            return []
        
        meetings = data.get("data", [])
        
        print(f"📊 API返回 {len(meetings)} 个赛马日")
        
        # 打印每个赛马日的详细信息
        for meeting in meetings:
            print(f"  - {meeting.get('date')} {meeting.get('venueCode')}: {len(meeting.get('races', []))} 场比赛")
        
        upcoming_races = []
        today = datetime.now().date()
        future_limit = today + timedelta(days=14)
        
        for meeting in meetings:
            meeting_date_str = meeting.get("date", "")
            if not meeting_date_str:
                continue
            
            # 解析日期
            try:
                meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
            except ValueError:
                print(f"⚠️ 日期格式错误: {meeting_date_str}")
                continue
            
            # 只保留未来14天内的赛事
            if meeting_date < today or meeting_date > future_limit:
                print(f"⏭️ 跳过 {meeting_date_str} (不在未来14天内)")
                continue
            
            venue_code = meeting.get("venueCode", "ST")
            venue_name = meeting.get("venue", "")
            races_list = meeting.get("races", [])
            
            print(f"✅ 处理 {meeting_date_str} {venue_code}: {len(races_list)} 场比赛")
            
            if races_list and len(races_list) > 0:
                # 有详细场次信息
                for race in races_list:
                    race_no = race.get("no", 0)
                    distance = race.get("distance") or 0
                    race_class = (
                        race.get("race_class")
                        or race.get("className")
                        or race.get("raceClass_en")
                        or race.get("raceClass")
                        or ""
                    )
                    race_track_obj = race.get("raceTrack") or {}
                    race_course_obj = race.get("raceCourse") or {}
                    surface = (
                        race.get("surface")
                        or race_track_obj.get("description_ch")
                        or race_track_obj.get("description_en")
                        or race.get("race_track")
                        or ""
                    )

                    upcoming_races.append({
                        "race_date": meeting_date_str,
                        "venue": venue_code,
                        "venue_name": venue_name,
                        "race_no": race_no,
                        "distance": distance,
                        "race_class": race_class,
                        "post_time": race.get("postTime") or race.get("post_time") or "",
                        "surface": surface,
                        "going": race.get("going") or "",
                        "race_track": surface,
                        "race_course_code": race_course_obj.get("displayCode") or race.get("race_course_code") or "",
                        "raceTrack": race_track_obj,
                        "raceCourse": race_course_obj,
                        "race_id": f"{meeting_date_str}_{venue_code}_{race_no}",
                    })
                    print(
                        f"    - 添加第{race_no}场: {distance}米 "
                        f"{race.get('postTime', '')} {surface} {race.get('going', '')}"
                    )
            else:
                # 没有详细场次，添加占位记录
                print(f"    - 无详细场次，添加占位记录")
                upcoming_races.append({
                    "race_date": meeting_date_str,
                    "venue": venue_code,
                    "venue_name": venue_name,
                    "race_no": 0,
                    "distance": 0,
                    "race_class": "TBC",
                    "race_id": f"{meeting_date_str}_{venue_code}_0"
                })
        
        print(f"📊 最终返回 {len(upcoming_races)} 场赛事")
        
        # 按日期和场次排序
        upcoming_races.sort(key=lambda x: (x.get('race_date', ''), x.get('race_no', 0)))
        
        # 打印最终结果
        for race in upcoming_races:
            print(f"  {race['race_date']} {race['venue']} 第{race['race_no']}场")
        
        return upcoming_races
        
    except Exception as e:
        print(f"❌ 获取未来赛事失败: {e}")
        return []
#-----------
def _fetch_races_metadata_map(min_date: str, max_date: str) -> Dict[str, Dict]:
    """Fetch surface/going metadata from races table for enrichment."""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = (
            f"{SUPABASE_URL}/rest/v1/races"
            f"?race_date=gte.{min_date}&race_date=lte.{max_date}"
            f"&select=race_date,venue,race_no,surface,going,distance,race_class"
        )
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return {}
        meta: Dict[str, Dict] = {}
        for row in response.json():
            key = f"{row.get('race_date')}_{row.get('venue')}_{row.get('race_no')}"
            meta[key] = row
        return meta
    except Exception as exc:
        print(f"_fetch_races_metadata_map failed: {exc}")
        return {}


def _enrich_upcoming_races_from_db(races: List[Dict]) -> List[Dict]:
    """Merge surface/going from Supabase races table (synced by Node.js API)."""
    if not races:
        return races
    dates = [r.get("race_date") for r in races if r.get("race_date")]
    if not dates:
        return races
    meta = _fetch_races_metadata_map(min(dates), max(dates))
    if not meta:
        return races

    enriched: List[Dict] = []
    for race in races:
        merged = dict(race)
        key = f"{merged.get('race_date')}_{merged.get('venue')}_{merged.get('race_no')}"
        db_row = meta.get(key)
        if db_row:
            if db_row.get("surface"):
                merged["surface"] = db_row["surface"]
            if db_row.get("going"):
                merged["going"] = db_row["going"]
            if db_row.get("distance") and not merged.get("distance"):
                merged["distance"] = db_row["distance"]
            if db_row.get("race_class") and not merged.get("race_class"):
                merged["race_class"] = db_row["race_class"]
        enriched.append(merged)
    return enriched
#----------
def get_upcoming_races_from_db() -> List[Dict]:
    """从本地数据库获取未来赛程（备用数据源）"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        next_two_weeks = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/races?race_date=gte.{today}&race_date=lte.{next_two_weeks}&order=race_date.asc,race_no.asc"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"从数据库获取赛事失败: {e}")
        return []
#-----------
def sync_races_to_db(races: List[Dict]) -> bool:
    """
    将 API 获取的赛程同步到本地 races 表作为缓存
    """
    if not races:
        return False
    
    try:
        headers = get_supabase_headers(use_secret=True)
        synced_count = 0
        
        for race in races:
            # 检查是否已存在
            check_url = f"{SUPABASE_URL}/rest/v1/races?race_date=eq.{race['race_date']}&venue=eq.{race['venue']}&race_no=eq.{race['race_no']}"
            check_response = requests.get(check_url, headers=headers)
            
            if check_response.status_code == 200 and check_response.json():
                # 已存在，更新
                update_url = f"{SUPABASE_URL}/rest/v1/races?race_date=eq.{race['race_date']}&venue=eq.{race['venue']}&race_no=eq.{race['race_no']}"
                update_data = {
                    "distance": race.get('distance', 0),
                    "race_class": race.get('race_class', ''),
                    "updated_at": datetime.now().isoformat()
                }
                surface = race.get("surface") or race.get("race_track")
                if surface:
                    update_data["surface"] = surface
                if race.get("going"):
                    update_data["going"] = race["going"]
                requests.patch(update_url, headers=headers, json=update_data)
            else:
                # 不存在，插入
                insert_data = {
                    "race_date": race['race_date'],
                    "venue": race['venue'],
                    "race_no": race['race_no'],
                    "distance": race.get('distance', 0),
                    "race_class": race.get('race_class', ''),
                    "race_status": "SCHEDULED",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                surface = race.get("surface") or race.get("race_track")
                if surface:
                    insert_data["surface"] = surface
                if race.get("going"):
                    insert_data["going"] = race["going"]
                insert_url = f"{SUPABASE_URL}/rest/v1/races"
                response = requests.post(insert_url, headers=headers, json=insert_data)
                if response.status_code in [200, 201]:
                    synced_count += 1
        
        if synced_count > 0:
            print(f"✅ 同步 {synced_count} 条新赛程到数据库")
        return True
        
    except Exception as e:
        print(f"同步赛程到数据库失败: {e}")
        return False
#------------
#------------
def get_upcoming_races() -> List[Dict]:
    """
    获取未来14天的赛事列表（带缓存）
    优先从 HKJC API 获取最新赛程；失败时尝试从数据库读取
    """
    # 先走 API 快路径（detailed=0），再尝试 detailed=1
    races = get_upcoming_races_from_api(detailed=False)
    if not races:
        races = get_upcoming_races_from_api(detailed=True)

    if races:
        return _enrich_upcoming_races_from_db(races)

    print("⚠️ API获取失败，尝试从数据库读取缓存...")
    return get_upcoming_races_from_db()
#------------------
def get_races_by_date(race_date: str) -> List[Dict]:
    """获取指定日期的所有赛事"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/races?race_date=eq.{race_date}&order=race_no.asc"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"获取赛事列表失败: {e}")
        return []
#-----
# ==================== 评分缓存函数 ====================

def get_scores_from_cache(race_date: str, race_no: int, venue: str) -> Tuple[List[Dict], List[float]]:
    """从缓存表读取评分"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/race_runners_scores?race_date=eq.{race_date}&race_no=eq.{race_no}&venue=eq.{venue}&order=horse_no.asc"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200 and response.json():
            data = response.json()
            scores = []
            probabilities = []
            for item in data:
                scores.append({
                    "horse_id": item.get('horse_id'),
                    "horse_no": item.get('horse_no'),
                    "basic_score": item.get('basic_score', 50),
                    "race_score": item.get('race_score', 50),
                    "odds_score": item.get('odds_score', 50),
                    "combined_score": item.get('overall_score', 50),
                    "win_probability": item.get('win_probability', 50)
                })
                probabilities.append(item.get('win_probability', 50) / 100)
            return scores, probabilities
        return [], []
    except Exception as e:
        print(f"从缓存读取评分失败: {e}")
        return [], []


def save_scores_to_cache(race_date: str, race_no: int, venue: str, runners: List[Dict], scores: List[Dict]) -> bool:
    """保存评分到缓存表"""
    try:
        headers = get_supabase_headers(use_secret=True)
        
        for i, runner in enumerate(runners):
            if i >= len(scores):
                continue
            score = scores[i]
            
            data = {
                "race_date": race_date,
                "race_no": race_no,
                "venue": venue,
                "horse_no": runner.get('horse_no'),
                "horse_id": runner.get('horse_id'),
                "horse_name": runner.get('horse_name'),
                "basic_score": score.get('basic_score'),
                "race_score": score.get('race_score'),
                "odds_score": score.get('odds_score'),
                "overall_score": score.get('combined_score'),
                "win_probability": score.get('win_probability'),
                "calculated_at": datetime.now().isoformat()
            }
            
            # 使用 upsert
            url = f"{SUPABASE_URL}/rest/v1/race_runners_scores"
            response = requests.post(url, headers=headers, json=data)
            if response.status_code not in [200, 201]:
                print(f"保存评分失败: {response.text}")
        
        return True
    except Exception as e:
        print(f"保存评分到缓存失败: {e}")
        return False
#----------------
def calculate_all_horses_scores_v2(runners: List[Dict], user_weights: Dict) -> Tuple[List[Dict], List[float]]:
    """
    计算一场赛事所有马匹的评分和胜率（使用新评分引擎）
    """
    if not runners:
        return [], []
    
    # 批量获取所有马匹的往绩
    horse_ids = [r.get('horse_id') for r in runners if r.get('horse_id')]
    
    # 使用 scoring_engine 中的批量获取函数（注意：复数形式）
    from scoring_engine import get_horses_performances_batch
    
    # 转换为元组（因为 @st.cache_data 要求 hashable）
    horse_ids_tuple = tuple(set(horse_ids))
    perf_cache = get_horses_performances_batch(horse_ids_tuple)

    incident_llm_map = _build_incident_llm_map(
        [r.get("incident", "") for r in runners if r.get("incident")]
    )
    
    scores = []
    basic_scores = []
    race_scores = []
    odds_scores = []
    status_scores = []
    
    # 获取赛事信息
    venue = runners[0].get('venue', 'ST') if runners else 'ST'
    distance = runners[0].get('distance', 1200) if runners else 1200
    race_date = datetime.now().strftime('%Y-%m-%d')
    
    for runner in runners:
        horse_id = runner.get('horse_id')
        if not horse_id:
            # 没有 horse_id 的马匹，使用默认评分
            basic_scores.append(50.0)
            race_scores.append(50.0)
            odds_scores.append(50.0)
            status_scores.append(50.0)
            scores.append({
                "horse_id": None,
                "basic_score": 50.0,
                "race_score": 50.0,
                "odds_score": 50.0,
                "combined_score": 50.0,
                "win_probability": 50.0
            })
            continue
        
        # 从缓存获取往绩
        from scoring_engine import get_horse_past_performances_v2_optimized
        past_performances = get_horse_past_performances_v2_optimized(horse_id, perf_cache, limit=10)
        
        # 获取本场参数
        draw = runner.get('draw')
        actual_weight = runner.get('actual_weight')
        jockey = runner.get('jockey_name')
        trainer = runner.get('trainer')
        body_weight = runner.get('body_weight')
        closing_profile = runner.get('closing_profile', 'Even')
        incident = runner.get('incident', '')
        odds_win = runner.get('odds_win', 10.0)
        
        # 使用 scoring_engine 中的函数计算评分
        from scoring_engine import (
            calculate_basic_score,
            calculate_race_score,
            calculate_odds_score,
            calculate_status_score,
            calculate_overall_score,
            get_horse_weight_comfort_range_from_cache
        )
        
        # 计算各维度评分
        basic_score = calculate_basic_score(past_performances, distance, user_weights)
        weight_comfort_range = get_horse_weight_comfort_range_from_cache(horse_id, past_performances)
        
        race_score = calculate_race_score(
            horse_id, venue, distance, draw, actual_weight,
            jockey, trainer, weight_comfort_range, past_performances, user_weights
        )
        
        odds_score = calculate_odds_score(odds_win)
        llm_overlay = incident_llm_map.get(incident, 0.0) if incident else 0.0
        status_score = calculate_status_score(
            None, body_weight,
            [p.get('body_weight') for p in past_performances if p.get('body_weight')],
            incident, runner.get('running_position', ''), None, user_weights,
            llm_incident_overlay=llm_overlay,
        )
        
        combined_score = calculate_overall_score(
            basic_score, race_score, odds_score, status_score, user_weights
        )
        
        scores.append({
            "horse_id": horse_id,
            "basic_score": round(basic_score, 2),
            "race_score": round(race_score, 2),
            "odds_score": round(odds_score, 2),
            "combined_score": round(combined_score, 2),
        })
        
        basic_scores.append(basic_score)
        race_scores.append(race_score)
        odds_scores.append(odds_score)
        status_scores.append(status_score)
    
    # 计算胜率
    from scoring_engine import softmax_probabilities
    probabilities = softmax_probabilities([s["combined_score"] for s in scores], temperature=0.8)
    
    for i, prob in enumerate(probabilities):
        scores[i]["win_probability"] = round(prob * 100, 2)
    
    return scores, probabilities


def get_horses_performances_batch(horse_ids: List[str], limit: int = 10) -> Dict[str, List[Dict]]:
    """
    批量获取多匹马的历史往绩
    """
    if not horse_ids:
        return {}
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 构建 IN 查询
        ids_str = ','.join([f"'{hid}'" for hid in horse_ids])
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?horse_id=in.({ids_str})&order=race_date.desc&limit=5000"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"批量获取失败: {response.status_code}")
            return {}
        
        data = response.json()
        
        # 构建缓存
        cache = {}
        for p in data:
            hid = p.get('horse_id')
            if not hid:
                continue
            if hid not in cache:
                cache[hid] = []
            cache[hid].append(p)
        
        # 限制每匹马返回的记录数
        for hid in cache:
            cache[hid] = cache[hid][:limit]
        
        print(f"批量获取 {len(horse_ids)} 匹马，共 {len(data)} 条记录")
        return cache
        
    except Exception as e:
        print(f"批量获取异常: {e}")
        return {}
#-----------------
def precompute_race_scores(race_date: str, race_no: int, venue: str, user_weights: Dict = None) -> bool:
    """预计算单场赛事的评分并保存到缓存"""
    try:
        if user_weights is None:
            user_weights = {"basic": 0.30, "race": 0.40, "odds": 0.30}
        
        # 获取出赛马匹
        runners = get_race_runners_with_details(race_date, venue, race_no)
        if not runners:
            return False
        
        # 计算评分
        scores, probabilities = calculate_all_horses_scores(None, runners, user_weights)
        
        # 保存到缓存
        return save_scores_to_cache(race_date, race_no, venue, runners, scores)
        
    except Exception as e:
        print(f"预计算评分失败: {e}")
        return False


def precompute_all_races_for_date(race_date: str, venue: str = None, user_weights: Dict = None) -> Dict:
    """预计算一天所有赛事的评分"""
    result = {"success": 0, "failed": 0, "total": 0}
    
    venues_to_process = [venue] if venue else ['ST', 'HV']
    
    for v in venues_to_process:
        for race_no in range(1, 13):
            result["total"] += 1
            if precompute_race_scores(race_date, race_no, v, user_weights):
                result["success"] += 1
                print(f"✅ 预计算成功: {race_date} {v} 第{race_no}场")
            else:
                result["failed"] += 1
    
    return result
#-------------------------
def _is_valid_runner_horse_no(horse_no) -> bool:
    """有效出赛马号须为正整数（0 为同步异常占位，无赔率）。"""
    if horse_no is None or horse_no == "":
        return False
    try:
        return int(horse_no) > 0
    except (TypeError, ValueError):
        return False


def _filter_valid_race_runners(runners: List[Dict]) -> List[Dict]:
    valid = [r for r in runners if _is_valid_runner_horse_no(r.get("horse_no"))]
    dropped = len(runners) - len(valid)
    if dropped:
        print(f"已过滤无效马号出马 {dropped} 条")
    return valid


def get_race_runners_with_details(race_date: str, venue: str, race_no: int) -> List[Dict]:
    """
    获取赛事出赛马匹详情
    
    数据源策略：
    - 如果 race_date >= 今天：从 race_runners_clean 获取（Node.js API 实时数据）
    - 如果 race_date < 今天：从 past_performances_v2 获取（历史数据）
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # ==================== 未来赛事：从 race_runners_clean 获取 ====================
        if race_date >= today:
            # 显式选择需要的字段，确保包含 odds_place
            url = f"{SUPABASE_URL}/rest/v1/race_runners_clean?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race_no}&select=*"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200 and response.json():
                runners = response.json()
                result = []
                for runner in runners:
                    # 安全获取赔率
                    odds_win_raw = runner.get('odds_win')
                    odds_place_raw = runner.get('odds_place')
                    try:
                        odds_win = float(odds_win_raw) if odds_win_raw else None
                    except (ValueError, TypeError):
                        odds_win = None
                    try:
                        odds_place = float(odds_place_raw) if odds_place_raw else None
                    except (ValueError, TypeError):
                        odds_place = None
                    
                    result.append({
                        "horse_id": runner.get('horse_id'),
                        "horse_name_zh": runner.get('horse_name_zh', runner.get('horse_name', '')),
                        "horse_name_en": runner.get('horse_name_en', ''),
                        "horse_name": "",
                        "horse_no": runner.get('horse_no'),
                        "draw": runner.get('draw'),
                        "actual_weight": runner.get('actual_weight'),
                        "jockey_name": runner.get('jockey_name'),
                        "odds_win": odds_win,
                        "odds_place": odds_place,  # ← 关键：添加位置赔率
                        "finishing_position": None,
                        "trainer": runner.get('trainer_name'),
                        "rating": runner.get('rating'),
                    })
                
                print(f"从 race_runners_clean 获取到 {len(result)} 匹马 (未来赛事)")
                return _filter_valid_race_runners(_enrich_runner_horse_names(result))
            else:
                print(f"race_runners_clean 中无数据: {race_date} {venue} 第{race_no}场")
                return []
        
        # ==================== 历史赛事：从 past_performances_v2 获取 ====================
        else:
            url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race_no}&order=position.asc&limit=100"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200 and response.json():
                data = response.json()
                result = []
                for p in data:
                    # 安全获取赔率
                    odds_raw = p.get('odds')
                    try:
                        odds_win = float(odds_raw) if odds_raw else None
                    except (ValueError, TypeError):
                        odds_win = None
                    
                    # 安全获取体重
                    body_weight = p.get('body_weight')
                    if body_weight:
                        try:
                            body_weight = int(body_weight)
                        except (ValueError, TypeError):
                            body_weight = None
                    
                    result.append({
                        "horse_id": p.get('horse_id'),
                        "horse_name_zh": p.get('horse_name', ''),
                        "horse_name_en": p.get('horse_name_en', ''),
                        "horse_name": "",
                        "horse_no": p.get('horse_no'),
                        "draw": p.get('draw'),
                        "actual_weight": p.get('actual_weight'),
                        "jockey_name": p.get('jockey'),
                        "odds_win": odds_win,
                        "odds_place": None,  # 历史数据没有位置赔率
                        "finishing_position": p.get('position'),
                        "trainer": p.get('trainer'),
                        "body_weight": body_weight,
                        "lbw_raw": p.get('lbw_raw'),
                        "running_position": p.get('running_position'),
                        "closing_profile": p.get('closing_profile'),
                        "incident": p.get('incident', ''),
                        "distance": p.get('distance'),
                        "venue": p.get('venue'),
                        "race_class": p.get('race_class'),
                        "going": p.get('going'),
                    })
                
                print(f"从 past_performances_v2 获取到 {len(result)} 匹马 (历史赛事)")
                return _filter_valid_race_runners(_enrich_runner_horse_names(result))
            else:
                return []
        
    except Exception as e:
        print(f"获取出赛马匹失败: {e}")
        return []


# ==================== 辅助函数：凯利公式计算 ====================

def calculate_kelly_fraction(probability: float, odds: float) -> float:
    """
    计算凯利公式建议投注比例
    f* = (p × b - q) / b
    其中 b = odds - 1
    """
    if odds <= 1 or probability <= 0 or probability >= 1:
        return 0.0
    
    b = odds - 1
    q = 1 - probability
    
    f = (probability * b - q) / b
    return max(0.0, min(0.25, f))  # 限制最大25%


def calculate_expected_value(probability: float, odds: float, stake: float) -> float:
    """计算期望值"""
    if odds <= 0:
        return -stake
    return probability * (stake * odds) - stake


# ==================== 辅助函数：胜率排序 ====================

def get_top_horses_by_probability(runners: List[Dict], limit: int = 3) -> List[Dict]:
    """按胜率排序，获取前N匹马"""
    if not runners:
        return []
    
    # 过滤掉 None 值
    valid_runners = []
    for r in runners:
        if r is not None and isinstance(r, dict):
            valid_runners.append(r)
    
    if not valid_runners:
        return []
    
    sorted_runners = sorted(valid_runners, key=lambda x: x.get('win_probability', 0), reverse=True)
    return sorted_runners[:limit]
#-----------------
# ==================== ML 模型训练和预测 ====================
# 尝试导入 ML 库
try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

#-------------
def prepare_ml_features(horse_id: int, race_id: int, past_performances_v2: List[Dict]) -> Dict:
    """
    为 ML 模型准备特征
    使用最近 N 场数据（N 从 get_ml_config 读取，默认30场）
    """
    features = {}
    
    # 获取 ML 配置
    from scoring_engine import get_ml_config
    ml_config = get_ml_config()
    recent_games = ml_config.get("recent_games", 30)
    
    # ✅ 只取最近 N 场（从 get_ml_config 读取）
    if len(past_performances_v2) > recent_games:
        recent_performances = past_performances_v2[:recent_games]
    else:
        recent_performances = past_performances_v2
    
    # 1. 基础统计特征（基于最近 N 场）
    if recent_performances:
        total = len(recent_performances)
        
        # 近5场（从最近 N 场中取）
        recent_5 = recent_performances[:5] if total >= 5 else recent_performances
        
        # 近10场
        recent_10 = recent_performances[:10] if total >= 10 else recent_performances
        
        # 胜率、入Q率、入T率（最近10场）
        wins_10 = sum(1 for p in recent_10 if p.get('position') == 1)
        places_10 = sum(1 for p in recent_10 if p.get('position', 0) <= 2)
        shows_10 = sum(1 for p in recent_10 if p.get('position', 0) <= 3)
        
        features['win_rate_10'] = wins_10 / len(recent_10) if recent_10 else 0
        features['place_rate_10'] = places_10 / len(recent_10) if recent_10 else 0
        features['show_rate_10'] = shows_10 / len(recent_10) if recent_10 else 0
        
        # 近5场胜率
        wins_5 = sum(1 for p in recent_5 if p.get('position') == 1)
        features['win_rate_5'] = wins_5 / len(recent_5) if recent_5 else 0
        
        # 平均完成时间（近5场）
        finish_times = [p.get('finish_seconds', 0) for p in recent_5 if p.get('finish_seconds')]
        features['avg_finish_time'] = np.mean(finish_times) if finish_times else 0
        
        # 名次趋势（最近5场名次变化）
        positions = [p.get('position', 0) for p in recent_5 if p.get('position')]
        if len(positions) >= 2:
            features['position_trend'] = positions[0] - positions[-1]  # 正数表示进步
        else:
            features['position_trend'] = 0
        
        # 负磅趋势
        weights = [p.get('actual_weight', 0) for p in recent_5 if p.get('actual_weight')]
        if len(weights) >= 2:
            features['weight_trend'] = weights[0] - weights[-1]
        else:
            features['weight_trend'] = 0
        
        # 近3场胜率（从最近 N 场中取）
        recent_3 = recent_performances[:3] if total >= 3 else recent_performances
        wins_3 = sum(1 for p in recent_3 if p.get('position') == 1)
        features['win_rate_3'] = wins_3 / len(recent_3) if recent_3 else 0
        
    else:
        # 无数据，填充默认值
        features['win_rate_10'] = 0
        features['place_rate_10'] = 0
        features['show_rate_10'] = 0
        features['win_rate_5'] = 0
        features['win_rate_3'] = 0
        features['avg_finish_time'] = 0
        features['position_trend'] = 0
        features['weight_trend'] = 0
    
    # 本场特征：增加反映马匹实力的字段
    features['draw'] = 0
    features['actual_weight'] = 0
    features['odds'] = 0
    features['distance'] = 0
    features['jockey_id'] = 0
    features['trainer_id'] = 0
    
    # ✅ 记录使用了多少场数据，便于调试
    features['data_used_count'] = len(recent_performances)
    
    return features

#--------
def train_lightgbm_model(draws: List[Dict], lookback: int = 0) -> Optional[Any]:
    """训练 LightGBM 模型（三分类：好/中/差）"""
    if not LGB_AVAILABLE:
        return None
    
    try:
        X_list = []
        y_list = []
        
        races = [d for d in draws if d.get('race_date')]
        
        for i, race in enumerate(races):
            if i < lookback:
                continue
            
            for runner in race.get('runners', []):
                horse_id = runner.get('horse_id')
                if not horse_id:
                    continue
                
                past = get_horse_past_performances_v2(horse_id, limit=10)
                features = prepare_ml_features(horse_id, race.get('race_id'), past)
                
                if features:
                    features['draw'] = runner.get('draw', 0)
                    features['actual_weight'] = runner.get('actual_weight', 0)
                    features['odds'] = runner.get('odds_win', 0)
                    features['distance'] = race.get('distance', 0)
                    
                    X_list.append(features)
                    
                    # ⭐ 三分类标签
                    position = runner.get('position', 0)
                    if position <= 3:
                        y_list.append(2)   # 好马组
                    elif position <= 8:
                        y_list.append(1)   # 中马组
                    else:
                        y_list.append(0)   # 差马组
        
        if len(X_list) < 50:
            return None
        
        X_df = pd.DataFrame(X_list).fillna(0)
        y_series = pd.Series(y_list)
        
        # ⭐ 三分类参数
        model = lgb.LGBMClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            verbose=-1,
            objective='multiclass',
            num_class=3
        )
        
        model.fit(X_df, y_series)
        return model
        
    except Exception as e:
        print(f"LightGBM 训练失败: {e}")
        return None

#-------------
def train_xgboost_model(draws: List[Dict], lookback: int = 0) -> Optional[Any]:
    """训练 XGBoost 模型（三分类：好/中/差）"""
    if not XGB_AVAILABLE:
        return None
    
    try:
        X_list = []
        y_list = []
        
        races = [d for d in draws if d.get('race_date')]
        
        for i, race in enumerate(races):
            if i < lookback:
                continue
            
            for runner in race.get('runners', []):
                horse_id = runner.get('horse_id')
                if not horse_id:
                    continue
                
                past = get_horse_past_performances_v2(horse_id, limit=10)
                features = prepare_ml_features(horse_id, race.get('race_id'), past)
                
                if features:
                    features['draw'] = runner.get('draw', 0)
                    features['actual_weight'] = runner.get('actual_weight', 0)
                    features['odds'] = runner.get('odds_win', 0)
                    features['distance'] = race.get('distance', 0)
                    
                    X_list.append(features)
                    
                    # ⭐ 三分类标签
                    position = runner.get('position', 0)
                    if position <= 3:
                        y_list.append(2)   # 好马组
                    elif position <= 8:
                        y_list.append(1)   # 中马组
                    else:
                        y_list.append(0)   # 差马组
        
        if len(X_list) < 50:
            return None
        
        X_df = pd.DataFrame(X_list).fillna(0)
        y_series = pd.Series(y_list)
        
        # ⭐ 三分类参数
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric='mlogloss',
            verbosity=0,
            objective='multi:softprob',
            num_class=3
        )
        
        model.fit(X_df, y_series)
        return model
        
    except Exception as e:
        print(f"XGBoost 训练失败: {e}")
        return None


def predict_with_ml_model(model: Any, features: Dict) -> float:
    """使用 ML 模型预测胜率"""
    if model is None:
        return 0.5
    
    try:
        X_pred = pd.DataFrame([features]).fillna(0)
        prob = model.predict_proba(X_pred)[0][1]
        return prob
    except Exception as e:
        print(f"预测失败: {e}")
        return 0.5
#--------------
def build_ml_features_for_prediction(runner: Dict, past_before: List[Dict], 
                                       race_date: str, venue: str, distance: int,
                                       horse_birth_years: Dict, 
                                       jockey_win_rates: Dict, 
                                       trainer_base_scores: Dict,
                                       horse_id: str = None,
                                       incident_llm_map: Optional[Dict[str, float]] = None) -> Dict:
    """
    为预测构建完整的30个特征（与训练一致）
    
    参数：
        runner: 当前马匹数据（包含 draw, actual_weight, odds, body_weight, incident, running_position, jockey, trainer 等）
        past_before: 该马匹在 race_date 之前的往绩列表（已按日期降序）
        race_date: 当前赛事日期
        venue: 场地
        distance: 路程
        horse_birth_years: {horse_id: birth_year}
        jockey_win_rates: {jockey_name: win_rate}
        trainer_base_scores: {trainer_name: score}
        horse_id: 马匹ID（如果 runner 中没有）
    
    返回：
        特征字典（30个特征）
    """
    if horse_id is None:
        horse_id = runner.get('horse_id', '')
    
    features = {}
    
    # ========== 1. 基础往绩因子 ==========
    total = len(past_before)
    if total > 0:
        recent_3 = past_before[:3] if total >= 3 else past_before
        recent_5 = past_before[:5] if total >= 5 else past_before
        recent_10 = past_before[:10] if total >= 10 else past_before
        
        wins_3 = sum(1 for p in recent_3 if p.get('position') == 1)
        features['win_rate_3'] = wins_3 / len(recent_3) if recent_3 else 0
        
        wins_10 = sum(1 for p in recent_10 if p.get('position') == 1)
        features['win_rate_10'] = wins_10 / len(recent_10) if recent_10 else 0
        
        places_10 = sum(1 for p in recent_10 if p.get('position', 0) in [1, 2])
        features['place_rate_10'] = places_10 / len(recent_10) if recent_10 else 0
        
        shows_10 = sum(1 for p in recent_10 if p.get('position', 0) in [1, 2, 3])
        features['show_rate_10'] = shows_10 / len(recent_10) if recent_10 else 0
        
        wins_5 = sum(1 for p in recent_5 if p.get('position') == 1)
        features['win_rate_5'] = wins_5 / len(recent_5) if recent_5 else 0
        
        features['win_rate'] = features['win_rate_10']
        features['place_rate'] = features['place_rate_10']
        features['show_rate'] = features['show_rate_10']
        
        # 路程评分
        distance_scores = []
        for p in recent_10:
            p_distance = p.get('distance', 0)
            if p_distance == 0:
                continue
            diff = abs(p_distance - distance)
            weight = 1.0 - min(0.7, diff / 400)
            pos = p.get('position', 0)
            if pos == 1:
                score = 100
            elif pos == 2:
                score = 85
            elif pos == 3:
                score = 70
            elif pos <= 5:
                score = 55
            elif pos <= 8:
                score = 40
            else:
                score = 25
            distance_scores.append(score * weight)
        features['distance_rating'] = sum(distance_scores) / len(distance_scores) if distance_scores else 0
        
        # 名次趋势
        positions = [p.get('position', 0) for p in recent_5 if p.get('position', 0) > 0]
        if len(positions) >= 2:
            if len(positions) >= 3:
                trend = (positions[-3] - positions[-1])
            else:
                trend = positions[-2] - positions[-1]
            features['trend'] = max(-10, min(10, trend)) / 10
        else:
            features['trend'] = 0
        
        weights = [p.get('actual_weight', 0) for p in past_before if p.get('actual_weight', 0) > 0]
        features['avg_weight'] = sum(weights) / len(weights) if weights else 0
    else:
        features['win_rate_3'] = 0
        features['win_rate_10'] = 0
        features['place_rate_10'] = 0
        features['show_rate_10'] = 0
        features['win_rate_5'] = 0
        features['win_rate'] = 0
        features['place_rate'] = 0
        features['show_rate'] = 0
        features['distance_rating'] = 0
        features['trend'] = 0
        features['avg_weight'] = 0
    
    # ========== 2. 场次因素 ==========
    venue_perf = [p for p in past_before if p.get('venue') == venue]
    if venue_perf:
        venue_wins = sum(1 for p in venue_perf[:5] if p.get('position') == 1)
        features['same_course'] = venue_wins / len(venue_perf[:5]) if venue_perf[:5] else 0
    else:
        features['same_course'] = 0
    
    dist_perf = [p for p in past_before if p.get('distance') == distance]
    if dist_perf:
        dist_wins = sum(1 for p in dist_perf[:5] if p.get('position') == 1)
        features['same_distance'] = dist_wins / len(dist_perf[:5]) if dist_perf[:5] else 0
    else:
        features['same_distance'] = 0
    
    draw_val = runner.get('draw', 0)
    if draw_val and draw_val > 0:
        features['draw'] = 100 - (draw_val - 1) * (80 / 13)
    else:
        features['draw'] = 0
    
    features['weight'] = runner.get('actual_weight', 0) or 0
    
    # ========== 3. 赔率因素 ==========
    odds_val = runner.get('odds_win', runner.get('odds', 0))
    if odds_val and odds_val > 0:
        features['odds'] = min(100, max(0, 100 * (1 - (odds_val - 1) / 98)))
    else:
        features['odds'] = 0
    
    features['odds_trend'] = 0
    features['ev'] = 0
    
    # ========== 4. 状态因素（填充真实值） ==========
    # ✅ 年龄因子
    birth_year = horse_birth_years.get(horse_id)
    if birth_year and birth_year > 0:
        try:
            race_year = int(race_date[:4])
            age = race_year - birth_year
            if 4 <= age <= 5:
                features['age'] = 100
            elif age == 3 or age == 6:
                features['age'] = 70
            elif age == 2 or age == 7:
                features['age'] = 50
            elif age >= 8:
                features['age'] = 30
            else:
                features['age'] = 40
        except:
            features['age'] = 0
    else:
        features['age'] = 0
    
    # ✅ 体重变化
    current_weight = runner.get('body_weight')
    if current_weight and current_weight > 0:
        last_weight = None
        for p in past_before:
            w = p.get('body_weight')
            if w and w > 0:
                last_weight = w
                break
        if last_weight and last_weight > 0:
            change = abs(current_weight - last_weight)
            if change <= 5:
                features['weight_change'] = 100
            elif change <= 10:
                features['weight_change'] = 70
            elif change <= 15:
                features['weight_change'] = 40
            else:
                features['weight_change'] = 20
        else:
            features['weight_change'] = 50
    else:
        features['weight_change'] = 50
    
    # ✅ 事件报告（规则 + LLM 缓存叠加，热路径不调 API）
    incident_text = runner.get('incident', '')
    features['incident'] = _incident_feature_score(incident_text, incident_llm_map)
    
    # ✅ 冲刺能力
    running_pos = runner.get('running_position', '')
    if running_pos and running_pos != '0' and running_pos != '---':
        positions = [int(c) for c in str(running_pos) if c.isdigit()]
        if len(positions) >= 2:
            first_pos = positions[0]
            last_pos = positions[-1]
            improvement = first_pos - last_pos
            if improvement >= 5:
                features['burst'] = 95
            elif improvement >= 3:
                features['burst'] = 85
            elif improvement >= 1:
                features['burst'] = 70
            elif improvement == 0:
                features['burst'] = 60
            else:
                features['burst'] = 40
        else:
            features['burst'] = 50
    else:
        features['burst'] = 50
    
    # ========== 5. 骑师和练马师（填充真实值） ==========
    # ✅ 骑师
    jockey = runner.get('jockey_name', runner.get('jockey', ''))
    if jockey:
        jockey_win_rate = jockey_win_rates.get(jockey, 0.12)
        features['jockey'] = jockey_win_rate * 100
        features['jockey_win_rate'] = jockey_win_rate * 100
    else:
        features['jockey'] = 0
        features['jockey_win_rate'] = 0
    
    # ✅ 练马师
    trainer = runner.get('trainer_name', runner.get('trainer', ''))
    if trainer:
        features['trainer'] = trainer_base_scores.get(trainer, 50)
    else:
        features['trainer'] = 0
    
    # ========== 6. 额外字段 ==========
    features['data_used_count'] = len(past_before)
    features['actual_weight'] = runner.get('actual_weight', 0) or 0
    features['distance'] = distance
    
    # ========== 7. 新马标记 ==========
    total_races = len(past_before)
    if total_races < 3:
        features['is_new_horse'] = 1
        if horse_id and 'PPG' in str(horse_id):
            features['new_horse_type'] = 2
        elif horse_id and 'INT' in str(horse_id):
            features['new_horse_type'] = 3
        else:
            features['new_horse_type'] = 1
    else:
        features['is_new_horse'] = 0
        features['new_horse_type'] = 0
    
    return features
#--------------
def get_trainer_base_scores() -> Dict[str, int]:
    """获取练马师基础评分"""
    return {
        "蔡約翰": 100, "大衛希斯": 95, "姚本輝": 90,
        "告東尼": 90, "羅富全": 85, "呂健威": 85,
        "沈集成": 80, "方嘉柏": 80, "伍鵬志": 80,
        "韋達": 75, "蘇偉賢": 70, "文家良": 70,
        "賀賢": 65, "鄭俊偉": 65, "葉楚航": 60,
        "徐雨石": 60, "黎昭昇": 60, "巫偉傑": 55,
        "廖康銘": 55, "游達榮": 55, "丁冠豪": 50,
    }
#-------------
def get_model_predictions(race_date: str, venue: str, race_no: int, 
                          runners: List[Dict], model_type: str, model=None,
                          perf_cache: Optional[Dict[str, List[Dict]]] = None,
                          incident_llm_map: Optional[Dict[str, float]] = None) -> List[float]:
    """
    获取 ML 模型预测的胜率
    支持二分类和三分类模型
    perf_cache: 可选，回测时传入本地 horse_cache，避免每场重复查库
    """
    from scoring_engine import get_ml_config
    ml_config = get_ml_config()
    recent_games = ml_config.get("recent_games", 60)
    
    if not runners:
        return []
    if model is None:
        return [0.34] * len(runners)
    
    distance = runners[0].get('distance', 1200) if runners else 1200
    
    horse_ids = [r.get('horse_id') for r in runners if r.get('horse_id')]
    if not horse_ids:
        return [0.34] * len(runners)
    
    if perf_cache is None:
        perf_cache = se_get_horses_performances_batch(tuple(set(horse_ids)))
    horse_birth_years = get_cached_horse_birth_years()
    jockey_win_rates = get_cached_jockey_win_rates()
    trainer_base_scores = get_cached_trainer_base_scores_for_ml()
    
    predictions = []
    #-----------
    for runner in runners:
        horse_id = runner.get('horse_id')
        if not horse_id:
            predictions.append(0.34)
            continue
        
        past_before = [
            p for p in perf_cache.get(horse_id, []) if p.get("race_date", "") < race_date
        ][:recent_games]
        
        features = build_ml_features_for_prediction(
            runner, past_before, race_date, venue, distance,
            horse_birth_years, jockey_win_rates, trainer_base_scores,
            horse_id,
            incident_llm_map=incident_llm_map,
        )
        
        if features:
            all_probs = predict_with_model(model, features, model_type, return_all_probs=True)
            # 三分类：取好马组概率（索引2）
            if isinstance(all_probs, list) and len(all_probs) >= 3:
                good_group_prob = all_probs[2]
            else:
                good_group_prob = 0.34
        else:
            good_group_prob = 0.34
        
        predictions.append(good_group_prob)
    
    return predictions

#------------
def get_historical_draws_for_training(limit: int = 300) -> List[Dict]:
    """
    获取用于训练的历史数据
    优先从 race_runners_clean 获取，若无数据则从 past_performances_v2 获取
    """
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/races?order=race_date.desc&limit={limit}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return []
        
        races = response.json()
        
        for race in races:
            race_date = race.get('race_date')
            venue = race.get('venue')
            race_no = race.get('race_no')
            race_id = race.get('race_id')
            
            runners = []
            
            # 1. 首先尝试从 race_runners_clean 获取（未来赛事）
            runners_url = f"{SUPABASE_URL}/rest/v1/race_runners_clean?race_id=eq.{race_id}"
            runners_response = requests.get(runners_url, headers=headers)
            
            if runners_response.status_code == 200 and runners_response.json():
                runners = runners_response.json()
            else:
                # 2. 如果 race_runners_clean 无数据，从 past_performances_v2 获取（历史赛事）
                perf_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race_no}&order=position.asc"
                perf_response = requests.get(perf_url, headers=headers)
                if perf_response.status_code == 200:
                    perf_data = perf_response.json()
                    for p in perf_data:
                        # 构造与 race_runners_clean 兼容的 runners 结构
                        runners.append({
                            'horse_id': p.get('horse_id'),
                            'horse_name': p.get('horse_name'),
                            'horse_no': p.get('horse_no'),
                            'draw': p.get('draw'),
                            'actual_weight': p.get('actual_weight'),
                            'odds_win': p.get('odds'),
                            'position': p.get('position'),  # 用于训练标签
                            'jockey_name': p.get('jockey'),
                            'trainer_name': p.get('trainer'),
                            'body_weight': p.get('body_weight'),
                            'running_position': p.get('running_position'),
                            'incident': p.get('incident'),
                        })
            
            race['runners'] = runners
        
        return races
        
    except Exception as e:
        print(f"获取训练数据失败: {e}")
        return []
#--------------
# ==================== 评分缓存（内存缓存）====================

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_race_scores(race_date: str, race_no: int, venue: str) -> Tuple[List[Dict], List[float]]:
    """
    缓存整场赛事的评分结果
    - 首次调用时计算并缓存到 race_scores_cache 表
    - 后续调用直接返回缓存结果
    - 缓存有效期 1 小时
    """
    print(f"=== get_cached_race_scores 被调用: {race_date} {venue} R{race_no} ===")
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # ==================== 1. 优先从缓存表读取 ====================
        cache_url = f"{SUPABASE_URL}/rest/v1/race_scores_cache?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race_no}&order=horse_no.asc"
        cache_response = requests.get(cache_url, headers=headers)
        
        if cache_response.status_code == 200 and cache_response.json():
            cache_data = cache_response.json()
            
            # 检查缓存是否完整（马匹数量应 > 0）
            if len(cache_data) > 0:
                scores = []
                probabilities = []
                for item in cache_data:
                    scores.append({
                        "horse_id": item.get('horse_id'),
                        "horse_no": item.get('horse_no'),
                        "basic_score": item.get('basic_score', 50),
                        "race_score": item.get('race_score', 50),
                        "odds_score": item.get('odds_score', 50),
                        "combined_score": item.get('overall_score', 50),
                        "win_probability": item.get('win_probability', 50)
                    })
                    probabilities.append(item.get('win_probability', 50) / 100)
                
                print(f"✅ 从缓存表读取评分: {race_date} {venue} R{race_no}, {len(scores)} 匹马")
                return scores, probabilities
        
        # ==================== 2. 无缓存时实时计算 ====================
        print(f"🔄 缓存未命中，实时计算: {race_date} {venue} R{race_no}")
        
        # 获取出赛马匹
        runners = get_race_runners_with_details(race_date, venue, race_no)
        if not runners:
            print(f"⚠️ 无出赛马匹数据: {race_date} {venue} R{race_no}")
            return [], []
        
        # 用户权重（可从用户设置读取，这里使用默认值）
        user_weights = {
            "basic": 0.30,
            "race": 0.40,
            "odds": 0.30,
            "temperature": 0.8,
            "odds_mix_ratio": 0.6
        }
        
        # 为没有赔率的马匹设置默认赔率
        for runner in runners:
            if not runner.get('odds_win') or runner.get('odds_win') <= 0:
                runner['odds_win'] = 10.0
        
        # 使用新的评分引擎计算
        scores, probabilities = calculate_all_horses_scores_v2(runners, user_weights)
        
        # ==================== 3. 保存到缓存表 ====================
        save_scores_to_cache(race_date, race_no, venue, runners, scores, probabilities)
        
        print(f"✅ 评分计算完成并已缓存: {race_date} {venue} R{race_no}")
        return scores, probabilities
        
    except Exception as e:
        print(f"❌ 缓存评分失败: {e}")
        return [], []
#-----------
def train_model_for_smart_betting(model_type: str, start_date: str = None, end_date: str = None) -> Optional[Any]:
    """
    为智能投注训练ML模型（使用与回测相同的数据和特征）
    end_date 作为 cutoff：训练标签仅包含严格早于该日的赛事（不含 cutoff 当日）。
    历史测试模式下应传入所选赛日，确保预测赛日不在训练范围内。
    """
    from scoring_engine import get_cached_model, set_cached_model, get_current_weights_hash
    import hashlib
    
    # 确定日期范围
    if start_date is None or end_date is None:
        end_date_dt = datetime.now()
        start_date_dt = end_date_dt - timedelta(days=SMART_BETTING_ML_TRAINING_WINDOW_DAYS)
        start_date = start_date_dt.strftime("%Y-%m-%d")
        end_date = end_date_dt.strftime("%Y-%m-%d")
    
    # 生成缓存键（与回测一致）
    weight_hash = get_current_weights_hash()
    cache_key = f"{model_type}_{start_date}_{end_date}_{weight_hash}"
    
    # 检查缓存
    cached_model = get_cached_model(cache_key)
    if cached_model is not None:
        print(f"✅ 智能投注使用缓存模型: {cache_key}")
        return cached_model
    
    # 批量获取数据（与回测相同）
    all_performances = get_performances_batch(start_date, end_date)
    if not all_performances:
        st.error("无法获取历史数据，请检查日期范围")
        return None
    
    # 构建马匹往绩缓存
    horse_cache = build_horse_performances_cache(all_performances)
    incident_llm_map = _build_incident_llm_map(
        [p.get("incident", "") for p in all_performances if p.get("incident")]
    )
    
    # 使用 cutoff_date = end_date（使用所有数据训练）
    train_X, train_y = prepare_training_data_by_date(
        end_date, all_performances, horse_cache, incident_llm_map=incident_llm_map
    )
    
    if train_X is None or len(train_X) < 50:
        st.error(f"训练数据不足: {len(train_X) if train_X is not None else 0} 条")
        return None
    
    # 训练模型（使用与回测相同的函数）
    model = get_or_train_model(train_X, train_y, model_type, cache_key)
    
    if model is not None:
        set_cached_model(cache_key, model)
        print(f"✅ 智能投注模型训练完成: {cache_key}")
    else:
        st.error("模型训练失败")
    
    return model

# ==================== 智能投注：性能优化辅助 ====================

def _resolve_ml_model_type(model_choice: str) -> Optional[str]:
    if model_choice == "LightGBM":
        return "lightgbm"
    if model_choice == "XGBoost":
        return "xgboost"
    if model_choice == "集成模型":
        return "ensemble"
    return None


def _get_smart_betting_training_window(prediction_cutoff_date: Optional[str] = None) -> Tuple[str, str]:
    """
    返回 ML 训练数据窗口 (start_date, cutoff_date)。
    cutoff_date 为预测赛日：训练标签仅使用严格早于该日的赛事（与回测一致）。
    """
    if prediction_cutoff_date:
        cutoff_dt = datetime.strptime(prediction_cutoff_date, "%Y-%m-%d")
        start_dt = cutoff_dt - timedelta(days=SMART_BETTING_ML_TRAINING_WINDOW_DAYS)
        return start_dt.strftime("%Y-%m-%d"), prediction_cutoff_date

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=SMART_BETTING_ML_TRAINING_WINDOW_DAYS)
    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def _runner_has_valid_odds(runner: Dict) -> bool:
    raw = runner.get("odds_win")
    try:
        return raw is not None and float(raw) > 0
    except (TypeError, ValueError):
        return False


def _runners_need_live_sync(runners: List[Dict]) -> bool:
    """DB 无出马或全部无独赢赔率时才阻塞同步 API。"""
    if not runners:
        return True
    return not any(_runner_has_valid_odds(r) for r in runners)


@st.cache_resource(show_spinner=False)
def _cached_smart_betting_ml_model(model_type: str, start_date: str, cutoff_date: str):
    """跨会话缓存已训练 ML 模型（Streamlit Cloud 进程内复用，避免每次重训）。"""
    return train_model_for_smart_betting(model_type, start_date, cutoff_date)


def get_smart_betting_ml_model(model_choice: str, prediction_cutoff_date: Optional[str] = None):
    """会话内缓存 ML 模型；历史模式下训练数据不包含预测赛日及之后赛事。"""
    model_type = _resolve_ml_model_type(model_choice)
    if not model_type:
        return None, None

    session_key = f"{model_type}_{prediction_cutoff_date or 'live'}"
    if (
        st.session_state.get("smart_betting_ml_session_key") == session_key
        and st.session_state.get("smart_betting_ml_model") is not None
    ):
        return model_type, st.session_state["smart_betting_ml_model"]

    start_date, cutoff_date = _get_smart_betting_training_window(prediction_cutoff_date)
    model = _cached_smart_betting_ml_model(model_type, start_date, cutoff_date)
    if model is not None:
        st.session_state["smart_betting_ml_session_key"] = session_key
        st.session_state["smart_betting_ml_type"] = model_type
        st.session_state["smart_betting_ml_model"] = model
    return model_type, model


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_jockey_win_rates() -> Dict[str, float]:
    return get_jockey_win_rates_from_db()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_trainer_base_scores_for_ml() -> Dict[str, int]:
    return get_trainer_base_scores()


@st.cache_data(ttl=600, show_spinner=False)
def get_cached_horse_birth_years() -> Dict[str, int]:
    return load_horse_birth_years()


@st.cache_data(ttl=300, show_spinner=False)
def _load_scoring_config_user_defaults() -> Optional[Dict]:
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/scoring_config?id=eq.1"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200 and response.json():
            return response.json()[0]
    except Exception:
        pass
    return None


def _try_apply_precomputed_scores(
    runners: List[Dict],
    race_date: str,
    venue: str,
    race_no: int,
) -> Optional[List[Dict]]:
    """若 race_runners_scores 已有预计算且覆盖大部分马匹，跳过实时评分。"""
    cached_scores, _ = get_scores_from_cache(race_date, race_no, venue)
    if not cached_scores:
        return None
    by_no = {s.get("horse_no"): s for s in cached_scores if s.get("horse_no") is not None}
    if len(by_no) < max(1, len(runners) * 2 // 3):
        return None
    merged: List[Dict] = []
    hit = 0
    for runner in runners:
        row = dict(runner)
        sc = by_no.get(row.get("horse_no"))
        if sc:
            overall = sc.get("combined_score", 50)
            wp_raw = sc.get("win_probability", 0)
            wp = wp_raw / 100 if wp_raw and wp_raw > 1 else (wp_raw or 0)
            row["overall_score"] = overall
            row["combined_score"] = overall
            row["win_probability"] = wp
            hit += 1
        merged.append(row)
    return merged if hit >= max(1, len(runners) * 2 // 3) else None


def _default_smart_betting_weights_config() -> Dict:
    config = get_scoring_config()
    return {
        "level1_weights": config.get("level1", {}),
        "basic_weights": config.get("basic", {}),
        "race_weights": config.get("race", {}),
        "odds_weights": config.get("odds", {}),
        "status_weights": config.get("status", {}),
    }


def _smart_betting_runners_cache_key(selected_race: Dict, model_choice: str) -> str:
    weights_sig = "custom" if st.session_state.get("scoring_weights_applied") else "default"
    return (
        f"{selected_race.get('race_date')}|{selected_race.get('venue')}|"
        f"{selected_race.get('race_no')}|{model_choice}|{weights_sig}"
    )


def _clear_smart_betting_runners_cache() -> None:
    st.session_state.pop("sb_scored_runners_key", None)
    st.session_state.pop("sb_scored_runners", None)


def _score_runners_for_parlay_race(
    race: Dict,
    model_choice: str,
    user_weights: Dict,
    weights_config: Optional[Dict] = None,
    ml_model=None,
    ml_model_type: Optional[str] = None,
    prediction_cutoff_date: Optional[str] = None,
    incident_llm_map: Optional[Dict[str, float]] = None,
) -> List[Dict]:
    """为过关/全天分析计算单场胜率（使用缓存出马表）。"""
    runners_data = get_cached_race_runners(
        race.get("race_date"), race.get("venue"), race.get("race_no")
    )
    if not runners_data:
        return []

    if incident_llm_map is None:
        incident_llm_map = _build_incident_llm_map(
            [r.get("incident", "") for r in runners_data if r.get("incident")]
        )

    if model_choice == "评分系统":
        if SCORING_ENGINE_OK:
            cfg = weights_config
            if cfg is None:
                cfg = (
                    st.session_state.get("user_scoring_config", {})
                    if st.session_state.get("scoring_weights_applied")
                    else _default_smart_betting_weights_config()
                )
            horse_ids = tuple({r.get("horse_id") for r in runners_data if r.get("horse_id")})
            perf_cache = se_get_horses_performances_batch(horse_ids)
            horse_birth_years = get_cached_horse_birth_years()
            return _finalize_parlay_runners(
                score_runners_for_prediction(
                    race.get("race_date"),
                    race.get("venue"),
                    race.get("distance", 1200),
                    runners_data,
                    perf_cache,
                    horse_birth_years,
                    cfg,
                    temperature=0.8,
                    incident_llm_map=incident_llm_map,
                )
            )

        scores, _ = calculate_all_horses_scores_v2(runners_data, user_weights)
        for i, runner in enumerate(runners_data):
            if i < len(scores):
                runner["overall_score"] = scores[i].get("overall_score", 0)
                runner["win_probability"] = scores[i].get("win_probability", 0) / 100
        return _finalize_parlay_runners(runners_data)

    if ml_model is None:
        ml_model_type, ml_model = get_smart_betting_ml_model(model_choice, prediction_cutoff_date)
    if ml_model is None:
        for runner in runners_data:
            runner["win_probability"] = 0.34
            runner["overall_score"] = 34
        return _finalize_parlay_runners(runners_data)

    ml_probs = get_model_predictions(
        race.get("race_date"),
        race.get("venue"),
        race.get("race_no"),
        runners_data,
        ml_model_type,
        ml_model,
        incident_llm_map=incident_llm_map,
    )
    for i, runner in enumerate(runners_data):
        if i < len(ml_probs):
            runner["win_probability"] = ml_probs[i]
            runner["overall_score"] = ml_probs[i] * 100
    return _finalize_parlay_runners(runners_data)


def _pack_parlay_race_entry(race: Dict, runners_data: List[Dict]) -> Dict:
    sorted_runners = sorted(runners_data, key=lambda x: x.get("win_probability", 0), reverse=True)
    scores = [runner.get("combined_score", runner.get("overall_score", 50)) for runner in sorted_runners]
    horse_names = [resolve_horse_name(_runner_record(runner)) for runner in sorted_runners]
    horse_nos = [runner.get("horse_no") for runner in sorted_runners]
    odds = []
    for runner in sorted_runners:
        odds_raw = runner.get("odds_win")
        try:
            odds.append(float(odds_raw) if odds_raw else 0)
        except (TypeError, ValueError):
            odds.append(0)
    win_probs = []
    for runner in sorted_runners:
        prob_raw = runner.get("win_probability")
        try:
            prob_val = float(prob_raw) if prob_raw is not None else 0.0
        except (TypeError, ValueError):
            prob_val = 0.0
        win_probs.append(round(prob_val * 100, 2) if prob_val <= 1 else round(prob_val, 2))
    return {
        "race_date": race.get("race_date"),
        "race_no": race.get("race_no"),
        "venue": race.get("venue"),
        "scores": scores,
        "horse_names": horse_names,
        "horse_nos": horse_nos,
        "win_probs": win_probs,
        "odds": odds,
    }


def _build_parlay_races_data(
    races_list: List[Dict],
    selected_indices: List[int],
    model_choice: str,
    user_weights: Dict,
    weights_config: Optional[Dict] = None,
    prediction_cutoff_date: Optional[str] = None,
) -> List[Dict]:
    """仅在用户点击生成过关时调用，避免每次 rerun 重复计算。"""
    ml_model = None
    ml_model_type = None
    if model_choice != "评分系统":
        ml_model_type, ml_model = get_smart_betting_ml_model(model_choice, prediction_cutoff_date)

    parlay_races_data = []
    sorted_indices = sorted(
        selected_indices,
        key=lambda i: races_list[i].get("race_no", 0),
    )
    for idx in sorted_indices:
        race = races_list[idx]
        runners_data = _score_runners_for_parlay_race(
            race,
            model_choice,
            user_weights,
            weights_config,
            ml_model,
            ml_model_type,
            prediction_cutoff_date,
        )
        if runners_data:
            parlay_races_data.append(_pack_parlay_race_entry(race, runners_data))
    return parlay_races_data


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_race_pool_odds(race_date: str, race_no: int) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    return (
        get_odds_qin_from_db(race_date, race_no),
        get_odds_tri_from_db(race_date, race_no),
        get_odds_tce_from_db(race_date, race_no),
    )


def _generate_parlay_combo_results(
    confidence_horses: List[Dict],
    bankroll: float,
    risk_multiplier: float,
) -> List[Dict]:
    """
    生成 2串1 / 3串1 过关组合。
    3串1 选取三场各一匹马，要求联合期望值 EV > 0。
    """
    texts = t()
    col_combo = texts["parlay_col_combo"]
    col_races = texts["parlay_col_races"]
    col_horses = texts["parlay_col_horses"]
    col_odds = texts["parlay_col_odds"]
    col_prob = texts["parlay_col_joint_prob"]
    col_stake = texts["parlay_col_stake"]
    results: List[Dict] = []
    n = len(confidence_horses)

    for i in range(n):
        for j in range(i + 1, n):
            h1, h2 = confidence_horses[i], confidence_horses[j]
            prob1 = float(h1.get("probability") or 0)
            prob2 = float(h2.get("probability") or 0)
            odds1 = float(h1.get("odds") or 0)
            odds2 = float(h2.get("odds") or 0)
            joint_prob = prob1 * prob2
            combined_odds = odds1 * odds2 if odds1 > 0 and odds2 > 0 else 0
            ev = joint_prob * combined_odds - 1 if combined_odds > 0 else -1
            if ev > 0:
                results.append({
                    col_combo: texts["parlay_combo_2x1"],
                    col_races: texts["parlay_races_2"].format(r1=h1["race_no"], r2=h2["race_no"]),
                    col_horses: f"{h1['display_name']} + {h2['display_name']}",
                    col_odds: f"{combined_odds:.1f}",
                    col_prob: f"{joint_prob * 100:.1f}%",
                    col_stake: f"HK${bankroll * 0.05 * risk_multiplier:.0f}",
                    "_ev": ev,
                })

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                h1, h2, h3 = confidence_horses[i], confidence_horses[j], confidence_horses[k]
                prob1 = float(h1.get("probability") or 0)
                prob2 = float(h2.get("probability") or 0)
                prob3 = float(h3.get("probability") or 0)
                odds1 = float(h1.get("odds") or 0)
                odds2 = float(h2.get("odds") or 0)
                odds3 = float(h3.get("odds") or 0)
                joint_prob = prob1 * prob2 * prob3
                combined_odds = odds1 * odds2 * odds3 if min(odds1, odds2, odds3) > 0 else 0
                ev = joint_prob * combined_odds - 1 if combined_odds > 0 else -1
                if ev > 0:
                    results.append({
                        col_combo: texts["parlay_combo_3x1"],
                        col_races: texts["parlay_races_3"].format(
                            r1=h1["race_no"], r2=h2["race_no"], r3=h3["race_no"]
                        ),
                        col_horses: (
                            f"{h1['display_name']} + {h2['display_name']} + {h3['display_name']}"
                        ),
                        col_odds: f"{combined_odds:.1f}",
                        col_prob: f"{joint_prob * 100:.1f}%",
                        col_stake: f"HK${bankroll * 0.03 * risk_multiplier:.0f}",
                        "_ev": ev,
                    })

    results.sort(key=lambda x: x.get("_ev", 0), reverse=True)
    for item in results:
        item.pop("_ev", None)
    return results

def _parlay_schedule_cache_key(
    selected_indices: List[int],
    model_choice: str,
    selected_date: str,
    prediction_cutoff_date: Optional[str],
) -> Tuple:
    return (tuple(selected_indices), model_choice, selected_date, prediction_cutoff_date or "live")


def _compute_parlay_schedule_results(
    parlay_races_data: List[Dict],
    max_legs: int,
) -> Tuple[Dict, ParlayRecommender]:
    """计算过关推荐：优先给出最优 2串1/3串1，并补充其他过关方式。"""
    recommender = ParlayRecommender()
    results = recommender.build_optimal_parlay_results(parlay_races_data, max_legs=max_legs)
    extra = recommender.get_parlay_recommendations_for_schedule(
        races_data=parlay_races_data,
        max_legs=max_legs,
        top_parlay_types=["2x3", "3x4", "3x7", "4x11"],
    )
    for key, recs in extra.items():
        if key not in results:
            results[key] = recs
    return results, recommender


def _display_parlay_schedule_results(results: Dict, recommender: ParlayRecommender) -> None:
    if not results:
        st.warning(t()["no_parlay_combo_found"])
        return

    texts = t()
    lang = get_lang()
    st.markdown(f"#### {texts['parlay_results_title']}")
    display_order = ["2x1", "3x1", "2x3", "3x4", "3x7", "4x11", "4x1", "5x1", "6x1"]
    shown_types = [t for t in display_order if t in results] + [
        t for t in results.keys() if t not in display_order
    ]

    best_rec = None
    best_ev = -999.0
    for parlay_type in shown_types:
        recommendations = results.get(parlay_type) or []
        if not recommendations:
            continue
        st.markdown(f"**{describe_parlay_type(parlay_type, lang)}**")
        for rec in recommendations[:3]:
            if rec.ev > best_ev:
                best_ev = rec.ev
                best_rec = rec
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**{format_parlay_display(rec, lang=lang)}**")
                with col2:
                    st.markdown(f"{texts['parlay_odds_label']}: **{rec.total_odds:.1f}**x")
                    st.markdown(f"{texts['parlay_combined_prob']}: {rec.combined_prob:.1f}%")
                with col3:
                    risk_color = "🟢" if rec.risk_level in ("低", "Low") else "🟡" if rec.risk_level in ("中", "Medium") else "🔴"
                    st.markdown(f"{texts['parlay_risk_label']}: {risk_color} {format_risk_level(rec.risk_level)}")
                    st.markdown(f"{texts['parlay_expected_roi']}: {rec.roi:+.1f}%")
            st.caption(
                f"{texts['parlay_suggested_bet']}: {describe_parlay_type(parlay_type, lang)} "
                f"({rec.num_bets} {tx('注', 'bets')}, {tx('共', 'total')} ${rec.total_stake:.0f})"
            )

    if best_rec:
        st.markdown("---")
        st.markdown(f"#### {texts['parlay_best_title']}")
        st.success(
            f"**{texts['parlay_best_combo']}**: {format_parlay_display(best_rec, lang=lang)}\n"
            f"- {texts['parlay_method']}: {describe_parlay_type(best_rec.parlay_type, lang)} "
            f"({best_rec.num_bets} {tx('注', 'bets')})\n"
            f"- {texts['parlay_total_odds']}: {best_rec.total_odds:.1f}x\n"
            f"- {texts['parlay_expected_roi']}: {best_rec.roi:+.1f}%\n"
            f"- {texts['parlay_suggest_stake']}: ${best_rec.total_stake:.0f}"
        )

# ==================== 智能投注：连赢/单T 展示辅助 ====================
def _horse_display_label(runner: Dict) -> str:
    from betting_strategy_engine import format_horse_display
    return format_horse_display(
        resolve_horse_name(_runner_record(runner)),
        runner.get("horse_no"),
    )


ODDS_KEY_MINUTES = [
    90, 80, 70, 60, 50, 45, 40, 35, 30, 27, 24, 21,
    18, 15, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0,
]


@st.cache_data(ttl=300, show_spinner=False)
def _query_odds_history_rows(race_date: str, venue: Optional[str], race_no: int) -> List[Dict]:
    if not SUPABASE_URL or not race_date:
        return []
    try:
        headers = get_supabase_headers(use_secret=True)
        url = (
            f"{SUPABASE_URL}/rest/v1/odds_history"
            f"?race_date=eq.{race_date}&race_no=eq.{race_no}"
            f"&odds_type=in.(WIN,PLA)"
            f"&select=horse_no,odds_type,odds_value,recorded_at,minutes_before_race,venue"
            f"&order=minutes_before_race.desc"
            f"&limit=5000"
        )
        if venue:
            url += f"&venue=eq.{venue}"
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"odds_history query failed: {response.status_code} venue={venue}")
            return []
        return response.json() or []
    except Exception as exc:
        print(f"_query_odds_history_rows failed: {exc}")
        return []


def _clean_odds_history_rows(rows: List[Dict]) -> List[Dict]:
    cleaned: List[Dict] = []
    for row in rows:
        try:
            odds_val = float(row.get("odds_value") or 0)
        except (TypeError, ValueError):
            continue
        if odds_val <= 0:
            continue
        hno = row.get("horse_no")
        if hno in (None, "", 0, "0"):
            continue
        cleaned.append(
            {
                "horse_no": str(hno).strip(),
                "odds_type": row.get("odds_type"),
                "odds_value": odds_val,
                "recorded_at": row.get("recorded_at"),
                "minutes_before_race": row.get("minutes_before_race"),
                "venue": row.get("venue"),
            }
        )
    return cleaned


@st.cache_data(ttl=300, show_spinner=False)
def fetch_race_odds_history(race_date: str, venue: str, race_no: int) -> List[Dict]:
    """Fetch WIN/PLA odds time series from odds_history (with venue fallback)."""
    race_no = int(race_no)
    venue = (venue or "ST").strip()

    rows = _clean_odds_history_rows(_query_odds_history_rows(race_date, venue, race_no))
    if rows:
        return rows

    for alt in ("ST", "HV"):
        if alt != venue:
            rows = _clean_odds_history_rows(_query_odds_history_rows(race_date, alt, race_no))
            if rows:
                return rows

    return _clean_odds_history_rows(_query_odds_history_rows(race_date, None, race_no))


def _odds_rows_for_pool(rows: List[Dict], odds_type: str) -> List[Dict]:
    return [r for r in rows if r.get("odds_type") == odds_type]


def _dedupe_odds_snapshots(pool_rows: List[Dict]) -> List[Dict]:
    """Keep one row per horse per minutes_before_race (latest recorded_at)."""
    best: Dict[Tuple[str, int], Dict] = {}
    for row in pool_rows:
        mins = row.get("minutes_before_race")
        if mins is None:
            continue
        try:
            mins_key = int(mins)
        except (TypeError, ValueError):
            continue
        key = (row.get("horse_no"), mins_key)
        prev = best.get(key)
        if prev is None or (row.get("recorded_at") or "") >= (prev.get("recorded_at") or ""):
            best[key] = row
    return list(best.values())


def _latest_odds_by_horse_from_history(rows: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Each horse_no -> {WIN, PLA} using the snapshot closest to post time."""
    latest: Dict[str, Dict[str, float]] = {}
    for pool in ("WIN", "PLA"):
        deduped = _dedupe_odds_snapshots(_odds_rows_for_pool(rows, pool))
        by_horse: Dict[str, List[Dict]] = {}
        for row in deduped:
            hno = str(row.get("horse_no", "")).strip()
            if hno:
                by_horse.setdefault(hno, []).append(row)
        for hno, snaps in by_horse.items():
            snaps.sort(key=lambda x: x.get("minutes_before_race", 0), reverse=True)
            try:
                val = float(snaps[-1].get("odds_value", 0))
            except (TypeError, ValueError):
                continue
            if val > 0:
                latest.setdefault(hno, {})[pool] = val
    return latest


def _merge_runners_with_odds_history(
    runners: List[Dict],
    odds_rows: List[Dict],
) -> List[Dict]:
    """Overlay latest WIN/PLA from odds_history (same source as realtime odds analysis)."""
    if not runners or not odds_rows:
        return runners
    latest = _latest_odds_by_horse_from_history(odds_rows)
    if not latest:
        return runners
    merged: List[Dict] = []
    for runner in runners:
        row = dict(runner)
        hno = str(row.get("horse_no", "")).strip()
        pool_odds = latest.get(hno, {})
        win_val = pool_odds.get("WIN")
        pla_val = pool_odds.get("PLA")
        if win_val and win_val > 0:
            row["odds_win"] = win_val
        if pla_val and pla_val > 0:
            row["odds_place"] = pla_val
        merged.append(row)
    return merged


def _parse_runner_table_odds(val) -> Optional[float]:
    try:
        if val is None or val == "-":
            return None
        parsed = float(val)
        return parsed if parsed > 0 else None
    except (ValueError, TypeError):
        return None


def _style_runner_table_min_odds(
    df: pd.DataFrame,
    win_col: str,
    place_col: str,
):
    """独赢/位置最低赔率标红加粗（可有多匹并列）。"""
    win_vals = [_parse_runner_table_odds(v) for v in df.get(win_col, [])]
    place_vals = [_parse_runner_table_odds(v) for v in df.get(place_col, [])]
    valid_win = [v for v in win_vals if v is not None]
    valid_place = [v for v in place_vals if v is not None]
    min_win = min(valid_win) if valid_win else None
    min_place = min(valid_place) if valid_place else None

    def _style_column(series: pd.Series) -> List[str]:
        col = series.name
        styles: List[str] = []
        for val in series:
            parsed = _parse_runner_table_odds(val)
            if parsed is not None:
                if col == win_col and min_win is not None and round(parsed, 1) == round(min_win, 1):
                    styles.append("color: #e60000; font-weight: bold")
                    continue
                if col == place_col and min_place is not None and round(parsed, 1) == round(min_place, 1):
                    styles.append("color: #e60000; font-weight: bold")
                    continue
            styles.append("")
        return styles

    return df.style.apply(_style_column, axis=0)


def _build_odds_summary_table(
    pool_rows: List[Dict],
    runners: List[Dict],
) -> pd.DataFrame:
    texts = t()
    deduped = _dedupe_odds_snapshots(pool_rows)
    by_horse: Dict[str, List[Dict]] = {}
    for row in deduped:
        by_horse.setdefault(row["horse_no"], []).append(row)

    name_map = {str(r.get("horse_no")): _horse_display_label(r) for r in runners}
    table_rows = []
    horse_order = [str(r.get("horse_no")) for r in runners if r.get("horse_no") is not None]
    extra_horses = sorted(set(by_horse.keys()) - set(horse_order), key=lambda x: int(x) if x.isdigit() else 999)
    for hno in horse_order + extra_horses:
        snaps = by_horse.get(hno, [])
        if not snaps:
            continue
        snaps.sort(key=lambda x: x.get("minutes_before_race", 0), reverse=True)
        opening = snaps[0]
        latest = snaps[-1]
        open_val = float(opening.get("odds_value", 0))
        latest_val = float(latest.get("odds_value", 0))
        change = latest_val - open_val if open_val > 0 else 0.0
        table_rows.append(
            {
                texts["horse_no"]: hno,
                texts["horse_name"]: name_map.get(hno, hno),
                texts["realtime_odds_opening"]: f"{open_val:.1f}",
                texts["realtime_odds_latest_val"]: f"{latest_val:.1f}",
                texts["realtime_odds_change"]: f"{change:+.1f}",
                texts["realtime_odds_snapshots"]: len(snaps),
            }
        )
    return pd.DataFrame(table_rows)


def _build_odds_trend_figure(pool_rows: List[Dict], runners: List[Dict], odds_type: str) -> go.Figure:
    texts = t()
    deduped = _dedupe_odds_snapshots(pool_rows)
    name_map = {str(r.get("horse_no")): _horse_display_label(r) for r in runners}
    fig = go.Figure()
    for hno in sorted({r["horse_no"] for r in deduped}, key=lambda x: int(x) if x.isdigit() else 999):
        horse_rows = [r for r in deduped if r["horse_no"] == hno]
        horse_rows.sort(key=lambda x: x.get("minutes_before_race", 0), reverse=True)
        if not horse_rows:
            continue
        fig.add_trace(
            go.Scatter(
                x=[r.get("minutes_before_race") for r in horse_rows],
                y=[r.get("odds_value") for r in horse_rows],
                mode="lines+markers",
                name=name_map.get(hno, f"#{hno}"),
                hovertemplate=(
                    f"{texts['horse_no']} {hno}<br>"
                    f"{texts['realtime_odds_min_before']}: %{{x}}<br>"
                    f"{texts['win_odds' if odds_type == 'WIN' else 'place_odds']}: %{{y:.1f}}<extra></extra>"
                ),
            )
        )
    y_label = texts["win_odds"] if odds_type == "WIN" else texts["place_odds"]
    fig.update_layout(
        title=texts["realtime_odds_trend"],
        xaxis_title=texts["realtime_odds_min_before"],
        yaxis_title=y_label,
        xaxis=dict(autorange="reversed"),
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _render_odds_detail_table(pool_rows: List[Dict], runners: List[Dict], odds_type: str, key_prefix: str) -> None:
    texts = t()
    deduped = _dedupe_odds_snapshots(pool_rows)
    name_map = {str(r.get("horse_no")): _horse_display_label(r) for r in runners}
    horse_options = [str(r.get("horse_no")) for r in runners if r.get("horse_no") is not None]
    if not horse_options:
        horse_options = sorted({r["horse_no"] for r in deduped}, key=lambda x: int(x) if x.isdigit() else 999)
    if not horse_options:
        return

    selected_hno = st.selectbox(
        texts["horse_name"],
        options=horse_options,
        format_func=lambda h: name_map.get(str(h), str(h)),
        key=f"{key_prefix}_horse_detail",
    )
    horse_rows = [r for r in deduped if r["horse_no"] == str(selected_hno)]
    horse_rows.sort(key=lambda x: x.get("minutes_before_race", 0), reverse=True)
    detail_rows = []
    for row in horse_rows:
        recorded = row.get("recorded_at") or ""
        if recorded:
            recorded = recorded[:16].replace("T", " ")
        detail_rows.append(
            {
                texts["realtime_odds_min_before"]: row.get("minutes_before_race"),
                texts["win_odds" if odds_type == "WIN" else "place_odds"]: f"{row.get('odds_value', 0):.1f}",
                texts["realtime_odds_recorded_at"]: recorded or "-",
            }
        )
    if detail_rows:
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)


def _odds_analysis_heading(selected_race: Dict, selected_date: str) -> str:
    race_date = selected_race.get("race_date") or selected_date
    race_no = selected_race.get("race_no", "-")
    venue_label = _venue_display_label(selected_race)
    return tx(
        f"📈 實時賠率分析（{race_date} 第{race_no}場 {venue_label}）",
        f"📈 Real-time Odds Analysis ({race_date} R{race_no} {venue_label})",
    )


def _format_collect_error_message(result: Dict) -> str:
    reason = (result.get("reason") or result.get("error") or "").strip()
    raw = result.get("rawMinutes")
    raw_text = f"{raw:.0f}" if isinstance(raw, (int, float)) else ""

    if reason == "outside_key_window":
        return tx(
            f"距開賽约 {raw_text} 分钟，尚未进入自动采集窗口（开赛前 98 分钟内）。"
            "请点「立即採集」强制保存当前快照，或稍后再试。",
            f"About {raw_text} min to post; auto-collect runs within 98 min of post time. "
            "Use Collect now to force-save current odds, or try again later.",
        )
    if reason == "no_odds_data":
        return tx("HKJC 尚未提供本场 WIN/PLA 赔率。", "HKJC WIN/PLA odds not available yet.")
    if reason:
        return reason
    if result.get("error"):
        return str(result["error"])
    return tx("未知错误，请确认 Render API 已部署最新版本。", "Unknown error; ensure Render API is up to date.")


def _run_odds_snapshot_collect(
    race_date: str,
    venue: str,
    race_no: int,
    *,
    show_success: bool = True,
    force: bool = False,
) -> List[Dict]:
    """调用 Node API 采集 WIN/PLA 快照并刷新 odds_history 缓存。"""
    collect_result = trigger_odds_collection_for_race(race_date, venue, int(race_no), force=force)
    fetch_race_odds_history.clear()
    _query_odds_history_rows.clear()
    rows = fetch_race_odds_history(race_date, venue, int(race_no))
    if show_success and collect_result.get("success") and rows:
        saved = collect_result.get("saved") or 0
        key_min = collect_result.get("keyMinute")
        if saved > 0 and key_min is not None:
            st.success(
                tx(
                    f"已採集 T-{key_min} 賠率快照（{saved} 条）",
                    f"Collected T-{key_min} snapshots ({saved} rows)",
                )
            )
        elif rows:
            st.info(tx("已有赔率走勢数据（本次未新增快照）。", "Trend data loaded (no new snapshots this run)."))
    elif show_success and not collect_result.get("success"):
        st.warning(
            tx(
                f"採集未成功：{_format_collect_error_message(collect_result)}",
                f"Collection failed: {_format_collect_error_message(collect_result)}",
            )
        )
    return rows


def _render_odds_detail_section(
    pool_rows: List[Dict],
    runners: List[Dict],
    odds_type: str,
    odds_label_key: str,
    state_key: str,
    trial_key: str,
) -> None:
    texts = t()

    def _body() -> None:
        _render_odds_detail_table(pool_rows, runners, odds_type, odds_label_key)

    render_collapsible_trial_section(
        texts["realtime_odds_detail"],
        state_key,
        trial_key,
        _body,
        expand_label=texts["realtime_odds_detail"],
        use_heading=False,
    )


def _load_realtime_odds_rows(
    race_ui_key: str,
    race_date: str,
    venue: str,
    race_no: int,
) -> List[Dict]:
    """加载赔率走勢；首次自动采集后缓存，折起再开无需重复请求。"""
    cache_key = f"odds_rows_cache_{race_ui_key}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    rows = fetch_race_odds_history(race_date, venue, race_no)
    if not rows:
        auto_collect_key = f"auto_odds_collect_{race_ui_key}"
        if not st.session_state.get(auto_collect_key):
            st.session_state[auto_collect_key] = True
            with st.spinner(tx("正在自動採集賠率快照...", "Auto-collecting odds snapshots...")):
                rows = _run_odds_snapshot_collect(race_date, venue, race_no, show_success=True)

    st.session_state[cache_key] = rows
    return rows


def _render_realtime_odds_body(
    selected_race: Dict,
    sorted_runners: List[Dict],
    selected_date: str,
    race_ui_key: str,
    odds_rows: Optional[List[Dict]] = None,
) -> None:
    texts = t()
    race_date = selected_race.get("race_date") or selected_date
    venue = selected_race.get("venue", "ST")
    race_no = int(selected_race.get("race_no"))
    cache_key = f"odds_rows_cache_{race_ui_key}"

    rows = odds_rows if odds_rows is not None else _load_realtime_odds_rows(
        race_ui_key, race_date, venue, race_no
    )
    unique_mins = len(
        {
            r.get("minutes_before_race")
            for r in _dedupe_odds_snapshots(rows)
            if r.get("minutes_before_race") is not None
        }
    ) if rows else 0

    st.caption(
        tx(
            f"已加载 {unique_mins} 个时间点走勢快照（目标约 26 个，开赛前 98 分钟内自动采集）",
            f"Loaded {unique_mins} trend snapshots (target ~26; auto-collect within 98 min of post time)",
        )
    )

    def _manual_collect() -> None:
        st.session_state[f"manual_collect_pending_{race_ui_key}"] = True

    st.button(
        tx("🔄 立即採集賠率快照", "🔄 Collect odds snapshots now"),
        key=f"manual_collect_odds_{race_ui_key}",
        use_container_width=True,
        on_click=_manual_collect,
    )
    if st.session_state.pop(f"manual_collect_pending_{race_ui_key}", False):
        with st.spinner(tx("正在採集賠率快照...", "Collecting odds snapshots...")):
            rows = _run_odds_snapshot_collect(race_date, venue, race_no, force=True)
            st.session_state[cache_key] = rows

    if not rows:
        st.info(texts["realtime_odds_no_data"])
        st.caption(
            tx(
                "提示：请先点上方「立即採集」或「刷新单场数据」；走勢仅记录开赛前约 98 分钟内的 WIN/PLA 快照。",
                "Tip: use Collect above or Refresh single race; trends need snapshots within ~98 min of post time.",
            )
        )
        return

    win_rows = _odds_rows_for_pool(rows, "WIN")
    pla_rows = _odds_rows_for_pool(rows, "PLA")
    unique_mins = len(
        {
            r.get("minutes_before_race")
            for r in _dedupe_odds_snapshots(rows)
            if r.get("minutes_before_race") is not None
        }
    )
    st.caption(texts["realtime_odds_points"].format(count=unique_mins))

    tab_win, tab_pla = st.tabs([texts["win_odds"], texts["place_odds"]])
    with tab_win:
        if not win_rows:
            st.info(texts["realtime_odds_no_data"])
        else:
            st.markdown(f"**{texts['realtime_odds_latest']}**")
            summary = _build_odds_summary_table(win_rows, sorted_runners)
            if not summary.empty:
                st.dataframe(summary, use_container_width=True, hide_index=True)
            st.plotly_chart(_build_odds_trend_figure(win_rows, sorted_runners, "WIN"), use_container_width=True)
            _render_odds_detail_section(
                win_rows,
                sorted_runners,
                "WIN",
                "win_odds",
                f"show_odds_win_detail_{race_ui_key}",
                f"odds_win_detail:{race_ui_key}",
            )

    with tab_pla:
        if not pla_rows:
            st.info(texts["realtime_odds_no_data"])
        else:
            st.markdown(f"**{texts['realtime_odds_latest']}**")
            summary = _build_odds_summary_table(pla_rows, sorted_runners)
            if not summary.empty:
                st.dataframe(summary, use_container_width=True, hide_index=True)
            st.plotly_chart(_build_odds_trend_figure(pla_rows, sorted_runners, "PLA"), use_container_width=True)
            _render_odds_detail_section(
                pla_rows,
                sorted_runners,
                "PLA",
                "pla_odds",
                f"show_odds_pla_detail_{race_ui_key}",
                f"odds_pla_detail:{race_ui_key}",
            )


def _render_realtime_odds_analysis(
    selected_race: Dict,
    sorted_runners: List[Dict],
    selected_date: str,
    race_ui_key: str,
    odds_rows: Optional[List[Dict]] = None,
) -> None:
    """Smart betting: odds_history snapshots (WIN/PLA) below runner table."""
    heading = _odds_analysis_heading(selected_race, selected_date)
    odds_state_key = f"show_odds_analysis_{race_ui_key}"
    texts = t()

    render_collapsible_trial_section(
        heading,
        odds_state_key,
        f"odds_analysis:{race_ui_key}",
        lambda: _render_realtime_odds_body(
            selected_race, sorted_runners, selected_date, race_ui_key, odds_rows
        ),
        expand_label=texts["realtime_odds_expand"],
    )


def _backtest_horse_label(name: str, horse_no=None, record: Optional[Dict] = None) -> str:
    from betting_strategy_engine import format_horse_display
    if record:
        display_name = resolve_horse_name(record)
    elif not name:
        return "-"
    else:
        display_name = resolve_horse_name({"horse_name": name})
    return format_horse_display(display_name, horse_no)


def _runner_backtest_label(runner: Optional[Dict]) -> str:
    if not runner:
        return "-"
    return _backtest_horse_label(
        runner.get("horse_name", ""),
        runner.get("horse_no"),
        record=runner,
    )


def _render_qin_suggestions(sorted_runners: List[Dict], key_prefix: str = "qin") -> None:
    """連贏組合推薦（展開即顯示，無二次扣費）"""
    if len(sorted_runners) < 2:
        st.warning(t()["qin_insufficient_horses"])
        return

    top_n = min(5, len(sorted_runners))
    top_runners = sorted_runners[:top_n]
    combinations = []
    for i in range(len(top_runners)):
        for j in range(i + 1, len(top_runners)):
            h1, h2 = top_runners[i], top_runners[j]
            odds1 = float(h1.get("odds_win") or 0)
            odds2 = float(h2.get("odds_win") or 0)
            estimated_odds = (odds1 * odds2) / 2 if odds1 > 0 and odds2 > 0 else 0
            prob1 = float(h1.get("win_probability") or 0)
            prob2 = float(h2.get("win_probability") or 0)
            joint_prob = prob1 * prob2 * 2
            ev = joint_prob * estimated_odds - 1 if estimated_odds > 0 else -1
            combinations.append(
                {
                    "name": f"{_horse_display_label(h1)} + {_horse_display_label(h2)}",
                    "odds": estimated_odds,
                    "ev": ev,
                    "recommended": ev > 0.15,
                }
            )

    combinations.sort(key=lambda x: x["ev"], reverse=True)
    top_combos = combinations[:5]
    if not top_combos:
        st.info(t()["no_qin_combos"])
        return

    if all(c["odds"] <= 0 for c in top_combos):
        st.caption(t()["missing_win_odds_hint"])

    selected = []
    for idx, combo in enumerate(top_combos):
        col1, col2, col3, col4 = st.columns([2.5, 1.2, 1.2, 1])
        with col1:
            st.write(f"**{combo['name']}**")
        with col2:
            st.write(f"{t()['odds_label']}: {combo['odds']:.1f}x" if combo["odds"] > 0 else f"{t()['odds_label']}: {t()['odds_estimated_label']}")
        with col3:
            ev_color = "🟢" if combo["ev"] > 0.15 else "🟡" if combo["ev"] > 0 else "🔴"
            st.write(f"{ev_color} EV: {combo['ev']:+.2f}")
        with col4:
            if st.checkbox(t()["select_label"], key=f"{key_prefix}_pick_{idx}", value=combo["recommended"]):
                selected.append(combo)
        st.markdown("---")

    if selected:
        total_stake = len(selected) * 20
        st.success(t()["qin_selected_summary"].format(count=len(selected), stake=total_stake))
    else:
        st.info(t()["select_combos_hint"])


def _render_tri_suggestions(sorted_runners: List[Dict]) -> None:
    """單T 推薦（展開即顯示）"""
    if len(sorted_runners) < 3:
        st.warning(t()["tri_insufficient_horses"])
        return

    top3 = sorted_runners[:3]
    h1, h2, h3 = top3[0], top3[1], top3[2]
    odds1 = float(h1.get("odds_win") or 0)
    odds2 = float(h2.get("odds_win") or 0)
    odds3 = float(h3.get("odds_win") or 0)
    label = f"{_horse_display_label(h1)} + {_horse_display_label(h2)} + {_horse_display_label(h3)}"

    if odds1 > 0 and odds2 > 0 and odds3 > 0:
        estimated_odds = odds1 * odds2 * odds3 * 0.5
    else:
        estimated_odds = 0
        st.caption(t()["tri_missing_odds"])

    prob1 = float(h1.get("win_probability") or 0)
    prob2 = float(h2.get("win_probability") or 0)
    prob3 = float(h3.get("win_probability") or 0)
    joint_prob = prob1 * prob2 * prob3 * 6
    ev = joint_prob * estimated_odds - 1 if estimated_odds > 0 else -1
    texts = t()

    st.write(f"**{label}**")
    if estimated_odds > 0:
        st.write(texts["tri_est_odds"].format(odds=estimated_odds))
    else:
        st.write(texts["tri_est_odds_pending"])
    st.write(f"{texts['tri_joint_prob']}: {joint_prob * 100:.1f}%")
    st.write(f"{texts['tri_ev']}: {ev:+.2f}")
    if ev > 0.15:
        st.success(texts["tri_ev_recommend"])
    else:
        st.info(texts["tri_ev_skip"])


def _render_tce_suggestions(sorted_runners: List[Dict]) -> None:
    """三重彩 推薦（展開即顯示，順序固定）"""
    texts = t()
    if len(sorted_runners) < 3:
        st.warning(texts["tce_insufficient_horses"])
        return

    top3 = sorted_runners[:3]
    h1, h2, h3 = top3[0], top3[1], top3[2]
    label = f"{_horse_display_label(h1)} > {_horse_display_label(h2)} > {_horse_display_label(h3)}"

    odds1 = float(h1.get("odds_win") or 0)
    odds2 = float(h2.get("odds_win") or 0)
    odds3 = float(h3.get("odds_win") or 0)

    if odds1 > 0 and odds2 > 0 and odds3 > 0:
        base = odds1 * odds2 * odds3
        estimated_odds = max(base * 0.15, base * 0.08)
    else:
        estimated_odds = 0
        st.caption(texts["tce_missing_odds"])

    prob1 = float(h1.get("win_probability") or 0)
    prob2 = float(h2.get("win_probability") or 0)
    prob3 = float(h3.get("win_probability") or 0)
    joint_prob = prob1 * prob2 * prob3
    ev = joint_prob * estimated_odds - 1 if estimated_odds > 0 else -1

    st.caption(texts["tce_order_hint"])
    st.write(f"**{label}**")
    if estimated_odds > 0:
        st.write(texts["tce_est_odds"].format(odds=estimated_odds))
    else:
        st.write(texts["tce_est_odds_pending"])
    st.write(f"{texts['tce_joint_prob']}: {joint_prob * 100:.2f}%")
    st.write(f"{texts['tce_ev']}: {ev:+.2f}")
    if ev > 0.15:
        st.success(texts["tce_ev_recommend"])
    else:
        st.info(texts["tce_ev_skip"])


# ==================== 智能投注：评分权重面板（按需加载） ====================
def _render_smart_betting_weights_panel(lang: str) -> None:
    """仅在用户打开权重面板时渲染，避免拖慢单场分析首屏。"""
    st.markdown("### " + ("⚙️ 评分权重设置" if lang == "zh" else "⚙️ Rating Weights"))
    st.caption(
        "调整评分因子权重，仅对当前会话有效，退出后恢复默认值"
        if lang == "zh"
        else "Adjust rating weights, only valid for current session"
    )

    config = _load_scoring_config_user_defaults()

    if config is None:
        default_level1 = {"basic": 0.30, "race": 0.35, "odds": 0.20, "status": 0.15}
        default_basic = {"win_rate_3": 0.20, "win_rate_10": 0.20, "place_rate_10": 0.15, "show_rate_10": 0.15, "distance_rating": 0.15, "trend": 0.15}
        default_race = {"same_course": 0.25, "same_distance": 0.25, "draw": 0.15, "weight": 0.10, "jockey": 0.15, "trainer": 0.10}
        default_odds = {"win_odds": 0.60, "odds_trend": 0.40}
        default_status = {"age": 0.30, "weight_change": 0.25, "incident": 0.25, "burst": 0.20}
    else:
        default_level1 = config.get("level1_weights", {"basic": 0.30, "race": 0.35, "odds": 0.20, "status": 0.15})
        default_basic = config.get("basic_weights", {"win_rate_3": 0.20, "win_rate_10": 0.20, "place_rate_10": 0.15, "show_rate_10": 0.15, "distance_rating": 0.15, "trend": 0.15})
        default_race = config.get("race_weights", {"same_course": 0.25, "same_distance": 0.25, "draw": 0.15, "weight": 0.10, "jockey": 0.15, "trainer": 0.10})
        default_odds = config.get("odds_weights", {"win_odds": 0.60, "odds_trend": 0.40})
        default_status = config.get("status_weights", {"age": 0.30, "weight_change": 0.25, "incident": 0.25, "burst": 0.20})

    if "user_scoring_config" not in st.session_state:
        st.session_state.user_scoring_config = {
            "level1_weights": default_level1.copy(),
            "basic_weights": default_basic.copy(),
            "race_weights": default_race.copy(),
            "odds_weights": default_odds.copy(),
            "status_weights": default_status.copy(),
        }

    if "scoring_weights_applied" not in st.session_state:
        st.session_state.scoring_weights_applied = False

    user_level1 = st.session_state.user_scoring_config["level1_weights"].copy()
    user_basic = st.session_state.user_scoring_config["basic_weights"].copy()
    user_race = st.session_state.user_scoring_config["race_weights"].copy()
    user_odds = st.session_state.user_scoring_config["odds_weights"].copy()
    user_status = st.session_state.user_scoring_config["status_weights"].copy()

    st.markdown("**一级因子权重**" if lang == "zh" else "**Level 1 Weights**")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        basic_val = st.number_input(
            "基础往绩" if lang == "zh" else "Basic",
            min_value=0, max_value=100, value=int(user_level1.get("basic", 0.30) * 100),
            step=1, key="user_basic_weight",
        )
        user_level1["basic"] = basic_val / 100

    with col2:
        race_val = st.number_input(
            "场次因素" if lang == "zh" else "Race",
            min_value=0, max_value=100, value=int(user_level1.get("race", 0.35) * 100),
            step=1, key="user_race_weight",
        )
        user_level1["race"] = race_val / 100

    with col3:
        odds_val = st.number_input(
            "赔率因素" if lang == "zh" else "Odds",
            min_value=0, max_value=100, value=int(user_level1.get("odds", 0.20) * 100),
            step=1, key="user_odds_weight",
        )
        user_level1["odds"] = odds_val / 100

    with col4:
        status_val = st.number_input(
            "状态因素" if lang == "zh" else "Status",
            min_value=0, max_value=100, value=int(user_level1.get("status", 0.15) * 100),
            step=1, key="user_level1_status",
        )
        user_level1["status"] = status_val / 100

    total_level1 = sum(user_level1.values()) * 100
    if abs(total_level1 - 100) < 0.1:
        st.success(f"✅ 总和: {total_level1:.0f}%" if lang == "zh" else f"✅ Total: {total_level1:.0f}%")
    else:
        st.error(f"❌ 总和: {total_level1:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_level1:.0f}%, must be 100%")

    with st.expander("📈 基础往绩二级因子" if lang == "zh" else "📈 Basic Performance Sub-factors", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            win3 = st.number_input("近3场胜率" if lang == "zh" else "Win Rate (L3)", min_value=0, max_value=100, value=int(user_basic.get("win_rate_3", 0.20) * 100), step=1, key="user_win3")
            win10 = st.number_input("近10场胜率" if lang == "zh" else "Win Rate (L10)", min_value=0, max_value=100, value=int(user_basic.get("win_rate_10", 0.20) * 100), step=1, key="user_win10")
            place10 = st.number_input("近10场入Q率" if lang == "zh" else "Place Rate (L10)", min_value=0, max_value=100, value=int(user_basic.get("place_rate_10", 0.15) * 100), step=1, key="user_place10")
        with col2:
            show10 = st.number_input("近10场入T率" if lang == "zh" else "Show Rate (L10)", min_value=0, max_value=100, value=int(user_basic.get("show_rate_10", 0.15) * 100), step=1, key="user_show10")
            distance_rating = st.number_input("同程表现评分" if lang == "zh" else "Distance Rating", min_value=0, max_value=100, value=int(user_basic.get("distance_rating", 0.15) * 100), step=1, key="user_distance")
            trend = st.number_input("名次趋势" if lang == "zh" else "Ranking Trend", min_value=0, max_value=100, value=int(user_basic.get("trend", 0.15) * 100), step=1, key="user_trend")
        user_basic["win_rate_3"] = win3 / 100
        user_basic["win_rate_10"] = win10 / 100
        user_basic["place_rate_10"] = place10 / 100
        user_basic["show_rate_10"] = show10 / 100
        user_basic["distance_rating"] = distance_rating / 100
        user_basic["trend"] = trend / 100
        total_basic = sum(user_basic.values()) * 100
        if abs(total_basic - 100) < 0.1:
            st.success(f"✅ 总和: {total_basic:.0f}%" if lang == "zh" else f"✅ Total: {total_basic:.0f}%")
        else:
            st.error(f"❌ 总和: {total_basic:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_basic:.0f}%, must be 100%")

    with st.expander("🏟️ 场次因素二级因子" if lang == "zh" else "🏟️ Race Factors Sub-factors", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            same_course = st.number_input("同场地胜率" if lang == "zh" else "Same Course", min_value=0, max_value=100, value=int(user_race.get("same_course", 0.25) * 100), step=1, key="user_same_course")
            same_distance = st.number_input("同路程胜率" if lang == "zh" else "Same Distance", min_value=0, max_value=100, value=int(user_race.get("same_distance", 0.25) * 100), step=1, key="user_same_distance")
            draw = st.number_input("档位优势" if lang == "zh" else "Draw", min_value=0, max_value=100, value=int(user_race.get("draw", 0.15) * 100), step=1, key="user_draw")
        with col2:
            weight = st.number_input("负磅变化" if lang == "zh" else "Weight", min_value=0, max_value=100, value=int(user_race.get("weight", 0.10) * 100), step=1, key="user_weight")
            jockey = st.number_input("骑师配合" if lang == "zh" else "Jockey", min_value=0, max_value=100, value=int(user_race.get("jockey", 0.15) * 100), step=1, key="user_jockey")
            trainer = st.number_input("练马师状态" if lang == "zh" else "Trainer", min_value=0, max_value=100, value=int(user_race.get("trainer", 0.10) * 100), step=1, key="user_trainer")
        user_race["same_course"] = same_course / 100
        user_race["same_distance"] = same_distance / 100
        user_race["draw"] = draw / 100
        user_race["weight"] = weight / 100
        user_race["jockey"] = jockey / 100
        user_race["trainer"] = trainer / 100
        total_race = sum(user_race.values()) * 100
        if abs(total_race - 100) < 0.1:
            st.success(f"✅ 总和: {total_race:.0f}%" if lang == "zh" else f"✅ Total: {total_race:.0f}%")
        else:
            st.error(f"❌ 总和: {total_race:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_race:.0f}%, must be 100%")

    with st.expander("💰 赔率因素二级因子" if lang == "zh" else "💰 Odds Factors Sub-factors", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            win_odds = st.number_input("独赢赔率" if lang == "zh" else "Win Odds", min_value=0, max_value=100, value=int(user_odds.get("win_odds", 0.60) * 100), step=1, key="user_win_odds")
        with col2:
            odds_trend = st.number_input("赔率变动趋势" if lang == "zh" else "Odds Trend", min_value=0, max_value=100, value=int(user_odds.get("odds_trend", 0.40) * 100), step=1, key="user_odds_trend")
        user_odds["win_odds"] = win_odds / 100
        user_odds["odds_trend"] = odds_trend / 100
        total_odds = sum(user_odds.values()) * 100
        if abs(total_odds - 100) < 0.1:
            st.success(f"✅ 总和: {total_odds:.0f}%" if lang == "zh" else f"✅ Total: {total_odds:.0f}%")
        else:
            st.error(f"❌ 总和: {total_odds:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_odds:.0f}%, must be 100%")

    with st.expander("🩺 状态因素二级因子" if lang == "zh" else "🩺 Status Factors Sub-factors", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("马龄因子" if lang == "zh" else "Age", min_value=0, max_value=100, value=int(user_status.get("age", 0.30) * 100), step=1, key="user_age")
            weight_change = st.number_input("体重变化" if lang == "zh" else "Weight Change", min_value=0, max_value=100, value=int(user_status.get("weight_change", 0.25) * 100), step=1, key="user_status_weight_change")
        with col2:
            incident = st.number_input("事件报告" if lang == "zh" else "Incident", min_value=0, max_value=100, value=int(user_status.get("incident", 0.25) * 100), step=1, key="user_incident")
            burst = st.number_input("冲刺能力" if lang == "zh" else "Burst", min_value=0, max_value=100, value=int(user_status.get("burst", 0.20) * 100), step=1, key="user_burst")
        user_status["age"] = age / 100
        user_status["weight_change"] = weight_change / 100
        user_status["incident"] = incident / 100
        user_status["burst"] = burst / 100
        total_status = sum(user_status.values()) * 100
        if abs(total_status - 100) < 0.1:
            st.success(f"✅ 总和: {total_status:.0f}%" if lang == "zh" else f"✅ Total: {total_status:.0f}%")
        else:
            st.error(f"❌ 总和: {total_status:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_status:.0f}%, must be 100%")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("✅ 应用权重并刷新" if lang == "zh" else "✅ Apply & Refresh", type="primary", use_container_width=True):
            if abs(sum(user_level1.values()) - 1) > 0.01:
                st.error("一级因子总和必须为100%，请调整后重试" if lang == "zh" else "Level 1 weights must sum to 100%")
            elif abs(sum(user_basic.values()) - 1) > 0.01:
                st.error("基础往绩二级因子总和必须为100%，请调整后重试" if lang == "zh" else "Basic weights must sum to 100%")
            elif abs(sum(user_race.values()) - 1) > 0.01:
                st.error("场次因素二级因子总和必须为100%，请调整后重试" if lang == "zh" else "Race weights must sum to 100%")
            elif abs(sum(user_odds.values()) - 1) > 0.01:
                st.error("赔率因素二级因子总和必须为100%，请调整后重试" if lang == "zh" else "Odds weights must sum to 100%")
            elif abs(sum(user_status.values()) - 1) > 0.01:
                st.error("状态因素二级因子总和必须为100%，请调整后重试" if lang == "zh" else "Status weights must sum to 100%")
            elif not require_trial("weights_apply", dedupe=False):
                pass
            else:
                st.session_state.user_scoring_config = {
                    "level1_weights": user_level1,
                    "basic_weights": user_basic,
                    "race_weights": user_race,
                    "odds_weights": user_odds,
                    "status_weights": user_status,
                }
                st.session_state.scoring_weights_applied = True
                st.success("权重已应用，正在刷新数据..." if lang == "zh" else "Weights applied, refreshing...")
                _clear_smart_betting_runners_cache()
                se_get_horses_performances_batch.clear()
                get_cached_race_runners.clear()
                st.rerun()

    with col2:
        if st.button("🔄 恢复默认值" if lang == "zh" else "🔄 Reset to Default", use_container_width=True):
            st.session_state.user_scoring_config = {
                "level1_weights": default_level1.copy(),
                "basic_weights": default_basic.copy(),
                "race_weights": default_race.copy(),
                "odds_weights": default_odds.copy(),
                "status_weights": default_status.copy(),
            }
            st.session_state.scoring_weights_applied = False
            st.success("已恢复到默认权重" if lang == "zh" else "Reset to default weights")
            st.rerun()

    if st.session_state.scoring_weights_applied:
        st.info("✅ 当前使用自定义权重" if lang == "zh" else "✅ Currently using custom weights")
    else:
        st.info("📌 当前使用管理员默认权重" if lang == "zh" else "📌 Currently using admin default weights")
        st.caption("💡 修改后需点击「应用权重并刷新」才会生效" if lang == "zh" else "💡 Click 'Apply & Refresh' after modification to take effect")


# ==================== 智能投注主页面 ====================
def render_smart_betting(show_title: bool = True):
    """智能投注页面：单场分析 + 全天优化 + 过关组合"""
    import time
    perf_log = {}
    t0 = time.time()
#--------------------
    # ⭐ 初始化折叠状态（用于扣费控制）
    if "expand_win" not in st.session_state:
        st.session_state.expand_win = False
    if "expand_qin" not in st.session_state:
        st.session_state.expand_qin = False
    if "expand_tri" not in st.session_state:
        st.session_state.expand_tri = False
    if "expand_qin_recommend" not in st.session_state:
        st.session_state.expand_qin_recommend = False
    if "prev_selected_race" not in st.session_state:
        st.session_state.prev_selected_race = None
    if "prev_selected_date" not in st.session_state:
        st.session_state.prev_selected_date = None
    if "expand_parlay" not in st.session_state:
        st.session_state.expand_parlay = False
    if "expand_scoring_weights" not in st.session_state:
        st.session_state.expand_scoring_weights = False
    #-----------
    # 付费标记（每个场次独立，切换场次时重置）
    if "paid_win" not in st.session_state:
        st.session_state.paid_win = False
    if "paid_qin" not in st.session_state:
        st.session_state.paid_qin = False
    if "paid_tri" not in st.session_state:
        st.session_state.paid_tri = False
    if "paid_qin_recommend" not in st.session_state:
        st.session_state.paid_qin_recommend = False
    if "paid_parlay" not in st.session_state:
        st.session_state.paid_parlay = False
    if "paid_scoring_weights" not in st.session_state:
        st.session_state.paid_scoring_weights = False
    #------------------
    if show_title:
        st.markdown(f"## {t()['smart_betting']}")
    perf_log["初始化"] = time.time() - t0    
    #-------------
    # ==================== 用户设置（紧凑一行，避免折叠区仍执行拖慢首屏） ====================
    if "_sb_bankroll_default" not in st.session_state:
        profile = get_user_profile(st.session_state.user_id)
        st.session_state["_sb_bankroll_default"] = int(profile.get("default_bankroll", 1000))

    col1, col2, col3 = st.columns(3)

    with col1:
        bankroll = st.number_input(
            t()["betting_budget"],
            min_value=100,
            max_value=100000,
            value=int(st.session_state["_sb_bankroll_default"]),
            step=100,
            key="betting_bankroll",
        )

    with col2:
        risk_preference = st.selectbox(
            t()["risk_preference"],
            options=["conservative", "standard", "aggressive"],
            format_func=lambda x: {
                "conservative": t()["conservative"],
                "standard": t()["standard"],
                "aggressive": t()["aggressive"],
            }.get(x, t()["standard"]),
            key="risk_preference",
        )
        risk_multiplier = {
            "conservative": 0.5,
            "standard": 0.8,
            "aggressive": 1.0,
        }.get(risk_preference, 0.8)

    with col3:
        model_choice = st.selectbox(
            t()["ai_model"],
            options=MODEL_CHOICE_OPTIONS,
            index=1,
            format_func=display_model_choice,
            key="ml_model_choice",
            help=t()["model_select_help"],
        )
    #-----------------
    lang = st.session_state.get("lang", "zh")
    wbtn_col, wcap_col = st.columns([1.2, 3.8])
    with wbtn_col:
        _weights_panel_open = st.session_state.get("sb_show_weights_panel", False)
        if st.button(
            ("收起权重" if _weights_panel_open else "⚙️ 评分权重") if lang == "zh"
            else ("Hide weights" if _weights_panel_open else "⚙️ Rating Weights"),
            key="toggle_sb_weights_panel",
            use_container_width=True,
        ):
            st.session_state.sb_show_weights_panel = not _weights_panel_open
            st.rerun()
    with wcap_col:
        if st.session_state.get("scoring_weights_applied"):
            st.caption("✅ " + ("当前使用自定义权重" if lang == "zh" else "Using custom weights"))
    #------------------
    st.markdown("---")
    
    #-------    
    # ==================== 选择赛日 ====================
    st.markdown(f"### {t()['select_race_day']}")
    t1 = time.time()
    perf_log["选择赛日"] = t1 - t0
    
    # ⭐ 日期模式选择（简洁样式，无大框）
    st.caption(t()["date_mode_label"])
    date_mode = st.radio(
        t()["date_mode_label"],
        options=[DATE_MODE_FUTURE, DATE_MODE_HISTORY],
        format_func=_date_mode_label,
        index=0,
        horizontal=True,
        key="date_mode_select",
        label_visibility="collapsed",
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        refresh_schedule_btn = st.button(t()["refresh_schedule"], use_container_width=True)

    if refresh_schedule_btn:
        get_cached_upcoming_races.clear()
        get_cached_race_runners.clear()
        st.session_state["schedule_refresh_pending"] = True
        st.rerun()

    if st.session_state.pop("schedule_refresh_pending", False):
        with st.spinner(t()["syncing_schedule"]):
            try:
                api_races = get_upcoming_races_from_api(detailed=True)
                if not api_races:
                    api_races = get_upcoming_races_from_api(detailed=False)
                if api_races:
                    api_races = _enrich_upcoming_races_from_db(api_races)
                    sync_races_to_db(api_races)
                    st.session_state["upcoming_races_override"] = api_races
                    st.success(t()["sync_complete"].format(success=len(api_races), failed=0))
                else:
                    st.warning(t()["no_races"])
            except requests.RequestException as exc:
                st.error(
                    tx(
                        f"同步賽程超時或失敗，請稍後再試：{exc}",
                        f"Schedule sync timed out or failed, please retry: {exc}",
                    )
                )
    
    # ==================== 根据模式获取赛事列表 ====================
    if date_mode == DATE_MODE_FUTURE:
        # 原有逻辑：获取未来14天赛事
        if st.session_state.get("upcoming_races_override"):
            upcoming_races = st.session_state.pop("upcoming_races_override")
        else:
            upcoming_races = get_cached_upcoming_races()
        if not upcoming_races:
            st.info(t()["no_races"])
            return
        
        valid_races = [r for r in upcoming_races if r.get('race_no', 0) > 0]
        if not valid_races:
            st.warning(t()["no_race_detail_data"])
            valid_races = upcoming_races
        
        dates = sorted(set([r.get('race_date') for r in valid_races if r.get('race_date')]))
        
        if not dates:
            st.info(t()["no_races_available"])
            return
        
        date_options = [f"{d} ({_weekday_label(d)})" for d in dates]
        
        selected_date_str = st.selectbox(t()["select_race_day"], date_options, key="selected_race_date")
        selected_date = selected_date_str.split(" ")[0]
        
        races = [r for r in valid_races if r.get('race_date') == selected_date]
        races.sort(key=_race_list_sort_key)
        overseas_count = sum(
            1 for r in races
            if (r.get("venue") or "").strip().upper() not in ("ST", "HV")
        )
        if overseas_count:
            st.caption(
                tx(
                    f"💡 同赛日含 {overseas_count} 场海外转播赛事（场次编号可能与本地重复，请留意「沙田/跑馬地/海外」标识）",
                    f"💡 This card includes {overseas_count} overseas simulcast race(s); race numbers may repeat—check venue labels.",
                )
            )
    
    else:
        st.info(t()["historical_mode_info"])
        historical_races = get_cached_historical_race_summaries()
        if not historical_races:
            st.warning(t()["no_history_race_data"])
            return

        dates = sorted(
            {r.get("race_date") for r in historical_races if r.get("race_date")},
            reverse=True,
        )
        date_options = [f"{d} ({_weekday_label(d)})" for d in dates]

        selected_date_str = st.selectbox(t()["select_history_race_day"], date_options, key="selected_history_date")
        selected_date = selected_date_str.split(" ")[0]
        races = [r for r in historical_races if r.get("race_date") == selected_date]
        races.sort(key=_race_list_sort_key)

    prediction_cutoff_date = selected_date if date_mode == DATE_MODE_HISTORY else None
    #-------------
    # ==================== 单场分析 ====================
    st.markdown(f"### {t()['single_race_analysis']}")
    
    if not races:
        st.warning(t()["no_race_detail_for_date"])
        return
    
    race_options = [_format_race_select_label(r) for r in races]
    
    selected_idx = st.selectbox(t()["select_race"], range(len(race_options)), format_func=lambda x: race_options[x], key="selected_race")
    #---------
    selected_race = races[selected_idx]
    current_race_key = (
        f"{selected_race.get('race_date')}_{selected_race.get('venue')}_{selected_race.get('race_no')}"
    )
    if st.session_state.get("prev_selected_race") != current_race_key:
        st.session_state.expand_win = False
        st.session_state.expand_qin = False
        st.session_state.expand_tri = False
        st.session_state.expand_qin_recommend = False
        st.session_state.expand_parlay = False
        st.session_state.expand_scoring_weights = False
        # 重置付费标记（换场次后，所有折叠重新计费）
        st.session_state.paid_win = False
        st.session_state.paid_qin = False
        st.session_state.paid_tri = False
        st.session_state.paid_qin_recommend = False
        st.session_state.paid_parlay = False
        st.session_state.paid_scoring_weights = False
        st.session_state.prev_selected_race = current_race_key
    #----------

    if not _is_local_venue(selected_race.get("venue")):
        st.warning(
            tx(
                "⚠️ 海外转播赛事：历史数据库以香港本地马匹为主，海外马通常无本地往绩，评分与 AI 推荐准确度有限，请主要参考赔率。",
                "⚠️ Overseas simulcast: the history DB covers HK horses; overseas runners often lack local form—treat scores/recommendations with caution.",
            )
        )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        refresh_race_btn = st.button(t()["refresh_race_data"], key="refresh_race")
    
    # ✅ 修改：单场同步也使用 API
    if refresh_race_btn:
        with st.spinner(t()["updating_odds"]):
            api_url = st.secrets.get("HKJC_API_URL", "")
            if api_url:
                try:
                    sync_url = f"{api_url.rstrip('/')}/sync/race"
                    response = requests.post(sync_url, json={
                        "date": selected_race.get('race_date'),
                        "venue": selected_race.get('venue'),
                        "raceNo": selected_race.get('race_no')
                    }, timeout=120)
                    if response.status_code == 200:
                        st.success(t()["data_updated"])
                        _clear_smart_betting_runners_cache()
                        get_cached_race_runners.clear()
                        get_cached_upcoming_races.clear()
                        fetch_race_odds_history.clear()
                        _query_odds_history_rows.clear()
                        st.session_state.pop(f"odds_rows_cache_{current_race_key}", None)
                        st.session_state.pop(f"auto_odds_collect_{current_race_key}", None)
                        auto_sync_key = (
                            f"auto_sync_{selected_race.get('race_date')}_"
                            f"{selected_race.get('venue')}_{selected_race.get('race_no')}"
                        )
                        st.session_state.pop(auto_sync_key, None)
                        st.rerun()
                    else:
                        st.warning(t()["update_failed"])
                except Exception as e:
                    st.error(f"{t()['sync_failed']}: {e}")
            else:
                if sync_single_race(selected_race):
                    st.success(t()["data_updated"])
                    st.rerun()
                else:
                    st.warning(t()["update_failed"])
    
    runners = get_cached_race_runners(
        selected_race.get('race_date'),
        selected_race.get('venue'),
        selected_race.get('race_no')
    )

    # 未来赛事：仅当 DB 无出马或无赔率时才同步 API（避免每次进页等 10s+）
    if (
        date_mode == DATE_MODE_FUTURE
        and st.secrets.get("HKJC_API_URL")
        and _runners_need_live_sync(runners)
    ):
        auto_sync_key = (
            f"auto_sync_{selected_race.get('race_date')}_"
            f"{selected_race.get('venue')}_{selected_race.get('race_no')}"
        )
        auto_sync_state = st.session_state.get(auto_sync_key)
        if auto_sync_state not in ("done", "failed"):
            if auto_sync_state != "running":
                st.session_state[auto_sync_key] = "running"
                try:
                    with st.spinner(t()["updating_odds"]):
                        synced = sync_single_race(selected_race)
                    st.session_state[auto_sync_key] = "done" if synced else "failed"
                except Exception:
                    st.session_state[auto_sync_key] = "failed"
                get_cached_race_runners.clear()
                st.rerun()
            else:
                st.info(tx("正在同步最新數據...", "Syncing latest data..."))
                return
        runners = get_cached_race_runners(
            selected_race.get('race_date'),
            selected_race.get('venue'),
            selected_race.get('race_no')
        )
    elif date_mode == DATE_MODE_FUTURE and runners and not refresh_race_btn:
        st.caption(
            tx(
                "💡 出马与赔率来自数据库缓存；如需最新数据请点击「刷新单场数据」",
                "💡 Runners/odds from DB cache; tap “Refresh race data” for latest API sync.",
            )
        )
    #------
    if not runners:
        st.warning(t()["no_runners"])
        return
    
    user_weights = {
        "basic": 0.30,
        "race": 0.40,
        "odds": 0.30,
        "temperature": 0.8,
        "odds_mix_ratio": 0.6
    }
    t2 = time.time()
    perf_log["获取 runners"] = t2 - t1
    perf_log["runners数量"] = len(runners)
    #--------
    runners_cache_key = _smart_betting_runners_cache_key(selected_race, model_choice)
    if (
        st.session_state.get("sb_scored_runners_key") == runners_cache_key
        and st.session_state.get("sb_scored_runners")
    ):
        runners = localize_runner_names(list(st.session_state["sb_scored_runners"]))
        perf_log["计算胜率"] = 0
    else:
        if not require_trial(f"score:{runners_cache_key}"):
            return
        # ==================== 计算胜率 ====================
        _ml_loading = model_choice != "评分系统"
        _progress_label = (
            t()["calculating_ml"].format(model=model_choice)
            if _ml_loading
            else t()["sb_scoring_runners"]
        )
        analysis_progress = st.progress(0, text=_progress_label)
        analysis_progress.progress(0.08, text=_progress_label)
        if model_choice == "评分系统":
            if not SCORING_ENGINE_OK:
                analysis_progress.empty()
                st.error("評分引擎未載入，請刷新頁面後重試。" if lang == "zh" else "Scoring engine failed to load. Please refresh.")
                return

            if st.session_state.get("scoring_weights_applied", False):
                weights_config = st.session_state.get("user_scoring_config", {})
            else:
                weights_config = _default_smart_betting_weights_config()

            precomputed = None
            if not st.session_state.get("scoring_weights_applied", False):
                precomputed = _try_apply_precomputed_scores(
                    runners,
                    selected_race.get("race_date"),
                    selected_race.get("venue"),
                    selected_race.get("race_no"),
                )

            if precomputed is not None:
                analysis_progress.progress(0.85, text=t()["sb_scoring_runners"])
                runners = localize_runner_names(precomputed)
            else:
                horse_ids = tuple({r.get("horse_id") for r in runners if r.get("horse_id")})
                perf_cache = se_get_horses_performances_batch(horse_ids)
                horse_birth_years = get_cached_horse_birth_years()
                incident_llm_map = _build_incident_llm_map(
                    [r.get("incident", "") for r in runners if r.get("incident")]
                )

                analysis_progress.progress(0.45, text=t()["sb_scoring_runners"])
                runners = score_runners_for_prediction(
                    selected_race.get("race_date"),
                    selected_race.get("venue"),
                    selected_race.get("distance", 1200),
                    runners,
                    perf_cache,
                    horse_birth_years,
                    weights_config,
                    temperature=0.8,
                    incident_llm_map=incident_llm_map,
                )
                runners = localize_runner_names(runners)
        #---------
        else:
            # ==================== ML 模型预测（使用与回测相同的训练数据） ====================
            model_type = _resolve_ml_model_type(model_choice)
            analysis_progress.progress(0.2, text=t()["calculating_ml"].format(model=model_choice))
            _, model = get_smart_betting_ml_model(model_choice, prediction_cutoff_date)
            analysis_progress.progress(0.55, text=t()["calculating_ml"].format(model=model_choice))

            if model is not None:
                try:
                    horse_ids = tuple({r.get("horse_id") for r in runners if r.get("horse_id")})
                    ml_perf_cache = se_get_horses_performances_batch(horse_ids)
                    incident_llm_map = _build_incident_llm_map(
                        [r.get("incident", "") for r in runners if r.get("incident")]
                    )
                    analysis_progress.progress(0.7, text=t()["calculating_ml"].format(model=model_choice))
                    ml_probs = get_model_predictions(
                        selected_race.get('race_date'),
                        selected_race.get('venue'),
                        selected_race.get('race_no'),
                        runners,
                        model_type,
                        model,
                        perf_cache=ml_perf_cache,
                        incident_llm_map=incident_llm_map,
                    )
                except Exception as e:
                    st.error(f"{t()['prediction_error']}: {e}")
                    ml_probs = [0.34] * len(runners)
            else:
                ml_probs = [0.34] * len(runners)

            for i, runner in enumerate(runners):
                if i < len(ml_probs):
                    runner['win_probability'] = ml_probs[i]
                    runner['overall_score'] = ml_probs[i] * 100
            runners = localize_runner_names(runners)

        analysis_progress.progress(0.9, text=t()["sb_building_recommendations"])
        st.session_state["sb_scored_runners_key"] = runners_cache_key
        st.session_state["sb_scored_runners"] = runners
        analysis_progress.progress(1.0, text=t()["sb_analysis_done"])
        analysis_progress.empty()
        t3 = time.time()
        perf_log["计算胜率"] = t3 - t2
    
    sorted_runners = runners if model_choice == "评分系统" else sorted(
        runners, key=lambda x: x.get("win_probability", 0), reverse=True
    )

    #--------------------
    # 在计算完 runners 的 win_probability 之后添加

    # ==================== 调用策略引擎生成投注建议 ====================
    # 初始化 t3 变量，防止 UnboundLocalError
    t3 = time.time()  # ← 添加这一行，确保 t3 始终有值
    
    if sorted_runners:
        # 准备策略引擎所需数据
        scores = [runner.get("combined_score", runner.get("overall_score", 50)) for runner in sorted_runners]
        horse_names = [resolve_horse_name(_runner_record(runner)) for runner in sorted_runners]
        horse_nos = [runner.get("horse_no") for runner in sorted_runners]
        
        # 获取赔率
        odds_win = []
        odds_place = []
        for runner in sorted_runners:
            odds_raw = runner.get('odds_win')
            try:
                odds = float(odds_raw) if odds_raw else 0
            except (ValueError, TypeError):
                odds = 0
            odds_win.append(odds)

            place_raw = runner.get('odds_place')
            try:
                place_odds = float(place_raw) if place_raw else 0
            except (ValueError, TypeError):
                place_odds = 0
            if place_odds <= 0 and odds > 0:
                place_odds = odds * 0.3
            odds_place.append(place_odds)
        
        # 获取连赢和单T赔率（如果有真实数据）
        odds_qin, odds_tri, odds_tce = get_cached_race_pool_odds(
            selected_race.get('race_date'), selected_race.get('race_no')
        )
        
        # 生成建议
        engine = _make_betting_strategy_engine()
        recommendations = engine.generate_all_recommendations(
            scores=scores,
            horse_names=horse_names,
            odds_win=odds_win,
            odds_place=odds_place,
            odds_qin=odds_qin,
            odds_tri=odds_tri,
            odds_tce=odds_tce,
            horse_nos=horse_nos,
        )
        t4 = time.time()
        perf_log["策略引擎"] = t4 - t3
    else:
        # 如果没有 runners，也要记录时间
        perf_log["策略引擎"] = 0
        recommendations = {}  # 空建议
        
    #------------
    # 显示表格
    st.markdown(f"#### 🏇 {t()['race_table_title'].format(race_no=selected_race.get('race_no'))} ({model_choice})")
    #-----------
    race_data = []
    for runner in sorted_runners:
        horse_name = _horse_display_label(runner)
        # 安全处理赔率
        odds_win_raw = runner.get('odds_win')
        odds_place_raw = runner.get('odds_place')
        
        try:
            odds_win_display = f"{float(odds_win_raw):.1f}" if odds_win_raw and float(odds_win_raw) > 0 else "-"
        except (ValueError, TypeError):
            odds_win_display = "-"
        
        try:
            odds_place_display = f"{float(odds_place_raw):.1f}" if odds_place_raw and float(odds_place_raw) > 0 else "-"
        except (ValueError, TypeError):
            odds_place_display = "-"
        
        # 安全处理胜率和评分
        win_prob = runner.get('win_probability', 0)
        win_prob_display = f"{win_prob*100:.1f}%" if win_prob else "0%"
        
        overall_score = runner.get('overall_score', 0)
        overall_score_display = f"{overall_score:.0f}" if overall_score else "0"
        
        # ⭐ 修复：安全获取赔率并转换为浮点数
        win_prob_val = runner.get('win_probability', 0)
        odds_raw = runner.get('odds_win')
        try:
            odds_win_val = float(odds_raw) if odds_raw and odds_raw != '' else 0
        except (ValueError, TypeError):
            odds_win_val = 0
        
        if win_prob_val > 0 and odds_win_val > 0:
            ev = win_prob_val * odds_win_val - 1
            ev_display = f"{ev:+.2f}"
        else:
            ev_display = "-"
        
        race_data.append({
            t()["horse_no"]: runner.get("horse_no", "-"),
            t()["horse_name_no"]: horse_name,
            t()["draw"]: runner.get('draw', '-'),
            t()["actual_weight"]: runner.get('actual_weight', '-'),
            t()["jockey"]: resolve_jockey_name(runner),
            t()["win_odds"]: odds_win_display,
            t()["place_odds"]: odds_place_display,
            t()["win_rate"]: win_prob_display,
            t()["overall_score"]: overall_score_display,
            t()["ev"]: ev_display
        })
    
    # 只有当有数据时才显示表格
    if race_data:
        runner_df = pd.DataFrame(race_data)
        st.dataframe(
            _style_runner_table_min_odds(runner_df, t()["win_odds"], t()["place_odds"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(t()["no_data"])
    
    t5 = time.time()
    perf_log["显示表格"] = t5 - t4

    _render_realtime_odds_analysis(
        selected_race,
        sorted_runners,
        selected_date,
        current_race_key,
        odds_rows=None,
    )
        
    #------------
    # ==================== AI 投注策略建议（折叠版） ====================
    st.markdown(f"### {_model_section_title(t()['ai_strategy_suggestions'], model_choice)}")
    st.caption(t()["ev_description"])
    _render_ai_strategy_recommendation_sections(current_race_key, recommendations, sorted_runners)

    st.markdown("---")
    # ==================== 新增：過関投注推薦器 ====================
    st.markdown(f"## {_model_section_title(t()['parlay_recommendation'], model_choice)}")
    st.caption(t()["parlay_description"])
    
    # 获取当前赛日的所有赛事（用于过关推荐；默认仅本地 ST/HV）
    current_races_for_parlay = [r for r in races if _is_local_venue(r.get("venue"))]
    if not current_races_for_parlay:
        current_races_for_parlay = races
    elif len(current_races_for_parlay) < len(races):
        st.caption(
            tx(
                "💡 過關推薦默认仅含沙田/跑馬地本地赛事（不含海外转播）",
                "💡 Parlay defaults to local ST/HV races only (excludes overseas simulcasts)",
            )
        )
    
    if current_races_for_parlay and len(current_races_for_parlay) >= 2:
        # 让用户選擇要過關的場次
        st.markdown(f"**{t()['parlay_select_races_title']}**")
        
        parlay_race_options = [_format_race_select_label(r, include_date=False) for r in current_races_for_parlay]
        
        # 多选框
        selected_parlay_indices = st.multiselect(
            t()["select_2_6_races"],
            options=range(len(parlay_race_options)),
            format_func=lambda x: parlay_race_options[x],
            default=range(min(3, len(parlay_race_options))),
            key="parlay_race_select"
        )
        
        if len(selected_parlay_indices) >= 2:
            st.caption(t()["selected_races_count"].format(count=len(selected_parlay_indices)))
            parlay_cache_key = _parlay_schedule_cache_key(
                selected_parlay_indices, model_choice, selected_date, prediction_cutoff_date
            )

            if st.button(t()["generate_parlay"], key="generate_parlay_schedule", use_container_width=True):
                if not require_trial(f"parlay_schedule:{parlay_cache_key}", dedupe=False):
                    pass
                else:
                    progress = _UiProgressBar(t()["calculating_parlay_schedule"])
                    weights_config = None
                    if model_choice == "评分系统" and st.session_state.get("scoring_weights_applied"):
                        weights_config = st.session_state.get("user_scoring_config", {})
                    sorted_indices = sorted(
                        selected_parlay_indices,
                        key=lambda i: current_races_for_parlay[i].get("race_no", 0),
                    )
                    parlay_races_data = []
                    total = max(len(sorted_indices), 1)
                    for step_i, idx in enumerate(sorted_indices):
                        progress.step(
                            (step_i + 0.5) / total,
                            t()["progress_race_analysis"].format(current=step_i + 1, total=total),
                        )
                        race = current_races_for_parlay[idx]
                        runners_data = _score_runners_for_parlay_race(
                            race,
                            model_choice,
                            user_weights,
                            weights_config,
                            None,
                            None,
                            prediction_cutoff_date,
                        )
                        if runners_data:
                            parlay_races_data.append(_pack_parlay_race_entry(race, runners_data))
                    progress.step(0.9, t()["progress_building_parlay"])
                    if len(parlay_races_data) < 2:
                        st.session_state.pop("parlay_schedule_results", None)
                        st.session_state.pop("parlay_schedule_cache_key", None)
                        progress.finish()
                        st.warning(t()["parlay_insufficient_data"])
                    else:
                        max_legs = min(len(parlay_races_data), 6)
                        results, recommender = _compute_parlay_schedule_results(
                            parlay_races_data, max_legs
                        )
                        st.session_state["parlay_schedule_results"] = results
                        st.session_state["parlay_schedule_cache_key"] = parlay_cache_key
                        progress.finish()

            cached_key = st.session_state.get("parlay_schedule_cache_key")
            cached_results = st.session_state.get("parlay_schedule_results")
            if cached_results and cached_key == parlay_cache_key:
                display_recommender = ParlayRecommender()
                _display_parlay_schedule_results(cached_results, display_recommender)
            else:
                st.caption(t()["parlay_select_hint"])
    
    st.markdown("---")
    
    # ==================== 全天优化投注 ====================
    st.markdown(f"### {_model_section_title(t()['full_day_optimization'], model_choice)}")
    st.caption(t()["kelly_description"])
    #----------------
    if st.button(t()["generate_full_day"], key="generate_full_day", use_container_width=True, type="primary"):
        if not require_trial(f"full_day:{selected_date}:{model_choice}", dedupe=False):
            pass
        else:
            progress = _UiProgressBar(t()["progress_optimizing_full_day"])
            all_bets = []
            total_stake = 0
            total_expected = 0
            ml_model = None
            ml_model_type = None
            if model_choice != "评分系统":
                ml_model_type, ml_model = get_smart_betting_ml_model(model_choice, prediction_cutoff_date)
            weights_config = None
            if model_choice == "评分系统" and st.session_state.get("scoring_weights_applied"):
                weights_config = st.session_state.get("user_scoring_config", {})

            total_races = max(len(races), 1)
            for race_i, race in enumerate(races):
                progress.step(
                    (race_i + 0.5) / total_races,
                    t()["progress_race_analysis"].format(current=race_i + 1, total=total_races),
                )
                race_runners = _score_runners_for_parlay_race(
                    race,
                    model_choice,
                    user_weights,
                    weights_config,
                    ml_model,
                    ml_model_type,
                    prediction_cutoff_date,
                )
                if not race_runners:
                    continue

                top_horses = sorted(race_runners, key=lambda x: x.get('win_probability', 0), reverse=True)[:2]
                for horse in top_horses:
                    if horse is None:
                        continue
                    prob = horse.get('win_probability', 0)
                    odds_raw = horse.get('odds_win')

                    try:
                        odds = float(odds_raw) if odds_raw else 0
                    except (ValueError, TypeError):
                        odds = 0

                    if prob <= 0 or odds <= 1:
                        continue

                    kelly = calculate_kelly_fraction(prob, odds)
                    if kelly <= 0:
                        continue

                    stake = bankroll * kelly * risk_multiplier * 0.3
                    expected = calculate_expected_value(prob, odds, stake)

                    if stake >= 10:
                        all_bets.append({
                            t()["col_race_no"]: f"{tx('第', 'Race ')}{race.get('race_no')}{tx('場', '')}",
                            t()["col_horse"]: _horse_display_label(horse),
                            t()["col_odds"]: odds,
                            t()["col_win_rate"]: f"{prob*100:.1f}%",
                            t()["col_suggested_amount"]: f"HK${stake:.0f}",
                            t()["col_expected_value"]: f"${expected:.0f}"
                        })
                        total_stake += stake
                        total_expected += expected

            progress.finish()
            if all_bets:
                st.dataframe(pd.DataFrame(all_bets), use_container_width=True, hide_index=True)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(t()["total_stake_metric"], f"HK${total_stake:.0f}")
                with col2:
                    st.metric(t()["total_ev_metric"], f"${total_expected:+.0f}")
                with col3:
                    roi = (total_expected / total_stake * 100) if total_stake > 0 else 0
                    st.metric(t()["expected_roi_metric"], f"{roi:+.1f}%")
            else:
                st.warning(t()["no_betting_opportunities"])

    st.markdown("---")
    st.markdown(f"### 💰 {_model_section_title(t()['day_portfolio_title'], model_choice)}")
    st.caption(t()["day_portfolio_desc"])
    portfolio_budget = st.number_input(
        t()["day_portfolio_budget_label"],
        min_value=100,
        max_value=10000,
        value=1000,
        step=100,
        key="day_portfolio_budget",
    )
    portfolio_min_ev = st.slider(
        t()["min_ev_threshold"],
        min_value=0.0,
        max_value=0.5,
        value=0.0,
        step=0.05,
        format="%.2f",
        key="day_portfolio_min_ev",
    )
    if st.button(t()["generate_day_portfolio"], key="generate_day_portfolio", use_container_width=True, type="primary"):
        if not require_trial(f"day_portfolio:{selected_date}:{model_choice}", dedupe=False):
            pass
        else:
            progress = _UiProgressBar(t()["optimizing_day_portfolio"])
            weights_config = None
            if model_choice == "评分系统" and st.session_state.get("scoring_weights_applied"):
                weights_config = st.session_state.get("user_scoring_config", {})
            incident_texts = []
            total_races = max(len(races), 1)
            for race_i, race in enumerate(races):
                progress.step(
                    (race_i + 0.4) / total_races,
                    t()["progress_race_analysis"].format(current=race_i + 1, total=total_races),
                )
                for runner in get_cached_race_runners(
                    race.get("race_date"), race.get("venue"), race.get("race_no")
                ) or []:
                    txt = runner.get("incident", "")
                    if txt:
                        incident_texts.append(txt)
            progress.step(0.85, t()["sb_building_recommendations"])
            incident_llm_map = _build_incident_llm_map(incident_texts)
            portfolio_result = build_live_day_portfolio(
                races,
                model_choice,
                portfolio_budget,
                min_ev=portfolio_min_ev,
                prediction_cutoff_date=prediction_cutoff_date,
                user_weights=user_weights,
                weights_config=weights_config,
                incident_llm_map=incident_llm_map,
            )
            progress.finish()
            if portfolio_result:
                _display_live_day_portfolio(portfolio_result, portfolio_budget)
    
    st.markdown("---")
    
    # ==================== 过关组合推荐 ====================
    st.markdown(f"### {_model_section_title(t()['parlay_generation'], model_choice)}")
    st.caption(t()["parlay_description"])
    #--------------------
    if st.button(t()["generate_parlay_combo"], key="generate_parlay", use_container_width=True, type="primary"):
        if not require_trial(f"parlay_combo:{selected_date}:{model_choice}", dedupe=False):
            pass
        else:
            progress = _UiProgressBar(t()["calculating_parlay"])
            confidence_horses = []
            ml_model = None
            ml_model_type = None
            if model_choice != "评分系统":
                ml_model_type, ml_model = get_smart_betting_ml_model(model_choice, prediction_cutoff_date)
            weights_config = None
            if model_choice == "评分系统" and st.session_state.get("scoring_weights_applied"):
                weights_config = st.session_state.get("user_scoring_config", {})

            total_races = max(len(races), 1)
            for race_i, race in enumerate(races):
                progress.step(
                    (race_i + 0.5) / total_races,
                    t()["progress_race_analysis"].format(current=race_i + 1, total=total_races),
                )
                race_runners = _score_runners_for_parlay_race(
                    race,
                    model_choice,
                    user_weights,
                    weights_config,
                    ml_model,
                    ml_model_type,
                    prediction_cutoff_date,
                )
                if not race_runners:
                    continue

                top = max(race_runners, key=lambda x: x.get('win_probability', 0), default=None)
                if top and top.get('win_probability', 0) >= 0.20:
                    confidence_horses.append({
                        "race_no": race.get('race_no'),
                        "horse_name": resolve_horse_name(_runner_record(top)),
                        "horse_no": top.get('horse_no'),
                        "display_name": _horse_display_label(top),
                        "probability": top.get('win_probability', 0),
                        "odds": top.get('odds_win', 0)
                    })

            progress.step(0.9, t()["progress_building_parlay"])
            confidence_horses.sort(key=lambda x: x.get("race_no", 0))
            parlay_results = _generate_parlay_combo_results(
                confidence_horses, bankroll, risk_multiplier
            )
            progress.finish()

            if parlay_results:
                st.dataframe(pd.DataFrame(parlay_results), use_container_width=True, hide_index=True)
                if len(confidence_horses) < 3:
                    st.caption(t()["parlay_3leg_hint"])
            else:
                st.info(t()["no_parlay_combos"])
    
    st.markdown("---")
    if st.session_state.get("sb_show_weights_panel"):
        _render_smart_betting_weights_panel(lang)
        st.markdown("---")
    st.caption(t()["disclaimer"])

def sync_single_race(race: Dict) -> bool:
    """同步单场赛事的最新数据（赔率、出赛马匹）"""
    try:
        API_BASE_URL = st.secrets.get("HKJC_API_URL", "")
        if not API_BASE_URL:
            return False
        
        sync_url = f"{API_BASE_URL.rstrip('/')}/sync/race"
        response = requests.post(sync_url, json={
            "date": race.get('race_date'),
            "venue": race.get('venue'),
            "raceNo": race.get('race_no')
        }, timeout=120)
        
        return response.status_code == 200 and response.json().get("success")
    except Exception as e:
        print(f"同步单场赛事失败: {e}")
        return False


def sync_meeting_via_api(race_date: str, venue: str) -> Dict:
    """同步整个赛马日出赛名单与赔率到 Supabase。"""
    result = {"success": False, "synced": 0, "failed": 0, "total": 0, "error": ""}
    try:
        API_BASE_URL = st.secrets.get("HKJC_API_URL", "").rstrip("/")
        if not API_BASE_URL:
            result["error"] = "HKJC_API_URL not configured"
            return result
        response = requests.post(
            f"{API_BASE_URL}/sync/meeting",
            json={"date": race_date, "venue": venue},
            timeout=600,
        )
        if response.status_code == 200:
            payload = response.json()
            result.update({
                "success": bool(payload.get("success")),
                "synced": payload.get("synced", 0),
                "failed": payload.get("failed", 0),
                "total": payload.get("total", 0),
            })
        else:
            result["error"] = response.text[:200]
    except Exception as exc:
        result["error"] = str(exc)
    return result


def sync_all_future_via_api() -> bool:
    """触发 Node.js 全量同步未来赛事。"""
    try:
        API_BASE_URL = st.secrets.get("HKJC_API_URL", "").rstrip("/")
        if not API_BASE_URL:
            return False
        response = requests.post(f"{API_BASE_URL}/sync/all", timeout=30)
        return response.status_code == 200 and response.json().get("success")
    except Exception as exc:
        print(f"sync_all_future_via_api failed: {exc}")
        return False


def trigger_odds_collection_for_race(race_date: str, venue: str, race_no: int, *, force: bool = False) -> Dict:
    """请求 Node.js 采集单场 WIN/PLA 赔率快照到 odds_history。"""
    result = {
        "success": False,
        "saved": 0,
        "keyMinute": None,
        "reason": "",
        "skipped": False,
        "rawMinutes": None,
        "error": "",
    }
    try:
        API_BASE_URL = st.secrets.get("HKJC_API_URL", "").rstrip("/")
        if not API_BASE_URL:
            result["error"] = "HKJC_API_URL not configured"
            return result
        response = requests.post(
            f"{API_BASE_URL}/collect/race",
            json={
                "date": race_date,
                "venue": venue,
                "raceNo": int(race_no),
                "force": force,
            },
            timeout=120,
        )
        payload = response.json() if response.content else {}
        result.update({
            "success": response.status_code == 200 and bool(payload.get("success")),
            "saved": payload.get("saved", 0),
            "keyMinute": payload.get("keyMinute"),
            "reason": payload.get("reason") or "",
            "skipped": payload.get("skipped", False),
            "rawMinutes": payload.get("rawMinutes"),
            "error": payload.get("error")
            or ("" if response.status_code == 200 else response.text[:200]),
        })
    except Exception as exc:
        result["error"] = str(exc)
    return result


# ==================== 第4次代码结束 ====================

# ============================================================
# 第5次代码：回测 + 管理员面板
# 包含：单场回测、全天回测、管理员用户管理
# 版本：v1.0
# 说明：替换原有的 render_backtest_page() 函数
# ============================================================

# ==================== 回测辅助函数 ====================
def get_historical_races(limit: int = 100) -> List[Dict]:
    """获取历史赛事列表（用于回测）"""
    try:
        headers = get_supabase_headers(use_secret=True)
        today = datetime.now().strftime("%Y-%m-%d")
        # 查询今天之前的赛事（无论 race_status 是什么）
        url = f"{SUPABASE_URL}/rest/v1/races?race_date=lt.{today}&order=race_date.desc,race_no.asc&limit={limit}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"获取历史赛事失败: {e}")
        return []


def get_race_without_future_data(race_date: str, race_id: int) -> List[Dict]:
    """
    获取赛事数据，但只使用该日期之前的历史数据
    关键：不能使用 race_date 之后的数据
    """
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 获取赛事信息
        race_url = f"{SUPABASE_URL}/rest/v1/races?race_id=eq.{race_id}"
        race_response = requests.get(race_url, headers=headers)
        
        if race_response.status_code != 200 or not race_response.json():
            return []
        
        race = race_response.json()[0]
        
        # 获取出赛马匹
        runners_url = f"{SUPABASE_URL}/rest/v1/race_runners?race_id=eq.{race_id}"
        runners_response = requests.get(runners_url, headers=headers)
        
        if runners_response.status_code != 200:
            return []
        
        runners = runners_response.json()
        
        # 为每匹马获取 race_date 之前的历史往绩
        for runner in runners:
            horse_id = runner.get('horse_id')
            if horse_id:
                perf_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?horse_id=eq.{horse_id}&race_date=lt.{race_date}&order=race_date.desc&limit=20"
                perf_response = requests.get(perf_url, headers=headers)
                if perf_response.status_code == 200:
                    runner['past_performances_v2'] = perf_response.json()
                else:
                    runner['past_performances_v2'] = []
        
        return runners
    except Exception as e:
        print(f"获取赛事数据失败: {e}")
        return []

#-------------
def run_backtest_on_race(race_id: int, race_date: str, user_weights: Dict) -> Dict:
    """
    对单场赛事进行回测（使用新评分引擎）
    返回: 预测结果 vs 实际结果
    """
    try:
        # 获取赛事信息
        headers = get_supabase_headers(use_secret=True)
        race_url = f"{SUPABASE_URL}/rest/v1/races?race_id=eq.{race_id}"
        race_response = requests.get(race_url, headers=headers)
        
        if race_response.status_code != 200 or not race_response.json():
            return {"success": False, "error": "无法获取赛事信息"}
        
        race = race_response.json()[0]
        venue = race.get('venue', 'ST')
        distance = race.get('distance', 1200)
        
        # 获取该赛事的出赛马匹（从 past_performances_v2）
        runners_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race.get('race_no')}&order=position.asc&limit=100"
        runners_response = requests.get(runners_url, headers=headers)
        
        if runners_response.status_code != 200 or not runners_response.json():
            return {"success": False, "error": "无法获取出赛马匹数据"}
        
        runners_data = runners_response.json()
        
        # 找出实际冠军
        actual_winner = None
        actual_winner_horse_id = None
        for r in runners_data:
            if r.get('position') == 1:
                actual_winner = r.get('horse_name', '')
                actual_winner_horse_id = r.get('horse_id')
                break
        
        if not actual_winner:
            return {"success": False, "error": "无实际赛果数据"}
        
        # 批量获取所有马匹的往绩
        horse_ids = [r.get('horse_id') for r in runners_data if r.get('horse_id')]
        perf_cache = get_horses_performances_batch(horse_ids)
        
        # 计算每匹马的评分
        runners_with_scores = []
        for r in runners_data:
            horse_id = r.get('horse_id')
            if not horse_id:
                continue
            
            performances = perf_cache.get(horse_id, [])
            
            # 提取历史体重
            past_weights = [p.get('body_weight') for p in performances if p.get('body_weight')]
            
            # 获取本场参数
            draw = r.get('draw')
            actual_weight = r.get('actual_weight')
            jockey = r.get('jockey')
            trainer = r.get('trainer')
            body_weight = r.get('body_weight')
            closing_profile = r.get('closing_profile', 'Even')
            incident = r.get('incident', '')
            odds_win = r.get('odds', 10.0)
            
            # 使用 scoring_engine 模块计算
            from scoring_engine import (
                calculate_basic_score,
                calculate_race_score,
                calculate_odds_score,
                calculate_status_score,
                calculate_overall_score
            )
            
            basic_score = calculate_basic_score(performances, distance)
            race_score = calculate_race_score(performances, venue, distance, draw, jockey, trainer)
            odds_score = calculate_odds_score(odds_win)
            status_score = calculate_status_score(horse_id, race_date, body_weight, past_weights, closing_profile, incident)
            overall_score = calculate_overall_score(basic_score, race_score, odds_score, status_score)
            
            runners_with_scores.append({
                "horse_id": horse_id,
                "horse_name": r.get('horse_name', ''),
                "combined_score": overall_score,
                "actual_winner": (horse_id == actual_winner_horse_id)
            })
        
        if not runners_with_scores:
            return {"success": False, "error": "无有效评分数据"}
        
        # 排序找出预测冠军
        runners_with_scores.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
        predicted_winner_id = runners_with_scores[0].get('horse_id') if runners_with_scores else None
        
        # 判断是否正确
        is_correct = (predicted_winner_id == actual_winner_horse_id)
        
        # 计算前三名命中率
        predicted_top3_ids = [s.get('horse_id') for s in runners_with_scores[:3]]
        actual_top3_ids = [r.get('horse_id') for r in runners_data if r.get('position', 0) in [1, 2, 3]]
        top3_hits = len(set(predicted_top3_ids) & set(actual_top3_ids))
        
        return {
            "success": True,
            "is_correct": is_correct,
            "top3_hits": top3_hits,
            "predicted_winner_score": runners_with_scores[0].get('combined_score', 0) if runners_with_scores else 0,
            "actual_winner_name": actual_winner,
            "total_runners": len(runners_data)
        }
        
    except Exception as e:
        print(f"回测失败: {e}")
        return {"success": False, "error": str(e)}


def run_full_day_backtest(race_date: str, user_weights: Dict) -> Dict:
    """
    对全天赛事进行回测
    返回: 全天统计结果
    """
    try:
        # 获取该日期的所有赛事
        headers = get_supabase_headers(use_secret=True)
        races_url = f"{SUPABASE_URL}/rest/v1/races?race_date=eq.{race_date}&race_status=eq.RESULT&order=race_no.asc"
        races_response = requests.get(races_url, headers=headers)
        
        if races_response.status_code != 200:
            return {"success": False, "error": "无法获取赛事列表"}
        
        races = races_response.json()
        
        results = []
        correct_predictions = 0
        total_top3_hits = 0
        total_runners = 0
        
        for race in races:
            backtest_result = run_backtest_on_race(race.get('race_id'), race_date, user_weights)
            
            if backtest_result.get("success"):
                results.append({
                    "race_no": race.get('race_no'),
                    "is_correct": backtest_result.get("is_correct", False),
                    "top3_hits": backtest_result.get("top3_hits", 0),
                    "total_runners": backtest_result.get("total_runners", 0)
                })
                
                if backtest_result.get("is_correct"):
                    correct_predictions += 1
                total_top3_hits += backtest_result.get("top3_hits", 0)
                total_runners += backtest_result.get("total_runners", 0)
        
        accuracy = (correct_predictions / len(results) * 100) if results else 0
        top3_accuracy = (total_top3_hits / (len(results) * 3) * 100) if results else 0
        
        return {
            "success": True,
            "total_races": len(results),
            "correct_predictions": correct_predictions,
            "accuracy": round(accuracy, 1),
            "top3_hits": total_top3_hits,
            "top3_accuracy": round(top3_accuracy, 1),
            "results": results
        }
        
    except Exception as e:
        print(f"全天回测失败: {e}")
        return {"success": False, "error": str(e)}
#--------------
def run_models_backtest(start_date: str, end_date: str) -> List[Dict]:
    """运行多个模型的回测对比"""
    results = []
    
    models = [
        {"name": "评分系统", "type": "rule"},
        {"name": "LightGBM", "type": "lightgbm"},
        {"name": "XGBoost", "type": "xgboost"},
        {"name": "集成模型", "type": "ensemble"}
    ]
    
    for model in models:
        try:
            result = run_single_model_backtest(start_date, end_date, model["type"])
            results.append({
                "模型": model["name"],
                "测试场次": result.get("total_races", 0),
                "预测正确": result.get("correct_predictions", 0),
                "准确率": result.get("accuracy", 0),
                "总回报": result.get("total_return", 0),
                "总投入": result.get("total_stake", 0),
                "ROI": result.get("roi", 0)
            })
        except Exception as e:
            print(f"{model['name']} 回测失败: {e}")
            results.append({
                "模型": model["name"],
                "测试场次": 0,
                "预测正确": 0,
                "准确率": 0,
                "总回报": 0,
                "总投入": 0,
                "ROI": 0
            })
    
    return results


def run_single_model_backtest(start_date: str, end_date: str, model_type: str) -> Dict:
    """运行单个模型的回测"""
    result = {
        "total_races": 0,
        "correct_predictions": 0,
        "accuracy": 0,
        "total_return": 0,
        "total_stake": 0,
        "roi": 0
    }
    
    try:
        # 获取回测期间的赛事
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/races?race_date=gte.{start_date}&race_date=lte.{end_date}&order=race_date.asc"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return result
        
        races = response.json()
        result["total_races"] = len(races)
        
        # 用户权重（用于评分系统）
        user_weights = {
            "basic": 0.30,
            "race": 0.40,
            "odds": 0.30,
            "temperature": 0.8,
            "odds_mix_ratio": 0.6
        }
        
        for race in races:
            race_id = race.get('race_id')
            race_date = race.get('race_date')
            venue = race.get('venue', 'ST')
            race_no = race.get('race_no', 1)
            
            # 获取该赛事的出赛马匹
            runners = get_cached_race_runners(race_date, venue, race_no)
            
            if not runners:
                continue
            
            # 根据模型类型预测
            predicted_winner = None
            best_prob = 0
            
            if model_type == "rule":
                # 使用评分系统
                scores, probabilities = calculate_all_horses_scores(race_id, runners, user_weights)
                for i, runner in enumerate(runners):
                    if i < len(probabilities) and probabilities[i] > best_prob:
                        best_prob = probabilities[i]
                        predicted_winner = runner.get('horse_name')
            else:
                # 使用 ML 模型
                model_type_key = 'lightgbm' if model_type == 'lightgbm' else 'xgboost' if model_type == 'xgboost' else 'ensemble'
                ml_probs = get_model_predictions(race_id, runners, model_type_key)
                for i, runner in enumerate(runners):
                    if i < len(ml_probs) and ml_probs[i] > best_prob:
                        best_prob = ml_probs[i]
                        predicted_winner = runner.get('horse_name')
            
            # 获取实际冠军
            actual_winner = None
            for runner in runners:
                if runner.get('finishing_position') == 1:
                    actual_winner = runner.get('horse_name')
                    break
            
            if predicted_winner and actual_winner and predicted_winner == actual_winner:
                result["correct_predictions"] += 1
                
                # 模拟投注（假设每场投注 100 元）
                result["total_stake"] += 100
                
                # 获取赔率（简化处理）
                odds = 3.0
                for runner in runners:
                    if runner.get('horse_name') == predicted_winner:
                        odds = runner.get('odds_win', 3.0)
                        break
                
                result["total_return"] += 100 * odds
        
        if result["total_races"] > 0:
            result["accuracy"] = result["correct_predictions"] / result["total_races"] * 100
            if result["total_stake"] > 0:
                result["roi"] = (result["total_return"] - result["total_stake"]) / result["total_stake"] * 100
        
    except Exception as e:
        print(f"回测失败: {e}")
    
    return result
#-----------
def run_backtest_for_model(start_date: str, end_date: str, model_type: str) -> Dict:
    """
    回测函数（优化版，支持新评分系统）
    - 批量获取数据，避免 N+1 查询
    - ROI 修正：每场都投注 100 元
    - 增加多个前三名指标
    - 使用 scoring_config 权重配置
    - 包含状态因子（马龄、体重、事件、冲刺能力）
    """
    # 获取当前语言
    lang = st.session_state.get("lang", "zh")
    texts = t()
    
    # 模型名称（双语）
    model_names = {
        "rule": "评分系统" if lang == "zh" else "Rating System",
        "lightgbm": "LightGBM",
        "xgboost": "XGBoost",
        "ensemble": "集成模型" if lang == "zh" else "Ensemble"
    }
    
    result = {
        "模型": model_names.get(model_type, model_type),
        "测试场次": 0,
        "预测正确": 0,                    # 独赢正确场次
        "前三名命中匹数": 0,              # 累计命中匹数
        "前三名命中场次": 0,              # 至少命中1匹的场次数
        "前三名全中场次": 0,              # 3匹全中（不按顺序）的场次数
        "前三名顺序正确场次": 0,          # 顺序完全正确的场次数
        "独赢正确率": 0,
        "前三名命中匹数率": 0,
        "前三名命中场次率": 0,
        "前三名全中率": 0,
        "前三名顺序正确率": 0,
        "总投入": 0,
        "总回报": 0,
        "ROI": 0,
        "debug_details": [],
        "cancelled": False,
    }
    
    try:
        from scoring_engine import score_runners_for_prediction, load_horse_birth_years

        # ==================== 1. 加载评分配置 ====================
        from scoring_engine import get_scoring_config
        config = get_scoring_config()
        level1 = config.get('level1', {})
        basic_w = config.get('basic', {})
        race_w = config.get('race', {})
        odds_w = config.get('odds', {})
        status_w = config.get('status', {})
        
        # ==================== 2. 批量获取所有数据 ====================
        status_text_msg = texts["ml_loading_data"].format(start=start_date, end=end_date)
        with st.spinner(status_text_msg):
            all_performances = get_performances_batch(start_date, end_date)
        
        if not all_performances:
            error_msg = "未獲取到任何數據" if lang == "zh" else "No data retrieved"
            st.error(error_msg)
            return result

        incident_llm_map = _build_incident_llm_map(
            [p.get("incident", "") for p in all_performances if p.get("incident")]
        )
        
        # ==================== 3. 构建马匹往绩缓存 ====================
        horse_cache = build_horse_performances_cache(all_performances)
        
        # 获取马匹信息（含出生年份）
        try:
            horse_birth_years = load_horse_birth_years()
        except Exception as e:
            print(f"获取马匹出生年份失败: {e}")
            horse_birth_years = {}
        
        weights_cfg = {
            "level1": level1,
            "basic": basic_w,
            "race": race_w,
            "odds": odds_w,
            "status": status_w,
        }
        
        # ==================== 4. 提取赛事列表 ====================
        races = get_races_from_performances(all_performances)
        result["测试场次"] = len(races)
        
        if result["测试场次"] == 0:
            warn_msg = "未找到任何賽事" if lang == "zh" else "No races found"
            st.warning(warn_msg)
            return result
        
        # ==================== 6. 初始化统计变量 ====================
        correct_predictions = 0
        total_top3_hits = 0
        total_top3_hit_races = 0
        total_tri_correct = 0
        total_tce_correct = 0
        
        # 独赢投注统计
        total_stake = 0
        total_return = 0
        total_win_stake = 0
        total_win_return = 0
        
        # 位置投注统计
        total_position_stake = 0
        total_position_return = 0
        
        # ==================== 7. 创建进度条 ====================
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # ==================== 8. 遍历每场赛事 ====================
        for idx, race in enumerate(races):
            # 取消检查点
            if st.session_state.get("stop_backtest", False):
                warn_msg = "⚠️ 回測已被用戶取消" if lang == "zh" else "⚠️ Backtest cancelled by user"
                st.warning(warn_msg)
                result["cancelled"] = True
                break
            
            race_date = race['race_date']
            venue = race['venue']
            race_no = race['race_no']
            distance = race.get('distance', 1200)
            
            progress_msg = t()["rule_backtest_progress"].format(
                date=race_date,
                race_no=race_no,
                current=idx + 1,
                total=result["测试场次"],
            )
            status_text.text(progress_msg)
            progress_bar.progress((idx + 1) / result['测试场次'])
            
            # 获取该场赛事的出赛马匹
            runners_data = [p for p in all_performances 
                           if p['race_date'] == race_date 
                           and p['venue'] == venue 
                           and p['race_no'] == race_no]
            
            if not runners_data:
                continue
            
            # 构建 runners 列表并计算评分（与智能投注共用逻辑）
            runners_input = []
            for r in runners_data:
                horse_id = r.get("horse_id")
                if not horse_id:
                    continue
                horse_name_zh = r.get("horse_name", "")
                runners_input.append(
                    {
                        "horse_id": horse_id,
                        "horse_name": horse_name_zh,
                        "horse_name_zh": horse_name_zh,
                        "horse_name_en": r.get("horse_name_en", ""),
                        "horse_no": r.get("horse_no"),
                        "draw": r.get("draw"),
                        "actual_weight": r.get("actual_weight"),
                        "jockey": r.get("jockey"),
                        "trainer": r.get("trainer"),
                        "odds_win": r.get("odds"),
                        "body_weight": r.get("body_weight"),
                        "incident": r.get("incident", ""),
                        "running_position": r.get("running_position", ""),
                    }
                )

            runners = score_runners_for_prediction(
                race_date,
                venue,
                distance,
                runners_input,
                horse_cache,
                horse_birth_years,
                weights_cfg,
                incident_llm_map=incident_llm_map,
            )
            
            if not runners:
                continue
            
            predicted_1st_id = runners[0].get("horse_id") if len(runners) > 0 else None
            predicted_2nd_id = runners[1].get("horse_id") if len(runners) > 1 else None
            predicted_3rd_id = runners[2].get("horse_id") if len(runners) > 2 else None
            predicted_top3_ids = {predicted_1st_id, predicted_2nd_id, predicted_3rd_id} - {None}
            #-------
            # 获取实际结果
            runners_data_sorted = sorted(runners_data, key=lambda x: x.get('position', 99))
            actual_1st_id = None
            actual_2nd_id = None
            actual_3rd_id = None
            actual_top3_ids = set()
            
            actual_1st_label = actual_2nd_label = actual_3rd_label = "-"
            for r in runners_data_sorted:
                pos = r.get('position')
                record = _runner_record(r)
                hid = r.get("horse_id")
                if pos == 1:
                    actual_1st_id = hid
                    actual_1st_label = _backtest_horse_label(
                        r.get('horse_name', ''), r.get('horse_no'), record=record
                    )
                    actual_top3_ids.add(hid)
                elif pos == 2:
                    actual_2nd_id = hid
                    actual_2nd_label = _backtest_horse_label(
                        r.get('horse_name', ''), r.get('horse_no'), record=record
                    )
                    actual_top3_ids.add(hid)
                elif pos == 3:
                    actual_3rd_id = hid
                    actual_3rd_label = _backtest_horse_label(
                        r.get('horse_name', ''), r.get('horse_no'), record=record
                    )
                    actual_top3_ids.add(hid)

            pred_1st_label = _runner_backtest_label(runners[0] if len(runners) > 0 else None)
            pred_2nd_label = _runner_backtest_label(runners[1] if len(runners) > 1 else None)
            pred_3rd_label = _runner_backtest_label(runners[2] if len(runners) > 2 else None)
            
            # 统计各指标
            is_correct = (predicted_1st_id == actual_1st_id) if predicted_1st_id and actual_1st_id else False
            
            hits = len(predicted_top3_ids & actual_top3_ids)
            total_top3_hits += hits
            if hits >= 1:
                total_top3_hit_races += 1
            
            tri_correct = (
                predicted_top3_ids == actual_top3_ids
                if len(predicted_top3_ids) == 3 and len(actual_top3_ids) == 3
                else False
            )
            if tri_correct:
                total_tri_correct += 1
            
            tce_correct = (
                predicted_1st_id == actual_1st_id
                and predicted_2nd_id == actual_2nd_id
                and predicted_3rd_id == actual_3rd_id
            ) if all([predicted_1st_id, predicted_2nd_id, predicted_3rd_id, actual_1st_id, actual_2nd_id, actual_3rd_id]) else False
            if tce_correct:
                total_tce_correct += 1
            #----------------
            # ==================== ROI计算（修复版） ====================
            # 投注策略：每场独赢投注100元
            total_stake += 100
            
            # ✅ 获取实际获胜马的赔率
            actual_winner_odds = 0
            for r in runners_data:
                if r.get('position') == 1:
                    odds_raw = r.get('odds')
                    try:
                        actual_winner_odds = float(odds_raw) if odds_raw and odds_raw != '' else 0
                    except (ValueError, TypeError):
                        actual_winner_odds = 0
                    break
            
            # ✅ 使用实际获胜马的赔率计算回报
            if is_correct and actual_winner_odds > 0:
                total_return += 100 * actual_winner_odds
            elif is_correct:
                # 如果没有赔率数据，使用默认值3.0
                total_return += 100 * 3.0
            
            # ==================== 位置投注ROI（额外统计） ====================
            # 每匹预测前三名的马，位置投注30元
            # 注意：需要先在函数开头初始化 total_position_stake 和 total_position_return
            for predicted_id in predicted_top3_ids:
                if predicted_id and predicted_id in actual_top3_ids:
                    total_position_stake += 30
                    total_position_return += 30 * 1.5
                elif predicted_id:
                    total_position_stake += 30
            
            # 记录调试详情（双语）
            if lang == "zh":
                result["debug_details"].append({
                    "赛期": race_date,
                    "场次": race_no,
                    "预测第1名": pred_1st_label,
                    "预测第2名": pred_2nd_label,
                    "预测第3名": pred_3rd_label,
                    "实际第1名": actual_1st_label,
                    "实际第2名": actual_2nd_label,
                    "实际第3名": actual_3rd_label,
                    "独赢正确": "✅" if is_correct else "❌",
                    "前3名命中匹数": hits,
                    "前3名全中": "✅" if tri_correct else "❌",
                    "前3名顺序正确": "✅" if tce_correct else "❌",
                    "赔率": f"{actual_winner_odds:.1f}" if actual_winner_odds > 0 else "-"  # ⭐ 新增
                })
            else:
                result["debug_details"].append({
                    "Date": race_date,
                    "Race": race_no,
                    "Pred 1st": pred_1st_label,
                    "Pred 2nd": pred_2nd_label,
                    "Pred 3rd": pred_3rd_label,
                    "Actual 1st": actual_1st_label,
                    "Actual 2nd": actual_2nd_label,
                    "Actual 3rd": actual_3rd_label,
                    "Win": "✅" if is_correct else "❌",
                    "Top3 Hits": hits,
                    "Trio": "✅" if tri_correct else "❌",
                    "Trifecta": "✅" if tce_correct else "❌",
                    "Odds": f"{actual_winner_odds:.1f}" if actual_winner_odds > 0 else "-"  # ⭐ 新增
                })
            #-----------
            if is_correct:
                correct_predictions += 1
        
        # ==================== 9. 清理进度条 ====================
        progress_bar.empty()
        status_text.empty()
        #--------------
        # 10. 计算最终结果
        if result["测试场次"] > 0 and not result["cancelled"]:
            # 独赢指标
            result["预测正确"] = correct_predictions
            result["独赢正确率"] = correct_predictions / result["测试场次"] * 100
            
            # 前三名指标
            result["前三名命中匹数"] = total_top3_hits
            result["前三名命中匹数率"] = total_top3_hits / (result["测试场次"] * 3) * 100
            
            result["前三名命中场次"] = total_top3_hit_races
            result["前三名命中场次率"] = total_top3_hit_races / result["测试场次"] * 100
            
            result["前三名全中场次"] = total_tri_correct
            result["前三名全中率"] = total_tri_correct / result["测试场次"] * 100
            
            result["前三名顺序正确场次"] = total_tce_correct
            result["前三名顺序正确率"] = total_tce_correct / result["测试场次"] * 100
            
            # 独赢ROI
            result["总投入"] = total_stake
            result["总回报"] = total_return
            if total_stake > 0:
                result["ROI"] = (total_return - total_stake) / total_stake * 100
            
            # 位置ROI
            result["位置总投入"] = total_position_stake
            result["位置总回报"] = total_position_return
            if total_position_stake > 0:
                result["位置ROI"] = (total_position_return - total_position_stake) / total_position_stake * 100
            
            # 综合ROI（独赢 + 位置）
            result["综合总投入"] = total_stake + total_position_stake
            result["综合总回报"] = total_return + total_position_return
            if result["综合总投入"] > 0:
                result["综合ROI"] = (result["综合总回报"] - result["综合总投入"]) / result["综合总投入"] * 100
        
        if not result["cancelled"]:
            success_msg = f"✅ 回測完成: {result['测试场次']} 場, 獨贏正確率 {result['独赢正确率']:.1f}%, ROI {result['ROI']:+.1f}%" if lang == "zh" else f"✅ Backtest complete: {result['测试场次']} races, Win Rate {result['独赢正确率']:.1f}%, ROI {result['ROI']:+.1f}%"
            st.success(success_msg)
        
    except Exception as e:
        error_msg = f"回測失敗: {e}" if lang == "zh" else f"Backtest failed: {e}"
        st.error(error_msg)
        print(f"回測失敗 ({model_type}): {e}")
    
    st.session_state.stop_backtest = False
    return result
#------------
# ==================== 回测专用：批量数据获取与缓存 ====================

@st.cache_data(ttl=3600, show_spinner=False)
def get_performances_batch(start_date: str, end_date: str) -> List[Dict]:
    """
    批量获取日期范围内的所有 past_performances_v2 数据
    使用 st.cache_data 缓存，避免重复查询
    """
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?race_date=gte.{start_date}&race_date=lte.{end_date}&limit=50000"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"批量获取数据失败: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"批量获取数据异常: {e}")
        return []
#----------------
# ==================== 新马判断辅助函数 ====================

def get_new_horse_info(horse_id: str, past_performances: List[Dict], race_date: str) -> Dict:
    """
    判断马匹是否为新马，并返回类型和默认评分
    
    参数：
        horse_id: 马匹ID
        past_performances: 该马匹在 race_date 之前的往绩列表
        race_date: 当前赛事日期
    
    返回：
        {
            'is_new': bool,
            'type': 'PP' | 'PPG' | 'INT' | 'EXPERIENCED',
            'score': int or None,
            'label': str,
            'total_races': int
        }
    """
    # 获取 race_date 之前的往绩
    past_before = [p for p in past_performances if p.get('race_date', '') < race_date]
    total_races = len(past_before)
    
    # 出赛不足3场 → 新马
    if total_races < 3:
        # 根据 horse_id 判断类型
        horse_id_str = str(horse_id) if horse_id else ''
        
        if 'PPG' in horse_id_str:
            return {
                'is_new': True,
                'type': 'PPG',
                'score': 42,
                'label': '自购马',
                'total_races': total_races
            }
        elif 'INT' in horse_id_str:
            return {
                'is_new': True,
                'type': 'INT',
                'score': 45,
                'label': '国际马',
                'total_races': total_races
            }
        else:
            return {
                'is_new': True,
                'type': 'PP',
                'score': 35,
                'label': '自购新马',
                'total_races': total_races
            }
    
    return {
        'is_new': False,
        'type': 'EXPERIENCED',
        'score': None,
        'label': '有经验马',
        'total_races': total_races
    }


def get_jockey_win_rates_from_db() -> Dict[str, float]:
    """
    从数据库统计所有骑师的胜率
    返回：{骑师名称: 胜率}
    """
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=jockey,position&limit=50000"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return {}
        
        data = response.json()
        jockey_stats = {}
        
        for p in data:
            jockey = p.get('jockey')
            if not jockey:
                continue
            if jockey not in jockey_stats:
                jockey_stats[jockey] = {'wins': 0, 'total': 0}
            jockey_stats[jockey]['total'] += 1
            if p.get('position') == 1:
                jockey_stats[jockey]['wins'] += 1
        
        result = {}
        for jockey, stats in jockey_stats.items():
            if stats['total'] > 0:
                result[jockey] = stats['wins'] / stats['total']
        
        return result
    except Exception as e:
        print(f"获取骑师胜率失败: {e}")
        return {}
#------------
def get_horse_birth_years_from_db() -> Dict[str, int]:
    """从数据库获取所有马匹的出生年份"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/horses_v2?select=horse_id,birth_year"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = {}
            for h in response.json():
                horse_id = h.get('horse_id')
                if horse_id:
                    result[horse_id] = h.get('birth_year')
            return result
        return {}
    except Exception as e:
        print(f"获取马匹出生年份失败: {e}")
        return {}
#----------------
def build_horse_performances_cache(performances: List[Dict]) -> Dict[str, List[Dict]]:
    """
    构建马匹往绩缓存
    输入：所有 past_performances_v2 记录
    输出：{ horse_id: [按日期降序排列的往绩列表] }
    """
    cache = {}
    
    for p in performances:
        horse_id = p.get('horse_id')
        if not horse_id:
            continue
        
        if horse_id not in cache:
            cache[horse_id] = []
        cache[horse_id].append(p)
    
    # 对每个马匹的往绩按 race_date 降序排序（最新的在前）
    for horse_id in cache:
        cache[horse_id].sort(key=lambda x: x.get('race_date', ''), reverse=True)
    
    return cache


def get_races_from_performances(performances: List[Dict]) -> List[Dict]:
    """
    从 performances 数据中提取唯一的赛事列表
    返回：[{ race_date, venue, race_no, distance (从第一匹马获取) }]
    """
    unique_races = {}
    
    for p in performances:
        key = f"{p['race_date']}_{p['venue']}_{p['race_no']}"
        if key not in unique_races:
            unique_races[key] = {
                "race_date": p['race_date'],
                "venue": p['venue'],
                "race_no": p['race_no'],
                "distance": p.get('distance', 1200)
            }
    
    # 按日期升序排序（从旧到新，便于时间旅行回测）
    races = list(unique_races.values())
    races.sort(key=lambda x: x['race_date'])
    
    return races


def calculate_basic_score_fast(past_performances_v2: List[Dict], target_distance: int) -> float:
    """
    快速计算基础评分（使用已获取的往绩数据，不查询数据库）
    用于回测场景，避免 N+1 查询问题
    """
    if not past_performances_v2:
        return 50.0
    
    # 取最近 10 场（已经是按日期降序排列）
    recent = past_performances_v2[:10]
    total = len(recent)
    if total == 0:
        return 50.0
    
    # 胜率、入Q率、入T率
    wins = sum(1 for p in recent if p.get('position') == 1)
    places = sum(1 for p in recent if p.get('position', 0) in [1, 2])
    shows = sum(1 for p in recent if p.get('position', 0) in [1, 2, 3])
    
    win_score = (wins / total) * 100
    place_score = (places / total) * 100
    show_score = (shows / total) * 100
    
    # 路程评分（考虑路程相似度）
    distance_scores = []
    for p in recent:
        p_distance = p.get('distance', 0)
        p_position = p.get('position', 0)
        
        if p_distance == 0:
            continue
        
        # 路程差异越小，权重越高
        distance_diff = abs(p_distance - target_distance)
        weight = 1.0 - min(0.7, distance_diff / 400)
        
        if p_position == 1:
            score = 100
        elif p_position == 2:
            score = 85
        elif p_position == 3:
            score = 70
        elif p_position <= 5:
            score = 55
        elif p_position <= 8:
            score = 40
        else:
            score = 25
        
        distance_scores.append(score * weight)
    
    distance_score = sum(distance_scores) / len(distance_scores) if distance_scores else 50.0
    
    # 综合评分（权重与 BASIC_SCORE_WEIGHTS 保持一致）
    total_score = win_score * 0.35 + place_score * 0.25 + show_score * 0.15 + distance_score * 0.25
    return round(total_score, 2)
#-------------
# ==================== ML 模型回测专用：时间滑窗训练 ====================

def prepare_training_data_by_date(
    cutoff_date: str,
    all_performances: List[Dict],
    horse_cache: Dict,
    incident_llm_map: Optional[Dict[str, float]] = None,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    准备截止到 cutoff_date 之前的训练数据
    使用18个因子（完整版，包含骑师、练马师、年龄、体重、事件、冲刺、新马标记）
    """
    from scoring_engine import get_ml_config
    
    ml_config = get_ml_config()
    recent_games = ml_config.get("recent_games", 60)
    top_n_horses = ml_config.get("top_n_horses", 4)
    
    X_list = []
    y_list = []
    group_weights = []
    
    # ==================== 1. 获取马匹出生年份（内存缓存） ====================
    horse_birth_years = load_horse_birth_years()
    
    # ==================== 2. 获取骑师胜率（Streamlit 缓存） ====================
    jockey_win_rates = get_cached_jockey_win_rates()
    
    # ==================== 3. 练马师基础评分 ====================
    trainer_base_scores = {
        "蔡約翰": 100, "大衛希斯": 95, "姚本輝": 90,
        "告東尼": 90, "羅富全": 85, "呂健威": 85,
        "沈集成": 80, "方嘉柏": 80, "伍鵬志": 80,
        "韋達": 75, "蘇偉賢": 70, "文家良": 70,
        "賀賢": 65, "鄭俊偉": 65, "葉楚航": 60,
        "徐雨石": 60, "黎昭昇": 60, "巫偉傑": 55,
        "廖康銘": 55, "游達榮": 55, "丁冠豪": 50,
    }
    
    # ==================== 4. 筛选 cutoff_date 之前的赛事 ====================
    past_races = [p for p in all_performances if p.get('race_date', '') < cutoff_date]

    if incident_llm_map is None:
        incident_llm_map = _build_incident_llm_map(
            [p.get("incident", "") for p in past_races if p.get("incident")]
        )
    
    # ==================== 5. 按赛事分组 ====================
    race_groups = {}
    for p in past_races:
        key = f"{p['race_date']}_{p['venue']}_{p['race_no']}"
        if key not in race_groups:
            race_groups[key] = []
        race_groups[key].append(p)
    
    # ==================== 6. 遍历每场赛事 ====================
    for race_key, runners_data in race_groups.items():
        if not runners_data:
            continue
        
        first_runner = runners_data[0]
        race_date = first_runner.get('race_date')
        venue = first_runner.get('venue', 'ST')
        distance = first_runner.get('distance', 1200)
        
        # 按名次排序
        sorted_runners = sorted(runners_data, key=lambda x: x.get('position', 99))
        
        # ==================== 分层训练：取前8名和后3名 ====================
        # 好马组：前3名（正例）
        good_runners = sorted_runners[:3]
        # 中马组：第4-8名（负例）
        medium_runners = sorted_runners[3:8] if len(sorted_runners) >= 8 else sorted_runners[3:]
        # 差马组：最后3名（负例，强化学习）
        bad_runners = sorted_runners[-3:] if len(sorted_runners) >= 3 else []
        
        # 合并所有需要训练的马匹
        all_train_runners = good_runners + medium_runners + bad_runners
        
        for r in all_train_runners:
            horse_id = r.get('horse_id')
            if not horse_id:
                continue
            
            position = r.get('position', 0)
            #----------
            # 确定分组标签（修正：标签必须为0,1,2连续整数）
            if position <= 3:
                group_label = 2      # 好马组（正例）
                group_weight = 1.5
            elif position <= 8:
                group_label = 1      # 中马组（负例）
                group_weight = 1.0
            else:
                group_label = 0      # 差马组（负例）
                group_weight = 0.8
            
            # 获取该马匹在 race_date 之前的往绩
            all_past = horse_cache.get(horse_id, [])
            past_before = [p for p in all_past if p.get('race_date', '') < race_date]
            past_before = past_before[:recent_games]
            
            # ========== 构建18个因子 ==========
            features = {}
            total = len(past_before)
            
            # ---- 1. 基础往绩因子 ----
            if total > 0:
                recent_3 = past_before[:3] if total >= 3 else past_before
                recent_5 = past_before[:5] if total >= 5 else past_before
                recent_10 = past_before[:10] if total >= 10 else past_before
                
                wins_3 = sum(1 for p in recent_3 if p.get('position') == 1)
                features['win_rate_3'] = wins_3 / len(recent_3) if recent_3 else 0
                
                wins_10 = sum(1 for p in recent_10 if p.get('position') == 1)
                features['win_rate_10'] = wins_10 / len(recent_10) if recent_10 else 0
                
                places_10 = sum(1 for p in recent_10 if p.get('position', 0) in [1, 2])
                features['place_rate_10'] = places_10 / len(recent_10) if recent_10 else 0
                
                shows_10 = sum(1 for p in recent_10 if p.get('position', 0) in [1, 2, 3])
                features['show_rate_10'] = shows_10 / len(recent_10) if recent_10 else 0
                
                wins_5 = sum(1 for p in recent_5 if p.get('position') == 1)
                features['win_rate_5'] = wins_5 / len(recent_5) if recent_5 else 0
                
                features['win_rate'] = features['win_rate_10']
                features['place_rate'] = features['place_rate_10']
                features['show_rate'] = features['show_rate_10']
                
                # 路程评分
                distance_scores = []
                for p in recent_10:
                    p_distance = p.get('distance', 0)
                    if p_distance == 0:
                        continue
                    diff = abs(p_distance - distance)
                    weight = 1.0 - min(0.7, diff / 400)
                    pos = p.get('position', 0)
                    if pos == 1:
                        score = 100
                    elif pos == 2:
                        score = 85
                    elif pos == 3:
                        score = 70
                    elif pos <= 5:
                        score = 55
                    elif pos <= 8:
                        score = 40
                    else:
                        score = 25
                    distance_scores.append(score * weight)
                features['distance_rating'] = sum(distance_scores) / len(distance_scores) if distance_scores else 0
                
                # 名次趋势
                positions = [p.get('position', 0) for p in recent_5 if p.get('position', 0) > 0]
                if len(positions) >= 2:
                    if len(positions) >= 3:
                        trend = (positions[-3] - positions[-1])
                    else:
                        trend = positions[-2] - positions[-1]
                    features['trend'] = max(-10, min(10, trend)) / 10
                else:
                    features['trend'] = 0
                
                weights = [p.get('actual_weight', 0) for p in past_before if p.get('actual_weight', 0) > 0]
                features['avg_weight'] = sum(weights) / len(weights) if weights else 0
            else:
                features['win_rate_3'] = 0
                features['win_rate_10'] = 0
                features['place_rate_10'] = 0
                features['show_rate_10'] = 0
                features['win_rate_5'] = 0
                features['win_rate'] = 0
                features['place_rate'] = 0
                features['show_rate'] = 0
                features['distance_rating'] = 0
                features['trend'] = 0
                features['avg_weight'] = 0
            
            # ---- 2. 场次因素 ----
            venue_perf = [p for p in past_before if p.get('venue') == venue]
            if venue_perf:
                venue_wins = sum(1 for p in venue_perf[:5] if p.get('position') == 1)
                features['same_course'] = venue_wins / len(venue_perf[:5]) if venue_perf[:5] else 0
            else:
                features['same_course'] = 0
            
            dist_perf = [p for p in past_before if p.get('distance') == distance]
            if dist_perf:
                dist_wins = sum(1 for p in dist_perf[:5] if p.get('position') == 1)
                features['same_distance'] = dist_wins / len(dist_perf[:5]) if dist_perf[:5] else 0
            else:
                features['same_distance'] = 0
            
            draw_val = r.get('draw', 0)
            if draw_val and draw_val > 0:
                features['draw'] = 100 - (draw_val - 1) * (80 / 13)
            else:
                features['draw'] = 0
            
            features['weight'] = r.get('actual_weight', 0) or 0
            
            # ---- 3. 赔率因素 ----
            odds_val = r.get('odds', 0)
            if odds_val and odds_val > 0:
                features['odds'] = min(100, max(0, 100 * (1 - (odds_val - 1) / 98)))
            else:
                features['odds'] = 0
            
            features['odds_trend'] = 0
            features['ev'] = 0
            
            # ---- 4. 状态因素（修复：从全部为0变为真实值） ----
            # ✅ 年龄因子
            birth_year = horse_birth_years.get(horse_id)
            if birth_year and birth_year > 0:
                try:
                    race_year = int(race_date[:4])
                    age = race_year - birth_year
                    if 4 <= age <= 5:
                        features['age'] = 100
                    elif age == 3 or age == 6:
                        features['age'] = 70
                    elif age == 2 or age == 7:
                        features['age'] = 50
                    elif age >= 8:
                        features['age'] = 30
                    else:
                        features['age'] = 40
                except:
                    features['age'] = 0
            else:
                features['age'] = 0
            
            # ✅ 体重变化
            current_weight = r.get('body_weight')
            if current_weight and current_weight > 0:
                last_weight = None
                for p in past_before:
                    w = p.get('body_weight')
                    if w and w > 0:
                        last_weight = w
                        break
                if last_weight and last_weight > 0:
                    change = abs(current_weight - last_weight)
                    if change <= 5:
                        features['weight_change'] = 100
                    elif change <= 10:
                        features['weight_change'] = 70
                    elif change <= 15:
                        features['weight_change'] = 40
                    else:
                        features['weight_change'] = 20
                else:
                    features['weight_change'] = 50
            else:
                features['weight_change'] = 50
            
            # ✅ 事件报告（规则 + LLM 缓存，与预测一致）
            features['incident'] = _incident_feature_score(r.get('incident', ''), incident_llm_map)
            
            # ✅ 冲刺能力
            running_pos = r.get('running_position', '')
            if running_pos and running_pos != '0' and running_pos != '---':
                positions = [int(c) for c in str(running_pos) if c.isdigit()]
                if len(positions) >= 2:
                    first_pos = positions[0]
                    last_pos = positions[-1]
                    improvement = first_pos - last_pos
                    if improvement >= 5:
                        features['burst'] = 95
                    elif improvement >= 3:
                        features['burst'] = 85
                    elif improvement >= 1:
                        features['burst'] = 70
                    elif improvement == 0:
                        features['burst'] = 60
                    else:
                        features['burst'] = 40
                else:
                    features['burst'] = 50
            else:
                features['burst'] = 50
            
            # ---- 5. 骑师和练马师（修复：从全部为0变为真实值） ----
            # ✅ 骑师
            jockey = r.get('jockey')
            if jockey:
                jockey_win_rate = jockey_win_rates.get(jockey, 0.12)
                features['jockey'] = jockey_win_rate * 100
                features['jockey_win_rate'] = jockey_win_rate * 100
            else:
                features['jockey'] = 0
                features['jockey_win_rate'] = 0
            
            # ✅ 练马师
            trainer = r.get('trainer')
            if trainer:
                features['trainer'] = trainer_base_scores.get(trainer, 50)
            else:
                features['trainer'] = 0
            
            # ---- 6. 额外字段 ----
            features['data_used_count'] = len(past_before)
            features['actual_weight'] = r.get('actual_weight', 0) or 0
            features['distance'] = distance
            
            # ---- 7. 新马标记（新增） ----
            new_horse_info = get_new_horse_info(horse_id, past_before, race_date)
            features['is_new_horse'] = 1 if new_horse_info['is_new'] else 0
            if new_horse_info['is_new']:
                if new_horse_info['type'] == 'PP':
                    features['new_horse_type'] = 1
                elif new_horse_info['type'] == 'PPG':
                    features['new_horse_type'] = 2
                elif new_horse_info['type'] == 'INT':
                    features['new_horse_type'] = 3
                else:
                    features['new_horse_type'] = 0
            else:
                features['new_horse_type'] = 0
            
            X_list.append(features)
            y_list.append(group_label)
            group_weights.append(group_weight)
    
    if len(X_list) < 50:
        return None, None
    
    X_df = pd.DataFrame(X_list).fillna(0)
    y_series = pd.Series(y_list)
    
    return X_df, y_series


#--------------------
def train_model_on_data(X_train: pd.DataFrame, y_train: pd.Series, model_type: str):
    """
    在指定数据上训练模型
    model_type: 'lightgbm', 'xgboost', 'ensemble'
    
    性能优化：n_estimators 从 100 降到 50，训练时间减半
    """
    if model_type == 'lightgbm' and LGB_AVAILABLE:
        model = lgb.LGBMClassifier(
            n_estimators=50,      # 从 100 降到 50
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            verbose=-1,
            subsample=0.8,        # 新增：每棵树使用 80% 样本，防止过拟合
            colsample_bytree=0.8  # 新增：每棵树使用 80% 特征
        )
        model.fit(X_train, y_train)
        return model
    
    elif model_type == 'xgboost' and XGB_AVAILABLE:
        model = xgb.XGBClassifier(
            n_estimators=50,      # 从 100 降到 50
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss',
            verbosity=0,
            subsample=0.8,        # 新增：每棵树使用 80% 样本
            colsample_bytree=0.8  # 新增：每棵树使用 80% 特征
        )
        model.fit(X_train, y_train)
        return model
    
    elif model_type == 'ensemble':
        # 集成模型：分别训练两个模型，返回字典
        lgb_model = None
        xgb_model = None
        
        if LGB_AVAILABLE:
            lgb_model = lgb.LGBMClassifier(
                n_estimators=50,   # 从 100 降到 50
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                verbose=-1,
                subsample=0.8,
                colsample_bytree=0.8
            )
            lgb_model.fit(X_train, y_train)
        
        if XGB_AVAILABLE:
            xgb_model = xgb.XGBClassifier(
                n_estimators=50,   # 从 100 降到 50
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss',
                verbosity=0,
                subsample=0.8,
                colsample_bytree=0.8
            )
            xgb_model.fit(X_train, y_train)
        
        return {'lightgbm': lgb_model, 'xgboost': xgb_model}
    
    return None

#-----------
def predict_with_model(model, features: Dict, model_type: str, return_all_probs: bool = False):
    """
    使用训练好的模型预测
    
    参数：
        model: 训练好的模型
        features: 特征字典
        model_type: 'lightgbm', 'xgboost', 'ensemble'
        return_all_probs: 是否返回所有类别概率（三分类时使用）
    
    返回：
        如果 return_all_probs=False: 返回获胜概率 (0-1)
        如果 return_all_probs=True: 返回 [差马组概率, 中马组概率, 好马组概率]
    """
    if model is None:
        if return_all_probs:
            return [0.33, 0.33, 0.34]
        return 0.5
    
    try:
        # 构建 DataFrame
        X_pred = pd.DataFrame([features]).fillna(0)
        
        # ⭐ 关键修复：确保特征顺序与模型训练时一致
        # LightGBM 和 XGBoost 都有 feature_names_in_ 属性
        if hasattr(model, 'feature_names_in_'):
            expected_features = list(model.feature_names_in_)
            # 确保所有特征都存在
            for col in expected_features:
                if col not in X_pred.columns:
                    X_pred[col] = 0
            # 按正确顺序排列
            X_pred = X_pred[expected_features]
        else:
            # 如果模型没有 feature_names_in_（集成模型或旧模型）
            # 尝试从 features 字典的键构建
            # 此时需要确保所有特征都存在
            pass
        
        if model_type == 'ensemble':
            # 集成模型：分别预测，然后平均
            all_probs = []
            for sub_model in [model.get('lightgbm'), model.get('xgboost')]:
                if sub_model is not None:
                    try:
                        # 对子模型也应用特征对齐
                        if hasattr(sub_model, 'feature_names_in_'):
                            sub_X = X_pred[list(sub_model.feature_names_in_)]
                        else:
                            sub_X = X_pred
                        prob = sub_model.predict_proba(sub_X)[0]
                        all_probs.append(prob)
                    except Exception as e:
                        print(f"子模型预测失败: {e}")
                        continue
            
            if not all_probs:
                if return_all_probs:
                    return [0.33, 0.33, 0.34]
                return 0.5
            
            # 平均所有子模型的概率
            avg_probs = np.mean(all_probs, axis=0)
            
            if return_all_probs:
                return avg_probs.tolist()
            else:
                if len(avg_probs) >= 3:
                    return avg_probs[2]  # 好马组
                else:
                    return avg_probs[1]  # 正类概率
        
        else:
            # 单模型
            probs = model.predict_proba(X_pred)[0]
            if return_all_probs:
                return probs.tolist()
            else:
                if len(probs) >= 3:
                    return probs[2]  # 好马组（类别2）
                else:
                    return probs[1]  # 正类概率
                
    except Exception as e:
        print(f"预测失败: {e}")
        # 打印特征数量便于调试
        print(f"  特征数量: {len(features)}")
        print(f"  特征列表: {list(features.keys())}")
        if return_all_probs:
            return [0.33, 0.33, 0.34]
        return 0.5
#-----------
# ==================== ML 模型缓存 ====================

_model_cache = {}
#---------
def get_or_train_model(X_train, y_train, model_type: str, cache_key: str):
    """
    获取或训练模型（带缓存）
    参数：
        X_train: 训练特征
        y_train: 训练标签
        model_type: 'lightgbm', 'xgboost', 'ensemble'
        cache_key: 唯一缓存键（应包含模型类型）
    返回：
        训练好的模型
    """
    global _model_cache
    
    # ⭐ 关键修复：缓存键必须包含模型类型（防止LightGBM和XGBoost共用）
    # 如果 cache_key 没有以模型类型开头，强制添加
    if not cache_key.startswith(model_type):
        cache_key = f"{model_type}_{cache_key}"
    
    # ⭐ 如果是集成模型，使用独立的缓存键格式
    if model_type == 'ensemble':
        lgb_key = f"lightgbm_{cache_key.replace('ensemble_', '')}"
        xgb_key = f"xgboost_{cache_key.replace('ensemble_', '')}"
        
        lgb_model = get_or_train_model(X_train, y_train, 'lightgbm', lgb_key)
        xgb_model = get_or_train_model(X_train, y_train, 'xgboost', xgb_key)
        
        return {'lightgbm': lgb_model, 'xgboost': xgb_model}
    
    # 检查缓存
    if cache_key in _model_cache:
        print(f"✅ 缓存命中: {cache_key}")
        return _model_cache[cache_key]
    
    # 训练新模型
    print(f"🔄 训练新模型: {cache_key}")
    
    from scoring_engine import get_ml_config
    config = get_ml_config()
    
    # ==================== LightGBM 训练 ====================
    if model_type == 'lightgbm' and LGB_AVAILABLE:
        # 检查标签是否是三分类
        unique_labels = sorted(y_train.unique())
        num_classes = len(unique_labels)
        
        if num_classes >= 3:
            # 三分类
            model = lgb.LGBMClassifier(
                n_estimators=config.get("lgb_n_estimators", 50),
                max_depth=config.get("lgb_max_depth", 4),
                learning_rate=config.get("lgb_learning_rate", 0.1),
                num_leaves=config.get("lgb_num_leaves", 16),
                random_state=42,
                verbose=-1,
                subsample=config.get("lgb_subsample", 0.7),
                colsample_bytree=config.get("lgb_colsample_bytree", 0.7),
                objective='multiclass',
                num_class=3
            )
        else:
            # 二分类
            model = lgb.LGBMClassifier(
                n_estimators=config.get("lgb_n_estimators", 50),
                max_depth=config.get("lgb_max_depth", 4),
                learning_rate=config.get("lgb_learning_rate", 0.1),
                num_leaves=config.get("lgb_num_leaves", 16),
                random_state=42,
                verbose=-1,
                subsample=config.get("lgb_subsample", 0.7),
                colsample_bytree=config.get("lgb_colsample_bytree", 0.7)
            )
        
        model.fit(X_train, y_train)
    
    # ==================== XGBoost 训练 ====================
    elif model_type == 'xgboost' and XGB_AVAILABLE:
        # 检查标签是否是三分类
        unique_labels = sorted(y_train.unique())
        num_classes = len(unique_labels)
        
        if num_classes >= 3:
            # 三分类
            model = xgb.XGBClassifier(
                n_estimators=config.get("xgb_n_estimators", 120),
                max_depth=config.get("xgb_max_depth", 4),
                learning_rate=config.get("xgb_learning_rate", 0.06),
                random_state=42,
                use_label_encoder=False,
                eval_metric='mlogloss',
                verbosity=0,
                subsample=config.get("xgb_subsample", 0.7),
                colsample_bytree=config.get("xgb_colsample_bytree", 0.7),
                objective='multi:softprob',
                num_class=3
            )
        else:
            # 二分类
            model = xgb.XGBClassifier(
                n_estimators=config.get("xgb_n_estimators", 120),
                max_depth=config.get("xgb_max_depth", 4),
                learning_rate=config.get("xgb_learning_rate", 0.06),
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss',
                verbosity=0,
                subsample=config.get("xgb_subsample", 0.7),
                colsample_bytree=config.get("xgb_colsample_bytree", 0.7)
            )
        
        model.fit(X_train, y_train)
    
    # ==================== 其他情况 ====================
    else:
        return None
    
    # 保存到缓存
    if model is not None:
        _model_cache[cache_key] = model
        print(f"✅ 模型已缓存: {cache_key}")
    
    return model


def clear_model_cache():
    """清空所有模型缓存（管理员强制刷新时使用）"""
    global _model_cache
    _model_cache = {}
    print("🗑️ 模型缓存已清空")


def get_model_cache_keys():
    """获取当前缓存的所有键（用于调试）"""
    return list(_model_cache.keys())


def _prepare_ml_runners_for_strategy(
    runners_data: List[Dict],
    race_date: str,
    venue: str,
    race_no: int,
    model_type: str,
    model,
    perf_cache: Optional[Dict[str, List[Dict]]] = None,
    incident_llm_map: Optional[Dict[str, float]] = None,
) -> List[Dict]:
    """为策略回测准备带 ML 胜率与赔率的出马列表。"""
    ml_probs = get_model_predictions(
        race_date, venue, race_no, runners_data, model_type, model,
        perf_cache=perf_cache,
        incident_llm_map=incident_llm_map,
    )
    prepared = []
    for i, row in enumerate(runners_data):
        item = dict(row)
        item["horse_name"] = resolve_horse_name(row)
        prob = ml_probs[i] if i < len(ml_probs) else 0.34
        item["win_probability"] = prob
        item["overall_score"] = prob * 100
        item["odds_win"] = row.get("odds")
        prepared.append(item)
    return prepared


def run_strategy_backtest(
    start_date: str,
    end_date: str,
    model_type: str,
    strategy_kind: str,
    min_ev_threshold: float = 0.10,
    stake_per_bet: float = 100,
) -> "BacktestSummary":
    """
    策略回测（时间滑窗 + EV 门槛）
    model_type: lightgbm | xgboost
    strategy_kind: win | qin
    """
    if not STRATEGY_BACKTEST_OK:
        st.error(f"策略回测模块加载失败: {STRATEGY_BACKTEST_IMPORT_ERROR}")
        return None

    model_label = "LightGBM" if model_type == "lightgbm" else "XGBoost"
    supabase_headers = get_supabase_headers(use_secret=True)
    backtester = StrategyBacktester(SUPABASE_URL, supabase_headers)
    diagnostics = BacktestDiagnostics()
    results = []

    if model_type == "lightgbm" and not LGB_AVAILABLE:
        st.error("LightGBM 未安装，请运行 pip install lightgbm")
        return BacktestSummary(model_name=model_label, diagnostics=diagnostics)
    if model_type == "xgboost" and not XGB_AVAILABLE:
        st.error("XGBoost 未安装，请运行 pip install xgboost")
        return BacktestSummary(model_name=model_label, diagnostics=diagnostics)

    all_performances = get_performances_batch(start_date, end_date)
    if not all_performances:
        st.error("未獲取到任何數據")
        return BacktestSummary(model_name=model_label, diagnostics=diagnostics)

    incident_llm_map = _build_incident_llm_map(
        [p.get("incident", "") for p in all_performances if p.get("incident")]
    )

    horse_cache = build_horse_performances_cache(all_performances)
    races = get_races_from_performances(all_performances)
    if not races:
        st.warning("未找到任何賽事")
        return BacktestSummary(model_name=model_label, diagnostics=diagnostics)

    races_by_date: Dict[str, List[Dict]] = {}
    for race in races:
        races_by_date.setdefault(race["race_date"], []).append(race)
    sorted_dates = sorted(races_by_date.keys())

    progress_bar = st.progress(0)
    status_text = st.empty()

    from scoring_engine import get_cached_model, get_current_weights_hash, set_cached_model

    weight_hash = get_current_weights_hash()

    for idx, current_date in enumerate(sorted_dates):
        if st.session_state.get("stop_backtest", False):
            st.warning("⚠️ 回測已被用戶取消")
            break

        status_text.text(f"策略回測 {model_label}: {current_date} ({idx + 1}/{len(sorted_dates)})")
        progress_bar.progress((idx + 1) / len(sorted_dates))

        train_X, train_y = prepare_training_data_by_date(
            current_date, all_performances, horse_cache, incident_llm_map=incident_llm_map
        )
        if train_X is None or len(train_X) < 50:
            continue

        cache_key = f"strategy_{model_type}_{current_date}_{weight_hash}"
        cached_model = get_cached_model(cache_key)
        if cached_model is not None:
            model = cached_model
        else:
            model = get_or_train_model(train_X, train_y, model_type, cache_key)
            if model is not None:
                set_cached_model(cache_key, model)
        if model is None:
            continue

        for race in races_by_date[current_date]:
            diagnostics.total_races += 1
            race_date = race["race_date"]
            venue = race["venue"]
            race_no = race["race_no"]

            runners_data = [
                p for p in all_performances
                if p["race_date"] == race_date and p["venue"] == venue and p["race_no"] == race_no
            ]
            if not runners_data:
                diagnostics.skipped_no_runners += 1
                continue

            ml_runners = _prepare_ml_runners_for_strategy(
                runners_data, race_date, venue, race_no, model_type, model,
                incident_llm_map=incident_llm_map,
            )
            win_odds_snapshot = fetch_win_odds_snapshot(
                race_date, venue, race_no, SUPABASE_URL, supabase_headers
            )

            if strategy_kind == "win":
                bet_result, reason = backtester.evaluate_win_race(
                    race_date,
                    venue,
                    race_no,
                    ml_runners,
                    min_ev_threshold,
                    stake_per_bet,
                    model_label,
                    win_odds_snapshot,
                )
            else:
                bet_result, reason, estimated = backtester.evaluate_qin_race(
                    race_date,
                    venue,
                    race_no,
                    ml_runners,
                    min_ev_threshold,
                    stake_per_bet,
                    model_label,
                    win_odds_snapshot,
                )

            if reason == "no_runners":
                diagnostics.skipped_no_runners += 1
            elif reason == "no_odds":
                diagnostics.skipped_no_odds += 1
            elif reason == "ev_below":
                diagnostics.skipped_ev_below += 1
            elif reason == "no_result":
                diagnostics.skipped_no_result += 1
            elif reason == "bet" and bet_result is not None:
                diagnostics.bet_races += 1
                results.append(bet_result)

    progress_bar.empty()
    status_text.empty()

    summary = backtester.build_summary(results, diagnostics, stake_per_bet, model_label)
    if summary.total_bets == 0:
        st.info(
            f"共分析 {diagnostics.total_races} 場："
            f"EV不足 {diagnostics.skipped_ev_below} 場，"
            f"缺赔率 {diagnostics.skipped_no_odds} 場，"
            f"缺赛果 {diagnostics.skipped_no_result} 場。"
            + (" 连赢赔率部分场次为估算值。" if strategy_kind == "qin" else "")
        )
    return summary


def _build_incident_llm_map(incident_texts: List[str]) -> Dict[str, float]:
    """预读 incident LLM 缓存（不调用 API）。"""
    if not INCIDENT_LLM_OK or not SUPABASE_URL:
        return {}
    headers = get_supabase_headers(use_secret=True)
    if build_incident_llm_map_from_texts:
        return build_incident_llm_map_from_texts(incident_texts, SUPABASE_URL, headers)
    mapping: Dict[str, float] = {}
    for text in set(t for t in incident_texts if t):
        mapping[text] = get_llm_impact_from_cache(text, SUPABASE_URL, headers)
    return mapping


def _incident_feature_score(
    incident_text: str,
    incident_llm_map: Optional[Dict[str, float]] = None,
) -> float:
    """规则 + 0.5×LLM 缓存分（-20~+20），与 ML 预测/训练一致。"""
    if incident_combined_feature_score:
        headers = get_supabase_headers(use_secret=True) if SUPABASE_URL else None
        return incident_combined_feature_score(
            incident_text,
            incident_llm_map=incident_llm_map,
            supabase_url=SUPABASE_URL or "",
            headers=headers,
        )
    if get_combined_incident_adjustment and SUPABASE_URL:
        combined, _, _ = get_combined_incident_adjustment(
            incident_text,
            SUPABASE_URL,
            get_supabase_headers(use_secret=True),
            incident_llm_map=incident_llm_map,
        )
        return combined
    return calculate_incident_score(incident_text)


def _group_race_days(races: List[Dict]) -> Dict[Tuple[str, str], List[Dict]]:
    days: Dict[Tuple[str, str], List[Dict]] = {}
    for race in races:
        key = (race["race_date"], race.get("venue", "ST"))
        days.setdefault(key, []).append(race)
    return days


def _score_races_for_day_ml(
    day_races: List[Dict],
    all_performances: List[Dict],
    model_type: str,
    model,
    horse_cache: Optional[Dict[str, List[Dict]]] = None,
    incident_llm_map: Optional[Dict[str, float]] = None,
) -> Dict[int, List[Dict]]:
    scored: Dict[int, List[Dict]] = {}
    for race in day_races:
        race_date = race["race_date"]
        venue = race["venue"]
        race_no = race["race_no"]
        runners_data = race.get("_runners_data")
        if runners_data is None:
            runners_data = [
                p for p in all_performances
                if p["race_date"] == race_date and p["venue"] == venue and p["race_no"] == race_no
            ]
        if not runners_data:
            continue
        ml_runners = _prepare_ml_runners_for_strategy(
            runners_data, race_date, venue, race_no, model_type, model,
            perf_cache=horse_cache,
            incident_llm_map=incident_llm_map,
        )
        scored[race_no] = ml_runners
    return scored


def run_day_portfolio_backtest(
    start_date: str,
    end_date: str,
    model_type: str = "lightgbm",
    budget_per_day: float = 1000.0,
    min_ev: float = 0.0,
    fast_mode: bool = False,
) -> Dict:
    """
    赛日组合策略回测：每日 ~$1000 在 WIN/PLA/QIN/TRI/TCE/孖宝 间优化分配。
    fast_mode=True 时每周重训一次模型（快速模式）。
    """
    if not DAY_PORTFOLIO_OK:
        st.error(f"{t()['day_portfolio_import_failed']}: {DAY_PORTFOLIO_IMPORT_ERROR}")
        return {}

    model_label = "LightGBM" if model_type == "lightgbm" else "XGBoost"
    if model_type == "lightgbm" and not LGB_AVAILABLE:
        st.error(t()["lightgbm_not_installed"])
        return {}
    if model_type == "xgboost" and not XGB_AVAILABLE:
        st.error(t()["xgboost_not_installed"])
        return {}

    all_performances = get_performances_batch(start_date, end_date)
    if not all_performances:
        st.error(t()["no_data_fetched"])
        return {}

    incident_texts = [p.get("incident", "") for p in all_performances if p.get("incident")]
    incident_llm_map = _build_incident_llm_map(incident_texts)

    horse_cache = build_horse_performances_cache(all_performances)
    races = get_races_from_performances(all_performances)
    if not races:
        st.warning(t()["no_races_found"])
        return {}

    race_days = _group_race_days(races)
    sorted_day_keys = sorted(race_days.keys())
    optimizer = DayPortfolioOptimizer(
        min_stake=10.0,
        min_ev=min_ev,
        max_candidates=50,
    )

    from scoring_engine import get_cached_model, get_current_weights_hash, set_cached_model

    weight_hash = get_current_weights_hash()
    progress_bar = st.progress(0)
    status_text = st.empty()

    day_results: List[DayPortfolioResult] = []
    total_stake = 0.0
    total_return = 0.0
    total_bets = 0
    total_hits = 0
    model = None
    last_train_key = None

    for idx, (race_date, venue) in enumerate(sorted_day_keys):
        if st.session_state.get("stop_backtest", False):
            st.warning(t()["backtest_cancelled"])
            break

        status_text.text(t()["day_portfolio_backtest_progress"].format(
            model=model_label, date=race_date, venue=venue,
            current=idx + 1, total=len(sorted_day_keys),
        ))
        progress_bar.progress((idx + 1) / len(sorted_day_keys))

        train_key = race_date
        if fast_mode:
            train_key = race_date[:7]

        if model is None or train_key != last_train_key:
            train_X, train_y = prepare_training_data_by_date(
                race_date, all_performances, horse_cache, incident_llm_map=incident_llm_map
            )
            if train_X is None or len(train_X) < 50:
                continue
            cache_key = f"portfolio_{model_type}_{train_key}_{weight_hash}"
            cached = get_cached_model(cache_key)
            if cached is not None:
                model = cached
            else:
                model = get_or_train_model(train_X, train_y, model_type, cache_key)
                if model is not None:
                    set_cached_model(cache_key, model)
            last_train_key = train_key

        if model is None:
            continue

        day_races = race_days[(race_date, venue)]
        scored_by_race = _score_races_for_day_ml(day_races, all_performances, model_type, model, incident_llm_map=incident_llm_map)
        for race_no, runners in scored_by_race.items():
            for row in runners:
                row["horse_name"] = resolve_horse_name(row)
        day_performances = [
            p for p in all_performances if p.get("race_date") == race_date and p.get("venue") == venue
        ]
        portfolio_races = build_race_day_races_from_performances(
            race_date, venue, day_performances, scored_by_race
        )
        if not portfolio_races:
            continue

        day_result = optimizer.optimize_day(race_date, venue, portfolio_races, budget_per_day)
        optimizer.settle_day(day_result, portfolio_races)
        day_results.append(day_result)
        total_stake += day_result.total_stake
        total_return += day_result.total_return
        total_bets += day_result.bet_count
        total_hits += day_result.hit_count

    progress_bar.empty()
    status_text.empty()

    roi = (total_return - total_stake) / total_stake * 100 if total_stake > 0 else 0.0
    hit_rate = total_hits / total_bets * 100 if total_bets > 0 else 0.0

    return {
        "model": model_label,
        "day_count": len(day_results),
        "total_stake": round(total_stake, 2),
        "total_return": round(total_return, 2),
        "roi": round(roi, 2),
        "hit_rate": round(hit_rate, 2),
        "total_bets": total_bets,
        "total_hits": total_hits,
        "day_results": day_results,
        "fast_mode": fast_mode,
    }


def build_live_day_portfolio(
    races: List[Dict],
    model_choice: str,
    budget: float,
    min_ev: float = 0.0,
    prediction_cutoff_date: Optional[str] = None,
    user_weights: Optional[Dict] = None,
    weights_config: Optional[Dict] = None,
    incident_llm_map: Optional[Dict[str, float]] = None,
) -> Optional[DayPortfolioResult]:
    """智能投注：生成当日最优组合（约 budget）。"""
    if not DAY_PORTFOLIO_OK or not races:
        return None

    ml_model = None
    ml_model_type = None
    if model_choice != "评分系统":
        ml_model_type, ml_model = get_smart_betting_ml_model(model_choice, prediction_cutoff_date)
        if ml_model is None:
            return None

    optimizer = DayPortfolioOptimizer(
        min_stake=10.0,
        min_ev=min_ev,
        max_candidates=50,
    )
    scored_by_race: Dict[int, List[Dict]] = {}

    for race in races:
        race_runners = _score_runners_for_parlay_race(
            race,
            model_choice,
            user_weights or {},
            weights_config,
            ml_model,
            ml_model_type,
            prediction_cutoff_date,
            incident_llm_map=incident_llm_map,
        )
        if race_runners:
            scored_by_race[race.get("race_no")] = race_runners

    if not scored_by_race:
        return None

    race_date = races[0].get("race_date", "")
    venue = races[0].get("venue", "ST")
    portfolio_races = build_race_day_races_from_performances(
        race_date, venue, [], scored_by_race
    )
    for pr in portfolio_races:
        pr.actual_top3 = None

    return optimizer.optimize_day(race_date, venue, portfolio_races, budget)


def _display_day_portfolio_backtest_summary(result: Dict) -> None:
    if not result:
        return
    st.markdown(f"#### {t()['day_portfolio_backtest_title'].format(model=result.get('model', ''))}")
    mode_label = t()["day_portfolio_mode_fast"] if result.get("fast_mode") else t()["day_portfolio_mode_std"]
    st.caption(t()["day_portfolio_backtest_caption"].format(mode=mode_label, days=result.get("day_count", 0)))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(t()["metric_day_count"], result.get("day_count", 0))
        st.metric(t()["metric_total_bets"], result.get("total_bets", 0))
    with c2:
        st.metric(t()["metric_hit_bets"], result.get("total_hits", 0))
        st.metric(t()["metric_hit_rate"], f"{result.get('hit_rate', 0):.1f}%")
    with c3:
        st.metric(t()["metric_total_stake"], f"${result.get('total_stake', 0):,.0f}")
        st.metric(t()["metric_total_return"], f"${result.get('total_return', 0):,.0f}")
    with c4:
        roi = result.get("roi", 0)
        st.metric("ROI", f"{'🟢' if roi > 0 else '🔴'} {roi:+.1f}%")

    rows = []
    for day in result.get("day_results", []):
        for bet in day.bets:
            c = bet.candidate
            rows.append({
                t()["col_race_day"]: day.race_date,
                t()["col_venue"]: day.venue,
                t()["col_pool"]: c.pool,
                t()["col_content"]: c.description,
                t()["col_odds"]: f"{c.odds:.1f}",
                t()["col_estimated"]: t()["col_yes"] if c.odds_estimated else t()["col_no"],
                t()["ev"]: f"{c.ev:+.2f}",
                t()["col_stake"]: f"${bet.stake:.0f}",
                t()["col_hit"]: "✅" if bet.actual_hit else "❌",
                t()["col_return"]: f"${bet.actual_return or 0:.0f}",
                t()["col_profit"]: f"${bet.profit or 0:+.0f}",
            })
    if rows:
        with st.expander(t()["portfolio_bet_details"], expanded=False):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _display_live_day_portfolio(result: DayPortfolioResult, budget: float) -> None:
    if not result or not result.bets:
        st.warning(t()["no_day_portfolio_bets"])
        return
    st.markdown(f"#### {t()['day_portfolio_live_title']}")
    st.caption(t()["day_portfolio_live_caption"].format(budget=budget, stake=result.total_stake))
    rows = []
    for bet in result.bets:
        c = bet.candidate
        rows.append({
            t()["col_pool"]: c.pool,
            t()["col_recommendation"]: c.description,
            t()["col_odds"]: f"{c.odds:.1f}{'*' if c.odds_estimated else ''}",
            t()["col_probability"]: f"{c.probability * 100:.1f}%",
            t()["ev"]: f"{c.ev:+.2f}",
            t()["col_suggested_stake"]: f"HK${bet.stake:.0f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(t()["estimated_odds_footnote"])


#----------
def run_ml_backtest(start_date: str, end_date: str, model_type: str, force_refresh: bool = False) -> Dict:
    """
    ML 模型回测（时间滑窗版本 + 修正指标）
    - 使用截止日期前的数据训练模型
    - 预测该日期当天的赛事
    - 滚动进行，确保无数据泄露
    - 包含训练进度提示
    
    参数：
        start_date: 开始日期
        end_date: 结束日期
        model_type: 'lightgbm' | 'xgboost' | 'ensemble'
        force_refresh: 是否强制刷新（忽略缓存）
    
    返回：
        回测结果字典
    """
    # ⭐ 如果是强制刷新，清空缓存
    if force_refresh:
        from scoring_engine import clear_model_cache
        clear_model_cache()
        print(f"🗑️ 已清空所有模型缓存")
    #-----------
    result = {
    "模型": "LightGBM" if model_type == "lightgbm" else "XGBoost" if model_type == "xgboost" else "集成模型",
    "测试场次": 0,
    "预测正确": 0,
    "前三名命中匹数": 0,
    "前三名命中场次": 0,
    "前三名全中场次": 0,
    "前三名顺序正确场次": 0,
    "独赢正确率": 0,
    "前三名命中匹数率": 0,
    "前三名命中场次率": 0,
    "前三名全中率": 0,
    "前三名顺序正确率": 0,
    "总投入": 0,
    "总回报": 0,
    "ROI": 0,
    # 新增：位置投注统计
    "位置总投入": 0,
    "位置总回报": 0,
    "位置ROI": 0,
    "debug_details": [],
    "cancelled": False,
    "model": None,
    "feature_importance": None,
    "feature_names": None,
    "from_cache": False,
}
    
    try:
        lang = get_lang()
        texts = t()
        # 1. 批量获取所有数据
        with st.spinner(texts["ml_loading_data"].format(start=start_date, end=end_date)):
            all_performances = get_performances_batch(start_date, end_date)
        
        if not all_performances:
            st.error(texts["ml_no_data"])
            return result
        
        # 2. 构建马匹往绩缓存
        horse_cache = build_horse_performances_cache(all_performances)
        incident_llm_map = _build_incident_llm_map(
            [p.get("incident", "") for p in all_performances if p.get("incident")]
        )
        print(f"📊 构建马匹缓存: {len(horse_cache)} 匹马")
        
        # 3. 获取按日期排序的赛事列表
        races = get_races_from_performances(all_performances)
        result["测试场次"] = len(races)
        
        if result["测试场次"] == 0:
            return result
        
        # 4. 按日期分组赛事（便于按天训练）
        races_by_date = {}
        for race in races:
            date = race['race_date']
            if date not in races_by_date:
                races_by_date[date] = []
            races_by_date[date].append(race)
        
        # 5. 按日期排序
        sorted_dates = sorted(races_by_date.keys())
        
        # 6. 初始化统计变量
        correct_predictions = 0           # 独赢正确场次
        total_top3_hits = 0               # 前三名累计命中匹数
        total_top3_hit_races = 0          # 前三名至少命中1匹的场次
        total_tri_correct = 0             # 前三名全中场次（不限顺序）
        total_tce_correct = 0             # 前三名顺序正确场次
        total_stake = 0                   # 独赢总投入（保留兼容）
        total_return = 0                  # 独赢总回报（保留兼容）
        
        # 独赢投注统计（新增）
        total_win_stake = 0
        total_win_return = 0
        
        # 位置投注统计（新增）
        total_position_stake = 0
        total_position_return = 0
        
        # 7. 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # ⭐ 用于保存最后一个模型（供特征重要性分析）
        last_model = None
        last_feature_names = None
        
        # 8. 时间滑窗回测
        for idx, current_date in enumerate(sorted_dates):
            # 取消检查点
            if st.session_state.get("stop_backtest", False):
                st.warning(texts["backtest_cancelled"])
                result["cancelled"] = True
                break
            
            status_text.text(
                texts["ml_processing_date"].format(
                    date=current_date, current=idx + 1, total=len(sorted_dates)
                )
            )
            progress_bar.progress((idx + 1) / len(sorted_dates))
            
            # 8.1 使用 current_date 之前的所有数据训练模型
            status_text.text(texts["ml_preparing_train"].format(date=current_date))
            #----------
            train_X, train_y = prepare_training_data_by_date(
                current_date, all_performances, horse_cache, incident_llm_map=incident_llm_map
            )
            
            if train_X is None or len(train_X) < 50:
                status_text.text(
                    texts["ml_insufficient_train"].format(
                        date=current_date,
                        count=len(train_X) if train_X is not None else 0,
                    )
                )
                continue
            
            # 显示训练数据量
            status_text.text(
                texts["ml_training"].format(
                    date=current_date,
                    count=len(train_X),
                    model=display_model_choice(result["模型"]),
                )
            )
            
            # ⭐ 生成缓存键（包含模型类型）
            import hashlib
            
            # 获取权重哈希
            from scoring_engine import get_current_weights_hash
            weight_hash = get_current_weights_hash()
            
            # ⭐ 明确包含模型类型，防止LightGBM和XGBoost共用缓存
            cache_key = f"{model_type}_{start_date}_{end_date}_{weight_hash}"
            print(f"🔑 缓存键: {cache_key}")
            print(f"🔑 [run_ml_backtest] 模型: {model_type}, 缓存键: {cache_key}")  # ← 添加这行
            # 尝试从缓存获取模型
            from scoring_engine import get_cached_model, set_cached_model
            cached_model = get_cached_model(cache_key)
            
            if cached_model is not None and not force_refresh:
                # ✅ 缓存命中
                model = cached_model
                print(f"✅ 使用缓存模型: {cache_key}")
                result["from_cache"] = True
            else:
                # ⭐ 训练新模型
                print(f"🔄 训练新模型: {cache_key}")
                model = get_or_train_model(train_X, train_y, model_type, cache_key)
                # 保存到缓存
                if model is not None:
                    set_cached_model(cache_key, model)
                    result["from_cache"] = False
            
            # ⭐ 保存模型信息（用于后续特征重要性提取）
            if model is not None:
                last_model = model
                if train_X is not None and hasattr(train_X, 'columns'):
                    last_feature_names = list(train_X.columns)
                    print(f"✅ 保存特征名称: {len(last_feature_names)} 个因子")
                    
                    # ⭐ 新增：保存训练数据供 SHAP 使用
                    st.session_state.admin_shap_train_data = {
                        'X_sample': train_X,
                        'feature_names': last_feature_names
                    }
                    print(f"✅ 保存训练数据供 SHAP 使用: {len(train_X)} 行")
                else:
                    last_feature_names = []
                    print(f"⚠️ train_X 无效，特征名称为空")
            #--------------
            if model is None:
                status_text.text(texts["ml_train_failed"].format(date=current_date))
                continue
            #-------------
            # ============================================================
            # 获取预测所需的辅助数据（骑师胜率、练马师评分、马匹出生年份）
            # ============================================================
            
            # 获取骑师胜率
            jockey_win_rates = get_jockey_win_rates_from_db()
            
            # 练马师基础评分
            trainer_base_scores = {
                "蔡約翰": 100, "大衛希斯": 95, "姚本輝": 90,
                "告東尼": 90, "羅富全": 85, "呂健威": 85,
                "沈集成": 80, "方嘉柏": 80, "伍鵬志": 80,
                "韋達": 75, "蘇偉賢": 70, "文家良": 70,
                "賀賢": 65, "鄭俊偉": 65, "葉楚航": 60,
                "徐雨石": 60, "黎昭昇": 60, "巫偉傑": 55,
                "廖康銘": 55, "游達榮": 55, "丁冠豪": 50,
            }
            
            # 获取马匹出生年份
            horse_birth_years = {}
            try:
                headers = get_supabase_headers(use_secret=True)
                horses_url = f"{SUPABASE_URL}/rest/v1/horses_v2?select=horse_id,birth_year"
                response = requests.get(horses_url, headers=headers)
                if response.status_code == 200:
                    for h in response.json():
                        horse_birth_years[h.get('horse_id')] = h.get('birth_year')
            except Exception as e:
                print(f"获取马匹出生年份失败: {e}")
            # ============================================================
            # 8.2 预测 current_date 当天的所有赛事
            # ============================================================
            for race in races_by_date[current_date]:
                # 内层循环取消检查点
                if st.session_state.get("stop_backtest", False):
                    break
                
                race_date = race['race_date']
                venue = race['venue']
                race_no = race['race_no']
                distance = race.get('distance', 1200)
                
                # 获取该场赛事的出赛马匹
                runners_data = [p for p in all_performances 
                               if p['race_date'] == race_date 
                               and p['venue'] == venue 
                               and p['race_no'] == race_no]
                
                if not runners_data:
                    continue
                
                # 预测所有马匹
                from scoring_engine import get_ml_config
                ml_config = get_ml_config()
                recent_games = ml_config.get("recent_games", 30)
                
                # 构建特征并预测 - 对所有马匹进行预测
                runners = []
                name_lookup = get_horses_name_lookup() if lang == "en" else None
                
                for r in runners_data:
                    horse_id = r.get('horse_id')
                    if not horse_id:
                        continue
                    
                    horse_name = r.get('horse_name', '')
                    horse_name_en = r.get('horse_name_en', '') or ''
                    if not horse_name_en and name_lookup:
                        horse_name_en = name_lookup.get(str(horse_id), {}).get("name_en", "")
                    
                    # 获取该马匹在 race_date 之前的往绩
                    all_past = horse_cache.get(horse_id, [])
                    past_before = [p for p in all_past if p.get('race_date', '') < race_date]
                    past_before = past_before[:recent_games]
                    
                    # ========== 构建18个因子（与训练一致）==========
                    features = {}
                    
                    # ---- 1. 基础往绩因子 ----
                    total = len(past_before)
                    if total > 0:
                        recent_3 = past_before[:3] if total >= 3 else past_before
                        recent_5 = past_before[:5] if total >= 5 else past_before
                        recent_10 = past_before[:10] if total >= 10 else past_before
                        
                        wins_3 = sum(1 for p in recent_3 if p.get('position') == 1)
                        features['win_rate_3'] = wins_3 / len(recent_3) if recent_3 else 0
                        
                        wins_10 = sum(1 for p in recent_10 if p.get('position') == 1)
                        features['win_rate_10'] = wins_10 / len(recent_10) if recent_10 else 0
                        
                        places_10 = sum(1 for p in recent_10 if p.get('position', 0) in [1, 2])
                        features['place_rate_10'] = places_10 / len(recent_10) if recent_10 else 0
                        
                        shows_10 = sum(1 for p in recent_10 if p.get('position', 0) in [1, 2, 3])
                        features['show_rate_10'] = shows_10 / len(recent_10) if recent_10 else 0
                        
                        wins_5 = sum(1 for p in recent_5 if p.get('position') == 1)
                        features['win_rate_5'] = wins_5 / len(recent_5) if recent_5 else 0
                        
                        features['win_rate'] = features['win_rate_10']
                        features['place_rate'] = features['place_rate_10']
                        features['show_rate'] = features['show_rate_10']
                        
                        distance_scores = []
                        for p in recent_10:
                            p_distance = p.get('distance', 0)
                            if p_distance == 0:
                                continue
                            diff = abs(p_distance - distance)
                            weight = 1.0 - min(0.7, diff / 400)
                            pos = p.get('position', 0)
                            if pos == 1:
                                score = 100
                            elif pos == 2:
                                score = 85
                            elif pos == 3:
                                score = 70
                            elif pos <= 5:
                                score = 55
                            elif pos <= 8:
                                score = 40
                            else:
                                score = 25
                            distance_scores.append(score * weight)
                        features['distance_rating'] = sum(distance_scores) / len(distance_scores) if distance_scores else 0
                        
                        positions = [p.get('position', 0) for p in recent_5 if p.get('position', 0) > 0]
                        if len(positions) >= 2:
                            if len(positions) >= 3:
                                trend = (positions[-3] - positions[-1])
                            else:
                                trend = positions[-2] - positions[-1]
                            features['trend'] = max(-10, min(10, trend)) / 10
                        else:
                            features['trend'] = 0
                        
                        weights = [p.get('actual_weight', 0) for p in past_before if p.get('actual_weight', 0) > 0]
                        features['avg_weight'] = sum(weights) / len(weights) if weights else 0
                    else:
                        features['win_rate_3'] = 0
                        features['win_rate_10'] = 0
                        features['place_rate_10'] = 0
                        features['show_rate_10'] = 0
                        features['win_rate_5'] = 0
                        features['win_rate'] = 0
                        features['place_rate'] = 0
                        features['show_rate'] = 0
                        features['distance_rating'] = 0
                        features['trend'] = 0
                        features['avg_weight'] = 0
                    
                    # ---- 2. 场次因素 ----
                    venue_perf = [p for p in past_before if p.get('venue') == venue]
                    if venue_perf:
                        venue_wins = sum(1 for p in venue_perf[:5] if p.get('position') == 1)
                        features['same_course'] = venue_wins / len(venue_perf[:5]) if venue_perf[:5] else 0
                    else:
                        features['same_course'] = 0
                    
                    dist_perf = [p for p in past_before if p.get('distance') == distance]
                    if dist_perf:
                        dist_wins = sum(1 for p in dist_perf[:5] if p.get('position') == 1)
                        features['same_distance'] = dist_wins / len(dist_perf[:5]) if dist_perf[:5] else 0
                    else:
                        features['same_distance'] = 0
                    
                    draw_val = r.get('draw', 0)
                    if draw_val and draw_val > 0:
                        features['draw'] = 100 - (draw_val - 1) * (80 / 13)
                    else:
                        features['draw'] = 0
                    
                    features['weight'] = r.get('actual_weight', 0) or 0
                    
                    # ---- 3. 赔率因素 ----
                    odds_val = r.get('odds', 0)
                    if odds_val and odds_val > 0:
                        features['odds'] = min(100, max(0, 100 * (1 - (odds_val - 1) / 98)))
                    else:
                        features['odds'] = 0
                    
                    features['odds_trend'] = 0
                    features['ev'] = 0
                    #----------
                    # ---- 4. 状态因素（填充真实值） ----
                    # ✅ 年龄因子
                    birth_year = horse_birth_years.get(horse_id)
                    if birth_year and birth_year > 0:
                        try:
                            race_year = int(race_date[:4])
                            age = race_year - birth_year
                            if 4 <= age <= 5:
                                features['age'] = 100
                            elif age == 3 or age == 6:
                                features['age'] = 70
                            elif age == 2 or age == 7:
                                features['age'] = 50
                            elif age >= 8:
                                features['age'] = 30
                            else:
                                features['age'] = 40
                        except:
                            features['age'] = 0
                    else:
                        features['age'] = 0
                    
                    # ✅ 体重变化
                    current_weight = r.get('body_weight')
                    if current_weight and current_weight > 0:
                        last_weight = None
                        for p in past_before:
                            w = p.get('body_weight')
                            if w and w > 0:
                                last_weight = w
                                break
                        if last_weight and last_weight > 0:
                            change = abs(current_weight - last_weight)
                            if change <= 5:
                                features['weight_change'] = 100
                            elif change <= 10:
                                features['weight_change'] = 70
                            elif change <= 15:
                                features['weight_change'] = 40
                            else:
                                features['weight_change'] = 20
                        else:
                            features['weight_change'] = 50
                    else:
                        features['weight_change'] = 50
                    
                    # ✅ 事件报告（规则 + LLM 缓存，与训练一致）
                    features['incident'] = _incident_feature_score(r.get('incident', ''), incident_llm_map)
                    
                    # ✅ 冲刺能力
                    running_pos = r.get('running_position', '')
                    if running_pos and running_pos != '0' and running_pos != '---':
                        positions = [int(c) for c in str(running_pos) if c.isdigit()]
                        if len(positions) >= 2:
                            first_pos = positions[0]
                            last_pos = positions[-1]
                            improvement = first_pos - last_pos
                            if improvement >= 5:
                                features['burst'] = 95
                            elif improvement >= 3:
                                features['burst'] = 85
                            elif improvement >= 1:
                                features['burst'] = 70
                            elif improvement == 0:
                                features['burst'] = 60
                            else:
                                features['burst'] = 40
                        else:
                            features['burst'] = 50
                    else:
                        features['burst'] = 50
                    
                    # ---- 5. 骑师和练马师（填充真实值） ----
                    # ✅ 骑师
                    jockey = r.get('jockey')
                    if jockey:
                        jockey_win_rate = jockey_win_rates.get(jockey, 0.12)
                        features['jockey'] = jockey_win_rate * 100
                        features['jockey_win_rate'] = jockey_win_rate * 100
                    else:
                        features['jockey'] = 0
                        features['jockey_win_rate'] = 0
                    
                    # ✅ 练马师
                    trainer = r.get('trainer')
                    if trainer:
                        features['trainer'] = trainer_base_scores.get(trainer, 50)
                    else:
                        features['trainer'] = 0
                    
                    # ---- 6. 额外字段 ----
                    features['data_used_count'] = len(past_before)
                    features['actual_weight'] = r.get('actual_weight', 0) or 0
                    features['distance'] = distance
                    #-------
                    # ---- 7. 新马标记（与训练保持一致） ----
                    # 判断是否为新马
                    total_races = len(past_before)
                    if total_races < 3:
                        # 新马
                        features['is_new_horse'] = 1
                        # 根据 horse_id 判断类型
                        if horse_id and 'PPG' in str(horse_id):
                            features['new_horse_type'] = 2  # PPG
                        elif horse_id and 'INT' in str(horse_id):
                            features['new_horse_type'] = 3  # INT
                        else:
                            features['new_horse_type'] = 1  # PP
                    else:
                        features['is_new_horse'] = 0
                        features['new_horse_type'] = 0
                    # ---- 获取赔率（确保 odds 始终有值） ----
                    odds_raw = r.get('odds')
                    try:
                        odds = float(odds_raw) if odds_raw and odds_raw != '' else 0
                    except (ValueError, TypeError):
                        odds = 0
                    
                    # 如果赔率为0或无效，使用默认值10.0
                    if odds <= 0:
                        odds = 10.0
                    
                    # ---- 预测 - 获取所有类别概率 ----
                    try:
                        all_probs = predict_with_model(model, features, model_type, return_all_probs=True)
                        
                        # 安全检查：确保 all_probs 是列表且有足够长度
                        if not isinstance(all_probs, list):
                            all_probs = [0.33, 0.33, 0.34]
                        if len(all_probs) < 3:
                            # 如果是二分类，补充为三分类格式
                            if len(all_probs) == 2:
                                all_probs = [all_probs[0], all_probs[1], all_probs[1]]
                            else:
                                all_probs = [0.33, 0.33, 0.34]
                        
                        # 提取好马组概率（类别2）
                        good_group_prob = all_probs[2] if len(all_probs) >= 3 else 0.34
                        prob_bad = all_probs[0] if len(all_probs) >= 3 else 0.33
                        prob_medium = all_probs[1] if len(all_probs) >= 3 else 0.33
                        
                    except Exception as e:
                        print(f"预测异常: {e}")
                        good_group_prob = 0.34
                        prob_bad = 0.33
                        prob_medium = 0.33
                        all_probs = [0.33, 0.33, 0.34]
                    
                    # ---- 添加到 runners 列表 ----
                    runners.append({
                        "horse_id": horse_id,
                        "horse_name": horse_name,
                        "horse_name_zh": horse_name,
                        "horse_name_en": horse_name_en,
                        "horse_no": r.get('horse_no'),
                        "finishing_position": r.get('position'),
                        "good_group_prob": good_group_prob,
                        "prob_bad": prob_bad,
                        "prob_medium": prob_medium,
                        "prob_good": good_group_prob,
                        "odds_win": odds,
                        "actual_position": r.get('position')
                    })
                
                if not runners:
                    continue
                #-----------
                # 按好马组概率排序（降序）
                runners.sort(key=lambda x: x.get('good_group_prob', 0), reverse=True)
                
                # 获取预测前三名（好马组概率最高的3匹）
                predicted_1st_id = runners[0].get('horse_id') if len(runners) > 0 else None
                predicted_2nd_id = runners[1].get('horse_id') if len(runners) > 1 else None
                predicted_3rd_id = runners[2].get('horse_id') if len(runners) > 2 else None
                predicted_top3_ids = {predicted_1st_id, predicted_2nd_id, predicted_3rd_id} - {None}
                
                # 保存预测前三名的赔率（用于ROI计算）
                predicted_top3_odds = []
                for r in runners[:3]:
                    odds = r.get('odds_win', 0)
                    predicted_top3_odds.append(odds if odds > 0 else 3.0)
                #-----------
                # 获取实际结果（用于验证）
                runners_data_sorted_actual = sorted(runners_data, key=lambda x: x.get('position', 99))
                actual_1st_id = None
                actual_2nd_id = None
                actual_3rd_id = None
                actual_top3_ids = set()
                actual_1st_label = actual_2nd_label = actual_3rd_label = "-"
                
                for rr in runners_data_sorted_actual:
                    pos = rr.get('position')
                    record = _runner_record(rr)
                    hid = rr.get('horse_id')
                    if pos == 1:
                        actual_1st_id = hid
                        actual_1st_label = _backtest_horse_label(
                            rr.get('horse_name', ''), rr.get('horse_no'), record=record
                        )
                        actual_top3_ids.add(hid)
                    elif pos == 2:
                        actual_2nd_id = hid
                        actual_2nd_label = _backtest_horse_label(
                            rr.get('horse_name', ''), rr.get('horse_no'), record=record
                        )
                        actual_top3_ids.add(hid)
                    elif pos == 3:
                        actual_3rd_id = hid
                        actual_3rd_label = _backtest_horse_label(
                            rr.get('horse_name', ''), rr.get('horse_no'), record=record
                        )
                        actual_top3_ids.add(hid)

                pred_1st_label = _runner_backtest_label(runners[0] if len(runners) > 0 else None)
                pred_2nd_label = _runner_backtest_label(runners[1] if len(runners) > 1 else None)
                pred_3rd_label = _runner_backtest_label(runners[2] if len(runners) > 2 else None)
                #------------
                # ==================== 统计命中情况 ====================

                # 1. 独赢正确率：预测第1名 = 实际第1名
                is_correct_win = (
                    predicted_1st_id == actual_1st_id
                    if predicted_1st_id and actual_1st_id
                    else False
                )
                
                # 2. 前三名命中匹数：预测前3名 ∩ 实际前3名
                hits = len(predicted_top3_ids & actual_top3_ids)
                total_top3_hits += hits
                if hits >= 1:
                    total_top3_hit_races += 1
                
                # 3. 前三名全中（不限顺序）：预测前3名集合 = 实际前3名集合
                tri_correct = (
                    predicted_top3_ids == actual_top3_ids
                    if len(predicted_top3_ids) == 3 and len(actual_top3_ids) == 3
                    else False
                )
                if tri_correct:
                    total_tri_correct += 1
                
                # 4. 前三名顺序正确：预测第1/2/3名 = 实际第1/2/3名
                tce_correct = (
                    predicted_1st_id == actual_1st_id
                    and predicted_2nd_id == actual_2nd_id
                    and predicted_3rd_id == actual_3rd_id
                ) if all([
                    predicted_1st_id, predicted_2nd_id, predicted_3rd_id,
                    actual_1st_id, actual_2nd_id, actual_3rd_id,
                ]) else False
                if tce_correct:
                    total_tce_correct += 1
                #-------------
                # ==================== ROI 计算 ====================
                
                # 获取预测前三名的赔率
                predicted_top3_odds = []
                for r in runners[:3]:
                    odds_val = r.get('odds_win', 0)
                    try:
                        odds_val = float(odds_val) if odds_val and odds_val != '' else 0
                    except (ValueError, TypeError):
                        odds_val = 0
                    predicted_top3_odds.append(odds_val if odds_val > 0 else 3.0)
                
                # 获取实际冠军的赔率
                actual_winner_odds = 0
                for rr in runners_data:
                    if rr.get('position') == 1:
                        odds_raw = rr.get('odds')
                        try:
                            actual_winner_odds = float(odds_raw) if odds_raw and odds_raw != '' else 0
                        except (ValueError, TypeError):
                            actual_winner_odds = 0
                        break
                #-------
                # ---- 1. 独赢投注 ----
                total_win_stake += 100
                
                if is_correct_win and actual_winner_odds > 0:      # ← 改为 is_correct_win
                    total_win_return += 100 * actual_winner_odds
                elif is_correct_win:                               # ← 改为 is_correct_win
                    total_win_return += 100 * 3.0
                
                # ---- 2. 位置投注 ----
                # 每场对预测前3名各投注30元
                position_stake_per_horse = 30
                total_position_stake += position_stake_per_horse * 3  # 3匹马，每匹30元
                
                # 位置赔率：保守估计为独赢赔率的35%
                for i, predicted_id in enumerate([predicted_1st_id, predicted_2nd_id, predicted_3rd_id]):
                    if predicted_id and predicted_id in actual_top3_ids:
                        # 该马跑入前3名，位置投注中奖
                        odds_val = predicted_top3_odds[i] if i < len(predicted_top3_odds) else 3.0
                        # 位置赔率约为独赢的30-40%，保守取35%
                        place_odds = odds_val * 0.35
                        if place_odds < 1.3:
                            place_odds = 1.3  # 最低位置赔率
                        total_position_return += position_stake_per_horse * place_odds
                
                # 记录调试详情
                if lang == "zh":
                    result["debug_details"].append({
                        "赛期": race_date,
                        "场次": race_no,
                        "预测第1名": pred_1st_label,
                        "预测第2名": pred_2nd_label,
                        "预测第3名": pred_3rd_label,
                        "实际第1名": actual_1st_label,
                        "实际第2名": actual_2nd_label,
                        "实际第3名": actual_3rd_label,
                        "独赢正确": "✅" if is_correct_win else "❌",
                        "前3名命中匹数": hits,
                        "前3名全中": "✅" if tri_correct else "❌",
                        "前3名顺序正确": "✅" if tce_correct else "❌"
                    })
                else:
                    result["debug_details"].append({
                        "Date": race_date,
                        "Race": race_no,
                        "Pred 1st": pred_1st_label,
                        "Pred 2nd": pred_2nd_label,
                        "Pred 3rd": pred_3rd_label,
                        "Actual 1st": actual_1st_label,
                        "Actual 2nd": actual_2nd_label,
                        "Actual 3rd": actual_3rd_label,
                        "Win": "✅" if is_correct_win else "❌",
                        "Top3 Hits": hits,
                        "Trio": "✅" if tri_correct else "❌",
                        "Trifecta": "✅" if tce_correct else "❌"
                    })
                
                # 更新统计
                if is_correct_win:
                    correct_predictions += 1
        
        # 9. 清理进度条
        progress_bar.empty()
        status_text.empty()
        
        # 10. 计算最终结果
        if result["测试场次"] > 0 and not result["cancelled"]:
            result["预测正确"] = correct_predictions
            result["独赢正确率"] = correct_predictions / result["测试场次"] * 100
            #---------------
            # 前三名命中匹数率：分母为 测试场次 × 3（预测前3名）
            result["前三名命中匹数"] = total_top3_hits
            result["前三名命中匹数率"] = total_top3_hits / (result["测试场次"] * 3) * 100
            
            result["前三名命中场次"] = total_top3_hit_races
            result["前三名命中场次率"] = min(100, total_top3_hit_races / result["测试场次"] * 100)
            
            result["前三名全中场次"] = total_tri_correct
            result["前三名全中率"] = total_tri_correct / result["测试场次"] * 100
            
            result["前三名顺序正确场次"] = total_tce_correct
            result["前三名顺序正确率"] = total_tce_correct / result["测试场次"] * 100
            #------
            # 独赢ROI（使用 correct_predictions 和实际赔率累加）
            result["总投入"] = total_win_stake
            result["总回报"] = total_win_return
            if total_win_stake > 0:
                result["ROI"] = (total_win_return - total_win_stake) / total_win_stake * 100
            
            # 位置ROI（新增显示）
            result["位置总投入"] = total_position_stake
            result["位置总回报"] = total_position_return
            if total_position_stake > 0:
                result["位置ROI"] = (total_position_return - total_position_stake) / total_position_stake * 100
            else:
                result["位置ROI"] = 0
            #--------
            # 综合ROI（独赢 + 位置）
            result["综合总投入"] = total_win_stake + total_position_stake
            result["综合总回报"] = total_win_return + total_position_return
            if result["综合总投入"] > 0:
                result["综合ROI"] = (result["综合总回报"] - result["综合总投入"]) / result["综合总投入"] * 100
            else:
                result["综合ROI"] = 0
        # ⭐ 保存模型和特征重要性（供管理员查看）
        if last_model is not None:
            result["model"] = last_model
            result["feature_names"] = last_feature_names
            
            # 提取特征重要性
            try:
                if model_type == 'ensemble':
                    # 集成模型：分别提取两个模型的重要性，然后平均
                    lgb_imp = None
                    xgb_imp = None
                    if last_model.get('lightgbm') is not None:
                        lgb_imp = last_model['lightgbm'].feature_importances_
                    if last_model.get('xgboost') is not None:
                        xgb_imp = last_model['xgboost'].feature_importances_
                    
                    if lgb_imp is not None and xgb_imp is not None:
                        importance = (lgb_imp + xgb_imp) / 2
                    elif lgb_imp is not None:
                        importance = lgb_imp
                    elif xgb_imp is not None:
                        importance = xgb_imp
                    else:
                        importance = None
                else:
                    # 单模型
                    importance = last_model.feature_importances_
                
                if importance is not None and last_feature_names:
                    import pandas as pd
                    imp_df = pd.DataFrame({
                        '特征': last_feature_names,
                        '重要性': importance
                    }).sort_values('重要性', ascending=False)
                    
                    result["feature_importance"] = imp_df
                    print(f"✅ 特征重要性已提取: {len(imp_df)} 个因子")
            except Exception as e:
                print(f"⚠️ 提取特征重要性失败: {e}")
                result["feature_importance"] = None
        
        if not result["cancelled"]:
            model_label = display_model_choice(result["模型"])
            if lang == "zh":
                st.success(
                    f"✅ {model_label} 回測完成: {result['测试场次']} 場, "
                    f"獨贏正確率 {result['独赢正确率']:.1f}%, ROI {result['ROI']:+.1f}%"
                )
            else:
                st.success(
                    f"✅ {model_label} backtest complete: {result['测试场次']} races, "
                    f"win accuracy {result['独赢正确率']:.1f}%, ROI {result['ROI']:+.1f}%"
                )
        
    except Exception as e:
        err_msg = f"ML回測失敗 ({model_type}): {e}" if lang == "zh" else f"ML backtest failed ({model_type}): {e}"
        st.error(err_msg)
        print(f"ML回測失敗: {e}")
    
    # 重置取消标志
    st.session_state.stop_backtest = False

    # ⭐ 输出ML学习到的最优权重
    if last_model is not None and last_feature_names is not None:
        try:
            # 获取特征重要性
            if model_type == 'ensemble':
                lgb_imp = None
                xgb_imp = None
                if last_model.get('lightgbm') is not None:
                    lgb_imp = last_model['lightgbm'].feature_importances_
                if last_model.get('xgboost') is not None:
                    xgb_imp = last_model['xgboost'].feature_importances_
                
                if lgb_imp is not None and xgb_imp is not None:
                    importances = (lgb_imp + xgb_imp) / 2
                elif lgb_imp is not None:
                    importances = lgb_imp
                elif xgb_imp is not None:
                    importances = xgb_imp
                else:
                    importances = None
            else:
                importances = last_model.feature_importances_
            
            if importances is not None:
                total = sum(importances)
                if total > 0:
                    # 计算权重百分比
                    weights = {name: (imp / total) * 100 for name, imp in zip(last_feature_names, importances)}
                    
                    # 打印到控制台
                    print("\n" + "="*70)
                    print("📊 ML学习到的最优权重（18个因子）")
                    print("="*70)
                    print(f"{'因子名称':<20} {'权重':>10} {'说明'}")
                    print("-"*70)
                    
                    # 显示所有因子
                    for name, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
                        if weight > 0.1:  # 只显示有贡献的因子
                            # 中文映射
                            name_cn = feature_name_map.get(name, name)
                            print(f"   {name_cn:<18} {weight:>8.2f}%")
                    
                    print("="*70)
                    print(f"✅ 总权重: {sum(weights.values()):.2f}%")
                    print("="*70 + "\n")
                    
                    # 保存到result
                    result["optimal_weights"] = weights
        except Exception as e:
            print(f"提取最优权重失败: {e}")
    return result
#-----------
def _display_model_backtest_results(results: List[Dict]) -> None:
    """显示多模型回测对比表格、图表与详细场次。"""
    lang = get_lang()
    texts = t()
    if not results:
        st.warning(texts["backtest_select_model"])
        return

    cancelled_results = [r for r in results if r.get("cancelled", False)]
    if cancelled_results:
        st.warning(texts["backtest_partial_cancelled"].format(count=len(cancelled_results)))

    completed_results = [r for r in results if not r.get("cancelled", False)]
    if not completed_results:
        st.warning(texts["backtest_all_failed"])
        return

    st.markdown(f"#### {texts['model_compare_results']}")
    st.caption(texts["model_compare_caption"])

    compare_df = pd.DataFrame(completed_results)
    if lang == "en":
        col_rename = {
            "模型": "Model",
            "测试场次": "Races",
            "独赢正确率": "Win Accuracy",
            "前三名命中匹数率": "Top-3 Horse Hit Rate",
            "前三名命中场次率": "Top-3 Race Hit Rate",
            "前三名全中率": "Trio Hit Rate",
            "前三名顺序正确率": "Trifecta Order Rate",
            "总投入": "Total Stake",
            "总回报": "Total Return",
            "ROI": "ROI",
            "位置ROI": "Place ROI",
            "综合ROI": "Combined ROI",
        }
        display_columns = list(col_rename.values())
        compare_df = compare_df.rename(columns=col_rename)
        format_map = {
            "Win Accuracy": "{:.1f}%",
            "Top-3 Horse Hit Rate": "{:.1f}%",
            "Top-3 Race Hit Rate": "{:.1f}%",
            "Trio Hit Rate": "{:.1f}%",
            "Trifecta Order Rate": "{:.1f}%",
            "ROI": "{:+.1f}%",
            "Place ROI": "{:+.1f}%",
            "Combined ROI": "{:+.1f}%",
            "Total Return": "${:.0f}",
            "Total Stake": "${:.0f}",
        }
        column_config = {
            "Model": st.column_config.TextColumn("Model", width="small"),
            "Races": st.column_config.NumberColumn("Races", width="small"),
            "Win Accuracy": st.column_config.NumberColumn("Win Acc.", width="small", format="%.1f%%"),
            "Top-3 Horse Hit Rate": st.column_config.NumberColumn("Top3 Horses", width="small", format="%.1f%%"),
            "Top-3 Race Hit Rate": st.column_config.NumberColumn("Top3 Races", width="small", format="%.1f%%"),
            "Trio Hit Rate": st.column_config.NumberColumn("Trio", width="small", format="%.1f%%"),
            "Trifecta Order Rate": st.column_config.NumberColumn("Trifecta", width="small", format="%.1f%%"),
            "Total Stake": st.column_config.NumberColumn("Stake", width="small", format="$%.0f"),
            "Total Return": st.column_config.NumberColumn("Return", width="small", format="$%.0f"),
            "ROI": st.column_config.NumberColumn("ROI", width="small", format="%+.1f%%"),
            "Place ROI": st.column_config.NumberColumn("Place ROI", width="small", format="%+.1f%%"),
            "Combined ROI": st.column_config.NumberColumn("Combined ROI", width="small", format="%+.1f%%"),
        }
        chart_labels = [
            "Win Acc.", "Top3 Horses", "Top3 Races", "Trio", "Trifecta Order", "ROI"
        ]
        metric_keys = [
            "独赢正确率", "前三名命中匹数率", "前三名命中场次率",
            "前三名全中率", "前三名顺序正确率", "ROI",
        ]
    else:
        display_columns = [
            "模型", "测试场次", "独赢正确率",
            "前三名命中匹数率", "前三名命中场次率",
            "前三名全中率", "前三名顺序正确率",
            "总投入", "总回报", "ROI", "位置ROI", "综合ROI",
        ]
        format_map = {
            "独赢正确率": "{:.1f}%",
            "前三名命中匹数率": "{:.1f}%",
            "前三名命中场次率": "{:.1f}%",
            "前三名全中率": "{:.1f}%",
            "前三名顺序正确率": "{:.1f}%",
            "ROI": "{:+.1f}%",
            "位置ROI": "{:+.1f}%",
            "综合ROI": "{:+.1f}%",
            "总回报": "${:.0f}",
            "总投入": "${:.0f}",
        }
        column_config = {
            "模型": st.column_config.TextColumn("模型", width="small"),
            "测试场次": st.column_config.NumberColumn("场次", width="small"),
            "独赢正确率": st.column_config.NumberColumn("独赢正确率", width="small", format="%.1f%%"),
            "前三名命中匹数率": st.column_config.NumberColumn("前3名匹数率", width="small", format="%.1f%%"),
            "前三名命中场次率": st.column_config.NumberColumn("前3名场次率", width="small", format="%.1f%%"),
            "前三名全中率": st.column_config.NumberColumn("前3名全中率", width="small", format="%.1f%%"),
            "前三名顺序正确率": st.column_config.NumberColumn("前3名顺序率", width="small", format="%.1f%%"),
            "总投入": st.column_config.NumberColumn("总投入", width="small", format="$%.0f"),
            "总回报": st.column_config.NumberColumn("总回报", width="small", format="$%.0f"),
            "ROI": st.column_config.NumberColumn("ROI", width="small", format="%+.1f%%"),
            "位置ROI": st.column_config.NumberColumn("位置ROI", width="small", format="%+.1f%%"),
            "综合ROI": st.column_config.NumberColumn("综合ROI", width="small", format="%+.1f%%"),
        }
        chart_labels = ["獨贏正確率", "前3名匹數率", "前3名場次率", "前3名全中率", "前3名順序率", "ROI"]
        metric_keys = [
            "独赢正确率", "前三名命中匹数率", "前三名命中场次率",
            "前三名全中率", "前三名顺序正确率", "ROI",
        ]

    available_cols = [c for c in display_columns if c in compare_df.columns]
    compare_df = compare_df[available_cols]
    if lang == "en" and "Model" in compare_df.columns:
        compare_df = compare_df.copy()
        compare_df["Model"] = compare_df["Model"].apply(display_model_choice)

    st.dataframe(
        compare_df.style.format({k: v for k, v in format_map.items() if k in compare_df.columns}),
        use_container_width=True,
        hide_index=True,
        column_config={k: v for k, v in column_config.items() if k in compare_df.columns},
    )

    fig = go.Figure()
    for model in completed_results:
        fig.add_trace(go.Bar(
            name=display_model_choice(model["模型"]),
            x=chart_labels,
            y=[model.get(key, 0) for key in metric_keys],
            textposition="auto",
        ))
    fig.update_layout(title=texts["backtest_chart_title"], barmode="group", height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"#### {texts['backtest_details_title']}")
    st.caption(tx("每個模型獨立窗口，可滾動查看所有場次", "Each model in its own panel — scroll to view all races."))

    if lang == "en":
        detail_column_config = {
            "Date": st.column_config.TextColumn("Date", width="small"),
            "Race": st.column_config.NumberColumn("Race", width="small"),
            "Pred 1st": st.column_config.TextColumn("Pred 1", width="small"),
            "Pred 2nd": st.column_config.TextColumn("Pred 2", width="small"),
            "Pred 3rd": st.column_config.TextColumn("Pred 3", width="small"),
            "Actual 1st": st.column_config.TextColumn("Actual 1", width="small"),
            "Actual 2nd": st.column_config.TextColumn("Actual 2", width="small"),
            "Actual 3rd": st.column_config.TextColumn("Actual 3", width="small"),
            "Win": st.column_config.TextColumn("Win", width="small"),
            "Top3 Hits": st.column_config.NumberColumn("Top3 Hits", width="small"),
            "Trio": st.column_config.TextColumn("Trio", width="small"),
            "Trifecta": st.column_config.TextColumn("Trifecta", width="small"),
        }
    else:
        detail_column_config = {
            "赛期": st.column_config.TextColumn("賽期", width="small"),
            "场次": st.column_config.NumberColumn("場次", width="small"),
            "预测第1名": st.column_config.TextColumn("預測1", width="small"),
            "预测第2名": st.column_config.TextColumn("預測2", width="small"),
            "预测第3名": st.column_config.TextColumn("預測3", width="small"),
            "实际第1名": st.column_config.TextColumn("實際1", width="small"),
            "实际第2名": st.column_config.TextColumn("實際2", width="small"),
            "实际第3名": st.column_config.TextColumn("實際3", width="small"),
            "独赢正确": st.column_config.TextColumn("獨贏", width="small"),
            "前3名命中匹数": st.column_config.NumberColumn("命中匹數", width="small"),
            "前3名全中": st.column_config.TextColumn("全中", width="small"),
            "前3名顺序正确": st.column_config.TextColumn("順序", width="small"),
        }

    for model_result in completed_results:
        model_name = display_model_choice(model_result["模型"])
        debug_details = model_result.get("debug_details", [])
        test_races = model_result.get("测试场次", 0)

        if debug_details:
            with st.expander(
                texts["backtest_expander_detail"].format(
                    model=model_name,
                    detail_count=len(debug_details),
                    test_races=test_races,
                ),
                expanded=False,
            ):
                detail_df = pd.DataFrame(debug_details)
                st.dataframe(
                    detail_df,
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                    column_config={
                        k: v for k, v in detail_column_config.items() if k in detail_df.columns
                    },
                )
                st.caption(texts["backtest_races_scroll"].format(count=len(detail_df)))
        else:
            with st.expander(
                texts["backtest_expander_empty"].format(model=model_name),
                expanded=False,
            ):
                st.info(texts["backtest_no_detail"])


def _get_backtest_performances_with_lookback(
    start_date: str,
    end_date: str,
    lookback_days: int = 730,
) -> List[Dict]:
    """拉取回测区间 + 训练回看窗口内的往绩，避免 ML 训练/预测缺历史。"""
    try:
        train_start = (
            datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")
    except ValueError:
        train_start = start_date
    return get_performances_batch(train_start, end_date)


def _performances_for_ml_training_window(
    all_performances: List[Dict],
    cutoff_date: str,
    training_window_days: int = 0,
) -> List[Dict]:
    """按训练窗口截取 cutoff 之前的往绩；0 表示不限。"""
    if not training_window_days or training_window_days <= 0:
        return all_performances
    try:
        cutoff_dt = datetime.strptime(cutoff_date, "%Y-%m-%d")
        min_date = (cutoff_dt - timedelta(days=training_window_days)).strftime("%Y-%m-%d")
    except ValueError:
        return all_performances
    return [
        p for p in all_performances
        if min_date <= p.get("race_date", "") < cutoff_date
    ]


def _build_race_performance_index(
    all_performances: List[Dict],
) -> Dict[Tuple[str, str, int], List[Dict]]:
    index: Dict[Tuple[str, str, int], List[Dict]] = {}
    for row in all_performances:
        key = (row["race_date"], row.get("venue", "ST"), int(row["race_no"]))
        index.setdefault(key, []).append(row)
    return index


def _attach_runners_data_to_day_races(
    day_races: List[Dict],
    perf_index: Dict[Tuple[str, str, int], List[Dict]],
) -> None:
    for race in day_races:
        key = (race["race_date"], race.get("venue", "ST"), int(race["race_no"]))
        race["_runners_data"] = perf_index.get(key, [])


def _score_races_for_day_rule(
    day_races: List[Dict],
    horse_cache: Dict,
    horse_birth_years: Dict,
    weights_cfg: Dict,
    incident_llm_map: Optional[Dict[str, float]] = None,
) -> Dict[int, List[Dict]]:
    from scoring_engine import score_runners_for_prediction

    scored: Dict[int, List[Dict]] = {}
    for race in day_races:
        race_date = race["race_date"]
        venue = race["venue"]
        race_no = race["race_no"]
        distance = race.get("distance", 1200)
        runners_data = race.get("_runners_data") or []
        if not runners_data:
            continue

        runners_input = []
        for r in runners_data:
            horse_id = r.get("horse_id")
            if not horse_id:
                continue
            horse_name_zh = r.get("horse_name", "")
            runners_input.append(
                {
                    "horse_id": horse_id,
                    "horse_name": horse_name_zh,
                    "horse_name_zh": horse_name_zh,
                    "horse_name_en": r.get("horse_name_en", ""),
                    "horse_no": r.get("horse_no"),
                    "draw": r.get("draw"),
                    "actual_weight": r.get("actual_weight"),
                    "jockey": r.get("jockey"),
                    "trainer": r.get("trainer"),
                    "odds_win": r.get("odds"),
                    "body_weight": r.get("body_weight"),
                    "incident": r.get("incident", ""),
                    "running_position": r.get("running_position", ""),
                }
            )

        runners = score_runners_for_prediction(
            race_date,
            venue,
            distance,
            runners_input,
            horse_cache,
            horse_birth_years,
            weights_cfg,
            incident_llm_map=incident_llm_map,
        )
        if runners:
            scored[race_no] = runners
    return scored


def _top1_pool_label(pool_code: str) -> str:
    lang = st.session_state.get("lang", "zh")
    labels = {
        "WIN": ("独赢", "Win"),
        "PLA": ("位置", "Place"),
        "DT": ("孖T", "Double Trio"),
        "TT": ("三T", "Triple Trio"),
        "SixUP": ("六环彩", "Six Up"),
    }
    zh, en = labels.get(pool_code, (pool_code, pool_code))
    return zh if lang == "zh" else en


def run_top1_fixed_strategy_backtest(
    start_date: str,
    end_date: str,
    model_type: str = "lightgbm",
    stake_per_bet: float = 10.0,
    random_seed: str = "7",
    use_date_as_seed: bool = False,
    include_win_place: bool = True,
    include_double_trio: bool = True,
    include_triple_trio: bool = True,
    include_six_up: bool = True,
    fast_mode: bool = True,
) -> Top1FixedBacktestResult:
    texts = t()
    model_names = {
        "rule": texts["rating_system"],
        "lightgbm": "LightGBM",
        "xgboost": "XGBoost",
    }
    model_label = model_names.get(model_type, model_type)

    if model_type == "lightgbm" and not LGB_AVAILABLE:
        st.error(texts["lightgbm_not_installed"])
        return Top1FixedBacktestResult(
            model_label=model_label,
            start_date=start_date,
            end_date=end_date,
            stake_per_bet=stake_per_bet,
            random_seed=random_seed,
            use_date_as_seed=use_date_as_seed,
            include_win_place=include_win_place,
            include_double_trio=include_double_trio,
            include_triple_trio=include_triple_trio,
            include_six_up=include_six_up,
        )
    if model_type == "xgboost" and not XGB_AVAILABLE:
        st.error(texts["xgboost_not_installed"])
        return Top1FixedBacktestResult(
            model_label=model_label,
            start_date=start_date,
            end_date=end_date,
            stake_per_bet=stake_per_bet,
            random_seed=random_seed,
            use_date_as_seed=use_date_as_seed,
            include_win_place=include_win_place,
            include_double_trio=include_double_trio,
            include_triple_trio=include_triple_trio,
            include_six_up=include_six_up,
        )

    with st.spinner(texts["top1_backtest_running"].format(model=model_label)):
        all_performances = _get_backtest_performances_with_lookback(start_date, end_date)
    if not all_performances:
        st.error(texts["no_data_fetched"])
        return Top1FixedBacktestResult(
            model_label=model_label,
            start_date=start_date,
            end_date=end_date,
            stake_per_bet=stake_per_bet,
            random_seed=random_seed,
            use_date_as_seed=use_date_as_seed,
            include_win_place=include_win_place,
            include_double_trio=include_double_trio,
            include_triple_trio=include_triple_trio,
            include_six_up=include_six_up,
        )

    horse_cache = build_horse_performances_cache(all_performances)
    perf_index = _build_race_performance_index(all_performances)
    incident_llm_map = _build_incident_llm_map(
        [p.get("incident", "") for p in all_performances if p.get("incident")]
    )
    all_races = get_races_from_performances(all_performances)
    backtest_races = [
        race for race in all_races if start_date <= race["race_date"] <= end_date
    ]
    if not backtest_races:
        st.warning(texts["no_races_found"])
        return Top1FixedBacktestResult(
            model_label=model_label,
            start_date=start_date,
            end_date=end_date,
            stake_per_bet=stake_per_bet,
            random_seed=random_seed,
            use_date_as_seed=use_date_as_seed,
            include_win_place=include_win_place,
            include_double_trio=include_double_trio,
            include_triple_trio=include_triple_trio,
            include_six_up=include_six_up,
        )

    day_race_groups = _group_race_days(backtest_races)
    sorted_day_keys = sorted(day_race_groups.keys())
    progress_bar = st.progress(0)
    status_text = st.empty()
    day_counter = {"idx": 0}

    weights_cfg = None
    horse_birth_years = {}
    if model_type == "rule":
        from scoring_engine import get_scoring_config, load_horse_birth_years

        config = get_scoring_config()
        weights_cfg = {
            "level1": config.get("level1", {}),
            "basic": config.get("basic", {}),
            "race": config.get("race", {}),
            "odds": config.get("odds", {}),
            "status": config.get("status", {}),
        }
        try:
            horse_birth_years = load_horse_birth_years()
        except Exception:
            horse_birth_years = {}

    model_cache: Dict[str, object] = {}
    weight_hash = None
    if model_type != "rule":
        from scoring_engine import get_cached_model, get_current_weights_hash, set_cached_model

        weight_hash = get_current_weights_hash()

    def score_day_races(race_date: str, venue: str, day_races: List[Dict]) -> Dict[int, List[Dict]]:
        day_counter["idx"] += 1
        progress_msg = (
            f"Top1 {model_label}: {race_date} {venue} "
            f"({day_counter['idx']}/{len(sorted_day_keys)})"
        )
        status_text.text(progress_msg)
        progress_bar.progress(day_counter["idx"] / max(len(sorted_day_keys), 1))

        _attach_runners_data_to_day_races(day_races, perf_index)
        if model_type == "rule":
            return _score_races_for_day_rule(
                day_races, horse_cache, horse_birth_years, weights_cfg, incident_llm_map
            )

        train_key = race_date[:7] if fast_mode else race_date
        model = model_cache.get(train_key)
        if model is None:
            train_X, train_y = prepare_training_data_by_date(
                race_date, all_performances, horse_cache, incident_llm_map=incident_llm_map
            )
            if train_X is None or len(train_X) < 50:
                return {}

            cache_key = f"top1_{model_type}_{train_key}_{weight_hash}"
            cached_model = get_cached_model(cache_key)
            if cached_model is not None:
                model = cached_model
            else:
                model = get_or_train_model(train_X, train_y, model_type, cache_key)
                if model is not None:
                    set_cached_model(cache_key, model)
            model_cache[train_key] = model

        if model is None:
            return {}
        return _score_races_for_day_ml(
            day_races, all_performances, model_type, model,
            horse_cache=horse_cache, incident_llm_map=incident_llm_map,
        )

    result = run_top1_fixed_backtest_core(
        start_date=start_date,
        end_date=end_date,
        model_label=model_label,
        stake_per_bet=stake_per_bet,
        random_seed=random_seed,
        use_date_as_seed=use_date_as_seed,
        include_win_place=include_win_place,
        include_double_trio=include_double_trio,
        include_triple_trio=include_triple_trio,
        include_six_up=include_six_up,
        day_race_groups=day_race_groups,
        score_day_races=score_day_races,
        should_cancel=lambda: st.session_state.get("stop_backtest", False),
    )

    progress_bar.empty()
    status_text.empty()
    if result.cancelled:
        st.warning(texts["backtest_cancelled"])
    return result


def _display_top1_fixed_backtest_results(result: Top1FixedBacktestResult) -> None:
    if not result:
        return
    texts = t()
    st.markdown(f"#### {texts['top1_summary_title']} · {result.model_label}")
    st.caption(
        f"{result.start_date} → {result.end_date} · "
        f"{texts['top1_race_days']}: {result.race_days} · "
        f"{texts['top1_stake_label']}: HK${result.stake_per_bet:.0f}"
    )

    pool_rows = []
    pool_defs = [
        ("WIN", result.win_stats, result.include_win_place),
        ("PLA", result.place_stats, result.include_win_place),
        ("DT", result.double_trio_stats, result.include_double_trio),
        ("TT", result.triple_trio_stats, result.include_triple_trio),
        ("SixUP", result.six_up_stats, result.include_six_up),
    ]
    for pool_code, stats, enabled in pool_defs:
        if not enabled:
            continue
        pool_rows.append(
            {
                texts["top1_col_pool"]: _top1_pool_label(pool_code),
                texts["metric_total_bets"]: stats.bets,
                texts["metric_hit_bets"]: stats.hits,
                texts["top1_hit_rate"]: f"{stats.hit_rate:.1f}%",
                texts["metric_total_stake"]: f"HK${stats.stake:,.0f}",
                texts["metric_total_return"]: f"HK${stats.return_amount:,.0f}",
                "ROI": f"{stats.roi:+.1f}%",
            }
        )

    if pool_rows:
        st.dataframe(pd.DataFrame(pool_rows), use_container_width=True, hide_index=True)

    detail_rows = []
    for detail in result.details:
        detail_rows.append(
            {
                texts["top1_col_pool"]: _top1_pool_label(detail.pool),
                texts["top1_col_date"]: detail.race_date,
                texts["top1_col_venue"]: detail.venue,
                texts["top1_col_race"]: detail.race_label,
                texts["top1_col_recommended"]: detail.recommended,
                texts["top1_col_actual"]: detail.actual,
                texts["top1_col_hit"]: "✅" if detail.hit else "❌",
                texts["top1_col_stake"]: f"HK${detail.stake:.0f}",
                texts["top1_col_return"]: f"HK${detail.return_amount:.0f}",
                texts["top1_col_note"]: detail.note,
            }
        )

    if detail_rows:
        with st.expander(texts["top1_detail_title"], expanded=True):
            st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True, height=420)
    else:
        st.info(texts["backtest_no_detail"])

    if result.skipped_notes:
        with st.expander(texts["top1_skipped"], expanded=False):
            for note in result.skipped_notes:
                st.caption(note)


def run_rank_calibration_backtest(
    start_date: str,
    end_date: str,
    model_type: str = "lightgbm",
    fast_mode: bool = True,
    training_window_days: int = 0,
) -> RankCalibrationResult:
    texts = t()
    model_names = {
        "rule": texts["rating_system"],
        "lightgbm": "LightGBM",
        "xgboost": "XGBoost",
    }
    model_label = model_names.get(model_type, model_type)
    training_window_days = max(0, int(training_window_days or 0))
    result = RankCalibrationResult(
        model_label=model_label,
        start_date=start_date,
        end_date=end_date,
        training_window_days=training_window_days,
    )

    if model_type == "lightgbm" and not LGB_AVAILABLE:
        st.error(texts["lightgbm_not_installed"])
        return result
    if model_type == "xgboost" and not XGB_AVAILABLE:
        st.error(texts["xgboost_not_installed"])
        return result

    fetch_lookback = max(730, training_window_days) if training_window_days > 0 else 730
    with st.spinner(texts["rank_calib_running"].format(model=model_label)):
        all_performances = _get_backtest_performances_with_lookback(
            start_date, end_date, lookback_days=fetch_lookback
        )
    if not all_performances:
        st.error(texts["no_data_fetched"])
        return result

    horse_cache = build_horse_performances_cache(all_performances)
    perf_index = _build_race_performance_index(all_performances)
    incident_llm_map = _build_incident_llm_map(
        [p.get("incident", "") for p in all_performances if p.get("incident")]
    )
    all_races = get_races_from_performances(all_performances)
    backtest_races = [
        race for race in all_races if start_date <= race["race_date"] <= end_date
    ]
    if not backtest_races:
        st.warning(texts["no_races_found"])
        return result

    backtest_races.sort(key=lambda r: (r["race_date"], r.get("venue", "ST"), r["race_no"]))
    day_race_groups = _group_race_days(backtest_races)
    sorted_day_keys = sorted(day_race_groups.keys())

    weights_cfg = None
    horse_birth_years = {}
    if model_type == "rule":
        from scoring_engine import get_scoring_config, load_horse_birth_years

        config = get_scoring_config()
        weights_cfg = {
            "level1": config.get("level1", {}),
            "basic": config.get("basic", {}),
            "race": config.get("race", {}),
            "odds": config.get("odds", {}),
            "status": config.get("status", {}),
        }
        try:
            horse_birth_years = load_horse_birth_years()
        except Exception:
            horse_birth_years = {}

    model_cache: Dict[str, object] = {}
    weight_hash = None
    if model_type != "rule":
        from scoring_engine import get_cached_model, get_current_weights_hash, set_cached_model

        weight_hash = get_current_weights_hash()

    progress_bar = st.progress(0)
    status_text = st.empty()
    calibration_races: List[RankCalibrationRace] = []

    for idx, (race_date, venue) in enumerate(sorted_day_keys):
        if st.session_state.get("stop_backtest", False):
            result.cancelled = True
            st.warning(texts["backtest_cancelled"])
            break

        status_text.text(
            f"{texts['rank_calib_title']} {model_label}: {race_date} {venue} "
            f"({idx + 1}/{len(sorted_day_keys)})"
        )
        progress_bar.progress((idx + 1) / max(len(sorted_day_keys), 1))

        day_races = day_race_groups[(race_date, venue)]
        _attach_runners_data_to_day_races(day_races, perf_index)

        if model_type == "rule":
            scored_by_race = _score_races_for_day_rule(
                day_races, horse_cache, horse_birth_years, weights_cfg, incident_llm_map
            )
        else:
            train_key = race_date[:7] if fast_mode else race_date
            model = model_cache.get(train_key)
            if model is None:
                train_performances = _performances_for_ml_training_window(
                    all_performances, race_date, training_window_days
                )
                train_X, train_y = prepare_training_data_by_date(
                    race_date, train_performances, horse_cache, incident_llm_map=incident_llm_map
                )
                if train_X is None or len(train_X) < 50:
                    continue
                window_tag = training_window_days if training_window_days > 0 else "all"
                cache_key = f"rank_calib_{model_type}_{train_key}_w{window_tag}_{weight_hash}"
                cached_model = get_cached_model(cache_key)
                if cached_model is not None:
                    model = cached_model
                else:
                    model = get_or_train_model(train_X, train_y, model_type, cache_key)
                    if model is not None:
                        set_cached_model(cache_key, model)
                model_cache[train_key] = model
            if model is None:
                continue
            scored_by_race = _score_races_for_day_ml(
                day_races, all_performances, model_type, model,
                horse_cache=horse_cache, incident_llm_map=incident_llm_map,
            )

        for race in sorted(day_races, key=lambda r: r["race_no"]):
            race_no = race["race_no"]
            scored = scored_by_race.get(race_no)
            runners_data = race.get("_runners_data") or []
            if not scored or not runners_data:
                continue
            table = build_rank_calibration_race(
                race_date,
                venue,
                race_no,
                scored,
                runners_data,
                name_resolver=resolve_horse_name,
            )
            if table:
                calibration_races.append(table)

    progress_bar.empty()
    status_text.empty()

    summary = summarize_rank_calibration(calibration_races)
    result.races = calibration_races
    result.race_count = int(summary["race_count"])
    result.top1_in_top3_count = int(summary["top1_in_top3_count"])
    result.top1_in_top3_rate = float(summary["top1_in_top3_rate"])
    result.ai_top4_cover_count = int(summary["ai_top4_cover_count"])
    result.ai_top4_cover_rate = float(summary["ai_top4_cover_rate"])
    return result


def _display_rank_calibration_results(result: RankCalibrationResult) -> None:
    if not result:
        return
    texts = t()
    st.markdown(f"#### {texts['rank_calib_title']} · {result.model_label}")
    window_note = (
        texts["rank_calib_train_window_summary"].format(days=result.training_window_days)
        if result.training_window_days > 0
        else texts["rank_calib_train_window_unlimited"]
    )
    st.caption(
        f"{result.start_date} → {result.end_date} · {window_note} · {texts['rank_calib_caption']}"
    )

    if result.race_count == 0:
        st.info(texts["backtest_no_detail"])
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(texts["rank_calib_race_count"], result.race_count)
    with c2:
        st.metric(
            texts["rank_calib_top1_top3"],
            f"{result.top1_in_top3_count}/{result.race_count} ({result.top1_in_top3_rate:.1f}%)",
        )
    with c3:
        st.metric(
            texts["rank_calib_ai_top4_cover"],
            f"{result.ai_top4_cover_count}/{result.race_count} ({result.ai_top4_cover_rate:.1f}%)",
        )

    labels = {
        "legend_top4": texts["rank_calib_legend_top4"],
        "legend_top1": texts["rank_calib_legend_top1"],
        "race_label": texts["rank_calib_race_label"],
        "col_rank": texts["rank_calib_col_rank"],
        "col_horse_no": texts["rank_calib_col_horse_no"],
        "col_horse_name": texts["rank_calib_col_horse_name"],
        "col_win_prob": texts["rank_calib_col_win_prob"],
        "col_odds": texts["rank_calib_col_odds"],
        "col_actual_top4": texts["rank_calib_col_actual"],
    }
    import streamlit.components.v1 as components

    components.html(render_rank_calibration_html(result, labels), height=720, scrolling=True)


def render_rank_calibration_backtest_section() -> None:
    """管理员专用：AI 排名校准表回测。"""
    texts = t()
    st.markdown("---")
    st.markdown(f"## {texts['rank_calib_title']}")
    st.caption(texts["rank_calib_caption"])

    if "admin_rank_calibration_result" not in st.session_state:
        st.session_state.admin_rank_calibration_result = None

    rc_date1, rc_date2, rc_model_col, rc_window_col = st.columns(4)
    with rc_date1:
        rank_calib_start = st.date_input(
            texts["start_date"],
            value=datetime.now() - timedelta(days=14),
            key="admin_rank_calib_start",
        )
    with rc_date2:
        rank_calib_end = st.date_input(
            texts["end_date"],
            value=datetime.now(),
            key="admin_rank_calib_end",
        )
    with rc_model_col:
        rank_calib_model_options = [texts["rating_system"], "LightGBM"]
        if XGB_AVAILABLE:
            rank_calib_model_options.append("XGBoost")
        rank_calib_model_idx = (
            rank_calib_model_options.index("LightGBM")
            if "LightGBM" in rank_calib_model_options
            else 0
        )
        rank_calib_model_label = st.selectbox(
            texts["ai_model"],
            options=rank_calib_model_options,
            index=rank_calib_model_idx,
            key="admin_rank_calib_model",
        )
    with rc_window_col:
        rank_calib_train_window = st.number_input(
            texts["rank_calib_train_window_label"],
            min_value=0,
            max_value=2000,
            value=730,
            step=1,
            key="admin_rank_calib_train_window",
            help=texts["rank_calib_train_window_help"],
        )

    rank_calib_fast_mode = st.checkbox(
        texts["fast_mode_label"],
        value=True,
        key="admin_rank_calib_fast_mode",
        help=texts["fast_mode_help"],
    )

    run_rank_calib_btn = st.button(
        texts["run_rank_calib"],
        type="primary",
        use_container_width=True,
        key="admin_run_rank_calib_btn",
    )

    if run_rank_calib_btn:
        if rank_calib_start > rank_calib_end:
            st.error(texts["invalid_date_range"])
        else:
            rc_model_type = "rule"
            if rank_calib_model_label == "LightGBM":
                rc_model_type = "lightgbm"
            elif rank_calib_model_label == "XGBoost":
                rc_model_type = "xgboost"
            rc_result = run_rank_calibration_backtest(
                start_date=rank_calib_start.strftime("%Y-%m-%d"),
                end_date=rank_calib_end.strftime("%Y-%m-%d"),
                model_type=rc_model_type,
                fast_mode=rank_calib_fast_mode,
                training_window_days=int(rank_calib_train_window),
            )
            st.session_state.admin_rank_calibration_result = rc_result
            _display_rank_calibration_results(rc_result)
    elif st.session_state.get("admin_rank_calibration_result"):
        _display_rank_calibration_results(st.session_state.admin_rank_calibration_result)


def render_backtest_page(show_title: bool = True):
    """回测页面：模型对比 + 单场回测 + 全天回测"""
    if show_title:
        st.markdown(f"## {t()['backtest']}")
    
    # ==================== 模型对比回测 ====================
    st.markdown(f"## {t()['model_comparison']}")
    st.caption(t()["backtest_period"])
    
    # 初始化 session_state 中的日期
    if "backtest_start_date" not in st.session_state:
        st.session_state.backtest_start_date = (datetime.now() - timedelta(days=180)).date()
    if "backtest_end_date" not in st.session_state:
        st.session_state.backtest_end_date = datetime.now().date()
    
    # ⭐ 新增：初始化回测结果缓存（用于 SHAP/热力图后保留）
    if "backtest_results" not in st.session_state:
        st.session_state.backtest_results = None
    if "backtest_completed" not in st.session_state:
        st.session_state.backtest_completed = False
    if "_backtest_just_run" not in st.session_state:
        st.session_state._backtest_just_run = False
    
    # 日期选择器（无预设按钮）
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        backtest_start = st.date_input(
            t()["start_date"], 
            value=st.session_state.backtest_start_date,
            key="backtest_start_date_input"
        )
    with col2:
        backtest_end = st.date_input(
            t()["end_date"], 
            value=st.session_state.backtest_end_date,
            key="backtest_end_date_input"
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_backtest_btn = st.button(t()["run_backtest"], type="primary", use_container_width=True)
    
    # 更新 session_state
    st.session_state.backtest_start_date = backtest_start
    st.session_state.backtest_end_date = backtest_end
    
    # 模型选择复选框
    st.markdown(t()["select_models"])
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    with col_m1:
        enable_rule = st.checkbox(t()["rating_system"], value=True, key="backtest_rule")
    with col_m2:
        enable_lgb = st.checkbox(t()["lightgbm"], value=LGB_AVAILABLE, key="backtest_lgb",
                                 disabled=not LGB_AVAILABLE,
                                 help=t()["install_lightgbm_help"] if not LGB_AVAILABLE else "")
    with col_m3:
        enable_xgb = st.checkbox(t()["xgboost"], value=XGB_AVAILABLE, key="backtest_xgb",
                                 disabled=not XGB_AVAILABLE,
                                 help=t()["install_xgboost_help"] if not XGB_AVAILABLE else "")
    with col_m4:
        enable_ensemble = st.checkbox(t()["ensemble"], value=(LGB_AVAILABLE or XGB_AVAILABLE), key="backtest_ensemble",
                                      disabled=(not LGB_AVAILABLE and not XGB_AVAILABLE),
                                      help=t()["ml_install_hint"] if (not LGB_AVAILABLE and not XGB_AVAILABLE) else "")
    
    if not LGB_AVAILABLE and not XGB_AVAILABLE:
        st.info(f"💡 {t()['ml_install_hint']}:\n```\npip install lightgbm xgboost\n```")
    
    st.markdown("---")
    
    # 运行回测
    if run_backtest_btn:
        if not require_trial(f"model_backtest:{backtest_start}:{backtest_end}", dedupe=False):
            pass
        else:
            if backtest_start > backtest_end:
                st.error(t()["invalid_date_range"])
            else:
                days_diff = (backtest_end - backtest_start).days
                st.info(t()["backtest_period_info"].format(
                    start=backtest_start, end=backtest_end, days=days_diff,
                ))
                
                with st.spinner(t()["running_model_backtest"]):
                    results = []
                    
                    if enable_rule:
                        result = run_backtest_for_model(
                            start_date=backtest_start.strftime("%Y-%m-%d"),
                            end_date=backtest_end.strftime("%Y-%m-%d"),
                            model_type="rule"
                        )
                        results.append(result)
                    
                    if enable_lgb and LGB_AVAILABLE:
                        result = run_ml_backtest(
                            start_date=backtest_start.strftime("%Y-%m-%d"),
                            end_date=backtest_end.strftime("%Y-%m-%d"),
                            model_type="lightgbm"
                        )
                        results.append(result)
                    
                    if enable_xgb and XGB_AVAILABLE:
                        result = run_ml_backtest(
                            start_date=backtest_start.strftime("%Y-%m-%d"),
                            end_date=backtest_end.strftime("%Y-%m-%d"),
                            model_type="xgboost"
                        )
                        results.append(result)
                    
                    if enable_ensemble and (LGB_AVAILABLE or XGB_AVAILABLE):
                        result = run_ml_backtest(
                            start_date=backtest_start.strftime("%Y-%m-%d"),
                            end_date=backtest_end.strftime("%Y-%m-%d"),
                            model_type="ensemble"
                        )
                        results.append(result)
                    
                    st.session_state.backtest_results = results
                    st.session_state.backtest_completed = True
                    _display_model_backtest_results(results)
    elif st.session_state.get("backtest_completed") and st.session_state.get("backtest_results"):
        _display_model_backtest_results(st.session_state.backtest_results)

    st.markdown("---")
    st.markdown(f"## {t()['top1_fixed_backtest']}")
    st.caption(t()["top1_fixed_backtest_caption"])

    if "top1_fixed_backtest_result" not in st.session_state:
        st.session_state.top1_fixed_backtest_result = None

    top1_model_options = [t()["rating_system"], "LightGBM"]
    if XGB_AVAILABLE:
        top1_model_options.append("XGBoost")
    default_top1_model_idx = top1_model_options.index("LightGBM") if "LightGBM" in top1_model_options else 0

    top1_date1, top1_date2, top1_model_col, top1_stake_col = st.columns(4)
    with top1_date1:
        top1_backtest_start = st.date_input(
            t()["start_date"],
            value=datetime.now() - timedelta(days=14),
            key="top1_backtest_start",
        )
    with top1_date2:
        top1_backtest_end = st.date_input(
            t()["end_date"],
            value=datetime.now(),
            key="top1_backtest_end",
        )
    with top1_model_col:
        top1_model_label = st.selectbox(
            t()["ai_model"],
            options=top1_model_options,
            index=default_top1_model_idx,
            key="top1_backtest_model",
        )
    with top1_stake_col:
        top1_stake = st.number_input(
            t()["top1_stake_label"],
            min_value=10,
            max_value=5000,
            value=10,
            step=10,
            key="top1_backtest_stake",
        )

    top1_c3, top1_c4, top1_c5, top1_c6 = st.columns(4)
    with top1_c3:
        top1_seed = st.text_input(
            t()["top1_random_seed_label"],
            value="7",
            key="top1_backtest_seed",
        )
    with top1_c4:
        top1_use_date_seed = st.checkbox(
            t()["top1_use_date_seed"],
            value=False,
            key="top1_backtest_use_date_seed",
        )
    with top1_c5:
        top1_fast_mode = st.checkbox(
            t()["fast_mode_label"],
            value=True,
            key="top1_backtest_fast_mode",
            help=t()["fast_mode_help"],
        )

    top1_chk1, top1_chk2, top1_chk3, top1_chk4 = st.columns(4)
    with top1_chk1:
        top1_include_win_place = st.checkbox(
            t()["top1_include_win_place"],
            value=True,
            key="top1_include_win_place",
        )
    with top1_chk2:
        top1_include_double_trio = st.checkbox(
            t()["top1_include_double_trio"],
            value=True,
            key="top1_include_double_trio",
        )
    with top1_chk3:
        top1_include_triple_trio = st.checkbox(
            t()["top1_include_triple_trio"],
            value=True,
            key="top1_include_triple_trio",
        )
    with top1_chk4:
        top1_include_six_up = st.checkbox(
            t()["top1_include_six_up"],
            value=True,
            key="top1_include_six_up",
        )

    run_top1_backtest_btn = st.button(
        t()["run_top1_fixed_backtest"],
        type="primary",
        use_container_width=True,
        key="run_top1_fixed_backtest_btn",
    )

    if run_top1_backtest_btn:
        if not require_trial(
            f"top1_fixed_backtest:{top1_backtest_start}:{top1_backtest_end}:{top1_model_label}",
            dedupe=False,
        ):
            pass
        elif top1_backtest_start > top1_backtest_end:
            st.error(t()["invalid_date_range"])
        else:
            top1_model_type = "rule"
            if top1_model_label == "LightGBM":
                top1_model_type = "lightgbm"
            elif top1_model_label == "XGBoost":
                top1_model_type = "xgboost"

            top1_result = run_top1_fixed_strategy_backtest(
                start_date=top1_backtest_start.strftime("%Y-%m-%d"),
                end_date=top1_backtest_end.strftime("%Y-%m-%d"),
                model_type=top1_model_type,
                stake_per_bet=float(top1_stake),
                random_seed=str(top1_seed).strip() or "7",
                use_date_as_seed=top1_use_date_seed,
                include_win_place=top1_include_win_place,
                include_double_trio=top1_include_double_trio,
                include_triple_trio=top1_include_triple_trio,
                include_six_up=top1_include_six_up,
                fast_mode=top1_fast_mode,
            )
            st.session_state.top1_fixed_backtest_result = top1_result
            _display_top1_fixed_backtest_results(top1_result)
    elif st.session_state.get("top1_fixed_backtest_result"):
        _display_top1_fixed_backtest_results(st.session_state.top1_fixed_backtest_result)

    st.markdown("---")
    #-------------
# ==================== 赛日组合策略回测 ====================
    st.markdown(f"## {t()['strategy_backtest']}")
    st.caption(t()["strategy_backtest_caption"])

    strat_col1, strat_col2, strat_col3, strat_col4, strat_col5, strat_col6 = st.columns(6)

    with strat_col1:
        backtest_strategy_start = st.date_input(
            t()['start_date'],
            value=datetime.now() - timedelta(days=14),
            key="strategy_backtest_start"
        )

    with strat_col2:
        backtest_strategy_end = st.date_input(
            t()['end_date'],
            value=datetime.now(),
            key="strategy_backtest_end"
        )

    strategy_model_options = []
    if LGB_AVAILABLE:
        strategy_model_options.append("LightGBM")
    if XGB_AVAILABLE:
        strategy_model_options.append("XGBoost")
    if not strategy_model_options:
        strategy_model_options = ["LightGBM", "XGBoost"]

    default_model_idx = strategy_model_options.index("LightGBM") if "LightGBM" in strategy_model_options else 0

    with strat_col3:
        strategy_model = st.selectbox(
            t()["ai_model"],
            options=strategy_model_options,
            index=default_model_idx,
            key="strategy_backtest_model",
            help=t()["strategy_model_help"],
        )

    with strat_col4:
        portfolio_budget = st.number_input(
            t()["day_portfolio_budget_label"],
            min_value=100,
            max_value=5000,
            value=1000,
            step=100,
            key="strategy_portfolio_budget",
        )

    with strat_col5:
        min_ev_threshold = st.slider(
            t()['min_ev_threshold'],
            min_value=0.0,
            max_value=0.5,
            value=0.0,
            step=0.05,
            format="%.2f",
            key="min_ev_threshold",
            help=t()["min_ev_help"],
        )

    with strat_col6:
        fast_mode = st.checkbox(
            t()["fast_mode_label"],
            value=False,
            key="strategy_fast_mode",
            help=t()["fast_mode_help"],
        )

    run_strategy_backtest_btn = st.button(
        t()['run_strategy_backtest'],
        type="primary",
        use_container_width=True,
        key="run_strategy_backtest_btn",
    )

    if run_strategy_backtest_btn:
        result = None
        if not require_trial(
            f"strategy_backtest:{backtest_strategy_start}:{backtest_strategy_end}:{strategy_model}",
            dedupe=False,
        ):
            pass
        else:
            start_date = backtest_strategy_start.strftime("%Y-%m-%d")
            end_date = backtest_strategy_end.strftime("%Y-%m-%d")
            model_type = "lightgbm" if strategy_model == "LightGBM" else "xgboost"
            cache_key = (
                f"day_portfolio_backtest_v1_{strategy_model}_"
                f"{start_date}_{end_date}_{portfolio_budget}_{min_ev_threshold}_{fast_mode}"
            )

            if cache_key not in st.session_state:
                with st.spinner(t()["running_day_portfolio_backtest"].format(model=strategy_model)):
                    result = run_day_portfolio_backtest(
                        start_date,
                        end_date,
                        model_type=model_type,
                        budget_per_day=portfolio_budget,
                        min_ev=min_ev_threshold,
                        fast_mode=fast_mode,
                    )
                    st.session_state[cache_key] = result
            else:
                result = st.session_state[cache_key]
                st.info(t()["using_cached_backtest"])

            if result and result.get("total_bets", 0) > 0:
                _display_day_portfolio_backtest_summary(result)
            elif result:
                st.warning(t()["backtest_no_bets"])

    st.caption(t()['disclaimer_backtest'])


# ==================== 第5次代码结束 ====================


# ==================== 主函数 ====================
def main():
    """主函数"""
    # 处理支付回调
    handle_stripe_callback()

    try_restore_remember_me_login()
    ensure_valid_access_token()
    try_restore_admin_session()
    render_pwa_install_hint(st.session_state.get("lang", "zh"))
    
    # 渲染侧边栏和顶部按钮
    render_sidebar()
    render_top_buttons()

    # 管理员登录
    if st.session_state.get("show_admin_login", False):
        inject_auth_mobile_body_class()
        if st.session_state.get("try_admin_local_restore"):
            _inject_admin_restore_js()
            st.session_state.try_admin_local_restore = False
        render_admin_login_form()
        return

    # 管理员模式
    if st.session_state.get("admin_mode", False):
        inject_sidebar_mobile_support()
        render_admin_panel()
        return

    # 未登录
    if not st.session_state.authenticated:
        inject_auth_mobile_body_class()
        if st.session_state.get("show_register", False):
            render_register_form()
        else:
            render_login_form()
        return

    inject_sidebar_mobile_support()
    
    # 已登录，直接显示主页（包含所有模块：数据概览 + 智能投注 + 回测）
    render_home()
    maybe_show_paywall_dialog()

# ============================================================
# 第2次代码：评分引擎 + 数据模型
# 包含：马匹评分函数、Softmax胜率计算、赔率校准、数据库操作
# 版本：v1.0
# ============================================================

# ==================== 评分权重常量 ====================
# 基础评分因子权重（近10场往绩）
BASIC_SCORE_WEIGHTS = {
    "win_rate": 0.35,           # 胜率
    "place_rate": 0.25,         # 入Q率（前2名）
    "show_rate": 0.15,          # 入T率（前3名）
    "avg_distance_rating": 0.15, # 平均完成时间评分
    "rating_trend": 0.10        # 官方评分趋势
}

# 场次评分因子权重
RACE_SCORE_WEIGHTS = {
    "same_course": 0.25,        # 同马场往绩
    "same_distance": 0.25,      # 同路程往绩
    "draw_advantage": 0.15,     # 档位优势
    "weight_advantage": 0.10,   # 负磅优势
    "jockey_score": 0.15,       # 骑师评分
    "trainer_score": 0.10       # 练马师评分
}

# 档位优势分数（内档有利，沙田1000米除外）
# 默认：档位越小分越高，1档100分，14档20分
DRAW_SCORE_BASE = {draw: int(100 - (draw - 1) * (80 / 13)) for draw in range(1, 15)}

# 沙田草地1000米直路赛：外档有利
DRAW_SCORE_STRAIGHT = {draw: int(20 + (draw - 1) * (80 / 13)) for draw in range(1, 15)}

# 负磅舒适区计算参数
WEIGHT_COMFORT_RANGE = 5  # 舒适区范围 ±5磅


# ==================== 辅助函数 ====================

def get_zone(num: int) -> int:
    """获取号码所在分区（1-7），用于分区热度计算"""
    return (num - 1) // 7 + 1


def get_zone_numbers(zone: int) -> List[int]:
    """获取指定分区的所有号码"""
    start = (zone - 1) * 7 + 1
    end = start + 6
    return list(range(start, end + 1))


def calculate_absence(num: int, draws: List[Dict]) -> int:
    """计算号码当前遗漏期数"""
    absence = 0
    for draw in reversed(draws):
        if num in draw['numbers']:
            break
        absence += 1
    return absence


def get_stock_name_from_tushare(ts_code: str) -> str:
    """获取股票/指数名称（兼容stock-quant）"""
    return ts_code


def get_stock_daily(ts_code: str, days: int = 120) -> pd.DataFrame:
    """获取股票日线数据（兼容stock-quant）"""
    return pd.DataFrame()


# ==================== 1. 基础评分函数 ====================

def calculate_win_rate(past_performances_v2: List[Dict], recent_n: int = 10) -> float:
    """计算最近N场的胜率"""
    if not past_performances_v2:
        return 0.0
    recent = past_performances_v2[-recent_n:] if len(past_performances_v2) >= recent_n else past_performances_v2
    wins = sum(1 for p in recent if p.get('finishing_position') == 1)
    return wins / len(recent) if recent else 0.0


def calculate_place_rate(past_performances_v2: List[Dict], recent_n: int = 10) -> float:
    """计算最近N场的入Q率（前2名）"""
    if not past_performances_v2:
        return 0.0
    recent = past_performances_v2[-recent_n:] if len(past_performances_v2) >= recent_n else past_performances_v2
    places = sum(1 for p in recent if p.get('finishing_position', 0) in [1, 2])
    return places / len(recent) if recent else 0.0


def calculate_show_rate(past_performances_v2: List[Dict], recent_n: int = 10) -> float:
    """计算最近N场的入T率（前3名）"""
    if not past_performances_v2:
        return 0.0
    recent = past_performances_v2[-recent_n:] if len(past_performances_v2) >= recent_n else past_performances_v2
    shows = sum(1 for p in recent if p.get('finishing_position', 0) in [1, 2, 3])
    return shows / len(recent) if recent else 0.0


def calculate_rating_trend(past_performances_v2: List[Dict], recent_n: int = 5) -> float:
    """计算官方评分趋势"""
    if len(past_performances_v2) < 2:
        return 0.0
    recent = past_performances_v2[-recent_n:] if len(past_performances_v2) >= recent_n else past_performances_v2
    ratings = [p.get('rating', 0) for p in recent if p.get('rating')]
    if len(ratings) < 2:
        return 0.0
    x = list(range(len(ratings)))
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(ratings)
    sum_xy = sum(x[i] * ratings[i] for i in range(n))
    sum_x2 = sum(x[i] ** 2 for i in range(n))
    denominator = n * sum_x2 - sum_x ** 2
    if denominator == 0:
        return 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return slope


def calculate_avg_distance_rating(past_performances_v2: List[Dict], target_distance: int) -> float:
    """计算在目标路程附近的平均表现评分"""
    if not past_performances_v2:
        return 50.0
    scores = []
    weights = []
    for p in past_performances_v2:
        distance = p.get('distance', 0)
        if distance == 0:
            continue
        distance_diff = abs(distance - target_distance)
        if distance_diff <= 200:
            weight = 1.0 - (distance_diff / 200) * 0.5
        else:
            weight = 0.3
        pos = p.get('finishing_position', 0)
        if pos == 1:
            score = 100
        elif pos == 2:
            score = 85
        elif pos == 3:
            score = 70
        elif 4 <= pos <= 5:
            score = 55
        elif 6 <= pos <= 8:
            score = 40
        else:
            score = 25
        scores.append(score)
        weights.append(weight)
    if not scores:
        return 50.0
    total_weighted_score = sum(scores[i] * weights[i] for i in range(len(scores)))
    total_weight = sum(weights)
    return total_weighted_score / total_weight if total_weight > 0 else 50.0


def calculate_basic_score(horse_id: int, target_distance: int, past_performances_v2: List[Dict]) -> float:
    """计算基础评分（0-100）"""
    win_rate = calculate_win_rate(past_performances_v2)
    place_rate = calculate_place_rate(past_performances_v2)
    show_rate = calculate_show_rate(past_performances_v2)
    rating_trend = calculate_rating_trend(past_performances_v2)
    distance_rating = calculate_avg_distance_rating(past_performances_v2, target_distance)
    win_score = min(win_rate * 100, 100)
    place_score = min(place_rate * 100, 100)
    show_score = min(show_rate * 100, 100)
    trend_score = 50 + rating_trend * 5
    trend_score = max(0, min(100, trend_score))
    total_score = (
        win_score * BASIC_SCORE_WEIGHTS["win_rate"] +
        place_score * BASIC_SCORE_WEIGHTS["place_rate"] +
        show_score * BASIC_SCORE_WEIGHTS["show_rate"] +
        distance_rating * BASIC_SCORE_WEIGHTS["avg_distance_rating"] +
        trend_score * BASIC_SCORE_WEIGHTS["rating_trend"]
    )
    return round(total_score, 2)


# ==================== 2. 场次评分函数 ====================

def get_draw_score(draw: int, venue: str, distance: int) -> float:
    """计算档位优势分数"""
    if draw is None or draw < 1 or draw > 14:
        return 50.0
    if venue == "ST" and distance == 1000:
        score = DRAW_SCORE_STRAIGHT.get(draw, 50)
    else:
        score = DRAW_SCORE_BASE.get(draw, 50)
    return score


def get_weight_advantage_score(actual_weight: int, weight_comfort_range: Tuple[int, int]) -> float:
    """计算负磅优势分数"""
    if actual_weight is None:
        return 50.0
    comfort_min, comfort_max = weight_comfort_range
    if comfort_min <= actual_weight <= comfort_max:
        return 85.0
    elif actual_weight < comfort_min:
        diff = comfort_min - actual_weight
        return max(40, 85 - diff * 3)
    else:
        diff = actual_weight - comfort_max
        return max(30, 85 - diff * 4)


def calculate_same_course_score(horse_id: int, venue: str, past_performances_v2: List[Dict]) -> float:
    """计算同马场往绩评分"""
    venue_performances = [p for p in past_performances_v2 if p.get('venue') == venue]
    if not venue_performances:
        return 50.0
    recent = venue_performances[-3:] if len(venue_performances) >= 3 else venue_performances
    scores = []
    for p in recent:
        pos = p.get('finishing_position', 0)
        if pos == 1:
            scores.append(100)
        elif pos == 2:
            scores.append(85)
        elif pos == 3:
            scores.append(70)
        elif 4 <= pos <= 5:
            scores.append(55)
        else:
            scores.append(35)
    if not scores:
        return 50.0
    return sum(scores) / len(scores)


def calculate_same_distance_score(horse_id: int, distance: int, past_performances_v2: List[Dict]) -> float:
    """计算同路程往绩评分"""
    distance_performances = [p for p in past_performances_v2 if p.get('distance') == distance]
    if not distance_performances:
        return 50.0
    recent = distance_performances[-3:] if len(distance_performances) >= 3 else distance_performances
    scores = []
    for p in recent:
        pos = p.get('finishing_position', 0)
        if pos == 1:
            scores.append(100)
        elif pos == 2:
            scores.append(85)
        elif pos == 3:
            scores.append(70)
        elif 4 <= pos <= 5:
            scores.append(55)
        else:
            scores.append(35)
    if not scores:
        return 50.0
    return sum(scores) / len(scores)


def calculate_jockey_score(jockey_id: int, recent_n: int = 20) -> float:
    """计算骑师评分"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/jockeys?jockey_id=eq.{jockey_id}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            data = response.json()[0]
            win_rate = data.get('win_rate', 0)
            return min(win_rate * 100, 100)
        return 50.0
    except Exception as e:
        print(f"获取骑师评分失败: {e}")
        return 50.0


def calculate_trainer_score(trainer_id: int, venue: str) -> float:
    """计算练马师评分"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/trainers?trainer_id=eq.{trainer_id}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            data = response.json()[0]
            win_rate = data.get('win_rate', 0)
            return min(win_rate * 100, 100)
        return 50.0
    except Exception as e:
        print(f"获取练马师评分失败: {e}")
        return 50.0

#-------------
def calculate_race_score(
    horse_id: int,
    venue: str,
    distance: int,
    draw: int,
    actual_weight: int,
    jockey_id: int,
    trainer_id: int,
    weight_comfort_range: Tuple[int, int],
    past_performances_v2: List[Dict]
) -> float:
    """计算场次评分"""
    same_course = calculate_same_course_score(horse_id, venue, past_performances_v2)
    same_distance = calculate_same_distance_score(horse_id, distance, past_performances_v2)
    draw_score = get_draw_score(draw, venue, distance)
    weight_score = get_weight_advantage_score(actual_weight, weight_comfort_range)
    jockey_score = calculate_jockey_score(jockey_id)
    trainer_score = calculate_trainer_score(trainer_id, venue)
    total_score = (
        same_course * RACE_SCORE_WEIGHTS["same_course"] +
        same_distance * RACE_SCORE_WEIGHTS["same_distance"] +
        draw_score * RACE_SCORE_WEIGHTS["draw_advantage"] +
        weight_score * RACE_SCORE_WEIGHTS["weight_advantage"] +
        jockey_score * RACE_SCORE_WEIGHTS["jockey_score"] +
        trainer_score * RACE_SCORE_WEIGHTS["trainer_score"]
    )
    return round(total_score, 2)


# ==================== 3. 赔率校准 ====================

def normalize_odds(odds, max_odds: float = 99.0) -> float:
    """将赔率归一化为0-100的分数"""
    # 处理 None、空字符串、非数字等情况
    if odds is None or odds == '' or odds == 'null':
        return 50.0
    
    try:
        odds_float = float(odds)
    except (ValueError, TypeError):
        return 50.0
    
    if odds_float <= 0 or odds_float > max_odds:
        return 50.0
    
    # 归一化：赔率1.5映射到100，赔率99映射到0
    normalized = max(0, min(100, 100 * (1 - (odds_float - 1) / (max_odds - 1))))
    return normalized


def calculate_odds_score(odds_win) -> float:
    """计算赔率校准分"""
    return normalize_odds(odds_win)


# ==================== 4. Softmax胜率计算 ====================

def softmax_probabilities(scores: List[float], temperature: float = 0.8) -> List[float]:
    """将评分转换为概率"""
    if not scores:
        return []
    max_score = max(scores)
    exp_scores = [np.exp((s - max_score) / temperature) for s in scores]
    sum_exp = sum(exp_scores)
    if sum_exp == 0:
        return [1.0 / len(scores)] * len(scores)
    return [e / sum_exp for e in exp_scores]


def calculate_win_probabilities(
    basic_scores: List[float],
    race_scores: List[float],
    odds_scores: List[float],
    weights: Dict,
    odds_mix_ratio: float = 0.6
) -> List[float]:
    """计算最终胜率"""
    n = len(basic_scores)
    if n == 0:
        return []
    combined_scores = []
    for i in range(n):
        combined = (
            basic_scores[i] * weights.get("basic", 0.30) +
            race_scores[i] * weights.get("race", 0.40) +
            odds_scores[i] * weights.get("odds", 0.30)
        )
        combined_scores.append(combined)
    temperature = weights.get("temperature", 0.8)
    softmax_probs = softmax_probabilities(combined_scores, temperature)
    odds_probs = [odds_score / 100.0 for odds_score in odds_scores]
    total_odds = sum(odds_probs)
    if total_odds > 0:
        odds_probs = [p / total_odds for p in odds_probs]
    final_probs = []
    for i in range(n):
        final = odds_mix_ratio * softmax_probs[i] + (1 - odds_mix_ratio) * odds_probs[i]
        final_probs.append(final)
    total_final = sum(final_probs)
    if total_final > 0:
        final_probs = [p / total_final for p in final_probs]
    return final_probs


# ==================== 5. 综合评分函数 ====================

def get_horse_past_performances_v2(horse_id: int, limit: int = 10) -> List[Dict]:
    """从数据库获取马匹的历史往绩"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?horse_id=eq.{horse_id}&order=race_date.desc&limit={limit}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"获取马匹往绩失败: {e}")
        return []

#---------------
def get_horse_weight_comfort_range(horse_id: int) -> Tuple[int, int]:
    """获取马匹的负磅舒适区"""
    past = get_horse_past_performances_v2(horse_id, limit=20)
    winning_weights = []
    for p in past:
        pos = p.get('finishing_position', 0)
        weight = p.get('actual_weight', 0)
        if pos in [1, 2, 3] and weight > 0:
            winning_weights.append(weight)
    if len(winning_weights) >= 3:
        mean_weight = sum(winning_weights) / len(winning_weights)
        return (int(mean_weight - WEIGHT_COMFORT_RANGE), int(mean_weight + WEIGHT_COMFORT_RANGE))
    return (118, 128)

#-------------
def calculate_horse_score(
    horse_id: int,
    race_id: int,
    venue: str,
    distance: int,
    draw: int,
    actual_weight: int,
    jockey_id: int,
    trainer_id: int,
    odds_win: float,
    user_weights: Dict,
    incident: str = ""  # 新增参数
) -> Dict:
    """计算马匹的综合评分（事件分读缓存，不调 DeepSeek API）"""
    past_performances_v2 = get_horse_past_performances_v2(horse_id)
    basic_score = calculate_basic_score(horse_id, distance, past_performances_v2)
    weight_comfort_range = get_horse_weight_comfort_range(horse_id)
    race_score = calculate_race_score(
        horse_id, venue, distance, draw, actual_weight,
        jockey_id, trainer_id, weight_comfort_range, past_performances_v2
    )
    odds_score = calculate_odds_score(odds_win)
    
    incident_impact = 0
    if incident and incident not in ("无特别报告。", "無特別報告。"):
        if INCIDENT_LLM_OK and SUPABASE_URL:
            combined, _, _ = get_combined_incident_adjustment(
                incident, SUPABASE_URL, get_supabase_headers(use_secret=True)
            )
            incident_impact = combined
        else:
            incident_result = analyze_incident_with_deepseek(incident)
            incident_impact = incident_result.get("score", 0)
    
    # 综合评分 = 基础评分 + 场次评分 + 赔率评分 + 事件影响
    combined_score = (
        basic_score * user_weights.get("basic", 0.30) +
        race_score * user_weights.get("race", 0.40) +
        odds_score * user_weights.get("odds", 0.30)
    ) + incident_impact
    
    # 确保评分在 0-100 之间
    combined_score = max(0, min(100, combined_score))
    
    return {
        "horse_id": horse_id,
        "basic_score": round(basic_score, 2),
        "race_score": round(race_score, 2),
        "odds_score": round(odds_score, 2),
        "combined_score": round(combined_score, 2),
        "incident_impact": incident_impact,
        "weight_comfort_range": weight_comfort_range
    }
#----------
# ==================== DeepSeek API 集成 ====================
try:
    from openai import OpenAI
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False
    print("OpenAI 库未安装，DeepSeek 功能不可用")


def get_deepseek_client():
    """获取 DeepSeek 客户端"""
    if not DEEPSEEK_AVAILABLE:
        return None
    
    api_key = st.secrets.get("DEEPSEEK_API_KEY", "")
    base_url = st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    
    if not api_key:
        print("DeepSeek API Key 未配置")
        return None
    
    try:
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception as e:
        print(f"创建 DeepSeek 客户端失败: {e}")
        return None


def analyze_incident_with_deepseek(incident_text: str) -> Dict:
    """读取 incident LLM 缓存（热路径不调 DeepSeek API）。"""
    default_result = {"score": 0, "type": "normal", "suggestion": ""}
    if not incident_text or incident_text in ("无特别报告。", "無特別報告。"):
        return default_result
    if INCIDENT_LLM_OK and SUPABASE_URL:
        llm = get_llm_impact_from_cache(
            incident_text, SUPABASE_URL, get_supabase_headers(use_secret=True)
        )
        return {"score": llm, "type": "cached", "suggestion": ""}
    return default_result


def analyze_race_with_deepseek(race_info: Dict, runners: List[Dict]) -> str:
    """整场赛事 DeepSeek 分析（已停用；防止非管理员路径调用 API）。"""
    return "此功能已停用。Incident 分析请使用管理员 DeepSeek 补全（结果永久缓存）。"


def batch_analyze_incidents(incidents: List[str]) -> List[Dict]:
    """
    批量分析多个事件报告
    使用缓存避免重复调用 API
    """
    results = []
    cache = {}  # 简单缓存
    
    for incident in incidents:
        if incident in cache:
            results.append(cache[incident])
        else:
            result = analyze_incident_with_deepseek(incident)
            cache[incident] = result
            results.append(result)
    
    return results
#-----------
# ==================== 批量获取马匹往绩（优化版）====================

@st.cache_data(ttl=3600, show_spinner=False)
def get_horses_performances_batch(horse_ids: tuple) -> Dict[str, List[Dict]]:
    """
    批量获取多匹马的历史往绩
    参数：
        horse_ids: 马匹ID元组，如 ('H001', 'H002', ...)
    返回：
        { horse_id: [往绩记录列表] }
    """
    if not horse_ids:
        return {}
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 构建 IN 查询
        ids_str = ','.join([f"'{hid}'" for hid in horse_ids])
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?horse_id=in.({ids_str})&order=race_date.desc&limit=10000"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"批量获取失败: {response.status_code}")
            return {}
        
        data = response.json()
        
        # 构建缓存
        cache = {}
        for p in data:
            hid = p.get('horse_id')
            if not hid:
                continue
            if hid not in cache:
                cache[hid] = []
            cache[hid].append(p)
        
        # 对每个马匹的往绩按日期排序（最新的在前）
        for hid in cache:
            cache[hid].sort(key=lambda x: x.get('race_date', ''), reverse=True)
        
        print(f"批量获取 {len(horse_ids)} 匹马，共 {len(data)} 条记录")
        return cache
        
    except Exception as e:
        print(f"批量获取异常: {e}")
        return {}


def get_horse_past_performances_v2_optimized(horse_id: str, cache: Dict[str, List[Dict]], limit: int = 10) -> List[Dict]:
    """
    从缓存中获取马匹往绩（优化版）
    参数：
        horse_id: 马匹ID
        cache: 批量获取的缓存字典
        limit: 返回最近 N 场
    """
    if not horse_id or horse_id not in cache:
        return []
    
    performances = cache.get(horse_id, [])
    return performances[:limit]
#-----------------
def calculate_all_horses_scores(
    race_id: int,
    runners: List[Dict],
    user_weights: Dict
) -> Tuple[List[Dict], List[float]]:
    """计算一场赛事所有马匹的评分和胜率（优化版）
    - 批量获取所有马匹的往绩（1次请求）
    - 从缓存读取，避免 N+1 查询
    """
    print(f"=== calculate_all_horses_scores 被调用，runners数量: {len(runners)} ===")
    
    if not runners:
        return [], []
    # ... 其余代码
    
    # ==================== 第1步：批量获取所有马匹的往绩 ====================
    # 收集所有 horse_id
    horse_ids = []
    for runner in runners:
        horse_id = runner.get("horse_id")
        if horse_id:
            horse_ids.append(horse_id)
    
    # 去重并转为元组（用于缓存）
    unique_horse_ids = tuple(set(horse_ids))
    
    # 批量获取（只有1次HTTP请求）
    perf_cache = get_horses_performances_batch(unique_horse_ids)
    
    # ==================== 第2步：计算每匹马的评分 ====================
    scores = []
    basic_scores = []
    race_scores = []
    odds_scores = []
    
    for runner in runners:
        horse_id = runner.get("horse_id")
        if not horse_id:
            # 没有 horse_id 的马匹，使用默认评分
            basic_scores.append(50.0)
            race_scores.append(50.0)
            odds_scores.append(50.0)
            scores.append({
                "horse_id": None,
                "basic_score": 50.0,
                "race_score": 50.0,
                "odds_score": 50.0,
                "combined_score": 50.0,
                "win_probability": 50.0
            })
            continue
        
        # 从缓存获取往绩（不查询数据库）
        past_performances_v2 = get_horse_past_performances_v2_optimized(horse_id, perf_cache, limit=10)
        
        # 获取赔率
        odds_win = runner.get("odds_win")
        if odds_win is None or odds_win == '':
            odds_win = 10.0
        
        # 获取赛事信息
        venue = runner.get("venue", "ST")
        distance = runner.get("distance", 1200)
        draw = runner.get("draw")
        actual_weight = runner.get("actual_weight")
        jockey_id = runner.get("jockey_id")
        trainer_id = runner.get("trainer_id")
        
        # 计算基础评分
        basic_score = calculate_basic_score_fast(past_performances_v2, distance)
        
        # 计算场次评分
        weight_comfort_range = get_horse_weight_comfort_range_from_cache(horse_id, past_performances_v2)
        race_score = calculate_race_score_optimized(
            horse_id, venue, distance, draw, actual_weight,
            jockey_id, trainer_id, weight_comfort_range, past_performances_v2
        )
        
        # 赔率评分
        odds_score = calculate_odds_score(odds_win)
        
        scores.append({
            "horse_id": horse_id,
            "basic_score": round(basic_score, 2),
            "race_score": round(race_score, 2),
            "odds_score": round(odds_score, 2),
            "combined_score": round(basic_score * user_weights.get("basic", 0.30) + 
                                   race_score * user_weights.get("race", 0.40) + 
                                   odds_score * user_weights.get("odds", 0.30), 2),
        })
        
        basic_scores.append(basic_score)
        race_scores.append(race_score)
        odds_scores.append(odds_score)
    
    # ==================== 第3步：计算胜率 ====================
    probabilities = calculate_win_probabilities(
        basic_scores, race_scores, odds_scores,
        user_weights, user_weights.get("odds_mix_ratio", 0.6)
    )
    
    for i, prob in enumerate(probabilities):
        scores[i]["win_probability"] = round(prob * 100, 2)
    
    return scores, probabilities


def get_horse_weight_comfort_range_from_cache(horse_id: str, past_performances_v2: List[Dict]) -> Tuple[int, int]:
    """从缓存的往绩中获取马匹的负磅舒适区（不查询数据库）"""
    winning_weights = []
    for p in past_performances_v2:
        pos = p.get('finishing_position', 0)
        weight = p.get('actual_weight', 0)
        if pos in [1, 2, 3] and weight > 0:
            winning_weights.append(weight)
    
    WEIGHT_COMFORT_RANGE = 5
    if len(winning_weights) >= 3:
        mean_weight = sum(winning_weights) / len(winning_weights)
        return (int(mean_weight - WEIGHT_COMFORT_RANGE), int(mean_weight + WEIGHT_COMFORT_RANGE))
    return (118, 128)


def calculate_race_score_optimized(
    horse_id: str,
    venue: str,
    distance: int,
    draw: int,
    actual_weight: int,
    jockey_id: int,
    trainer_id: int,
    weight_comfort_range: Tuple[int, int],
    past_performances_v2: List[Dict]
) -> float:
    """
    计算场次评分（优化版，使用已获取的往绩）
    """
    # 同马场往绩
    same_course = calculate_same_course_score_from_cache(horse_id, venue, past_performances_v2)
    
    # 同路程往绩
    same_distance = calculate_same_distance_score_from_cache(horse_id, distance, past_performances_v2)
    
    # 档位优势
    draw_score = get_draw_score(draw, venue, distance)
    
    # 负磅优势
    weight_score = get_weight_advantage_score(actual_weight, weight_comfort_range)
    
    # 骑师评分（仍然需要查询，但可以后续优化）
    jockey_score = calculate_jockey_score(jockey_id)
    
    # 练马师评分
    trainer_score = calculate_trainer_score(trainer_id, venue)
    
    RACE_SCORE_WEIGHTS = {
        "same_course": 0.25,
        "same_distance": 0.25,
        "draw_advantage": 0.15,
        "weight_advantage": 0.10,
        "jockey_score": 0.15,
        "trainer_score": 0.10
    }
    
    total_score = (
        same_course * RACE_SCORE_WEIGHTS["same_course"] +
        same_distance * RACE_SCORE_WEIGHTS["same_distance"] +
        draw_score * RACE_SCORE_WEIGHTS["draw_advantage"] +
        weight_score * RACE_SCORE_WEIGHTS["weight_advantage"] +
        jockey_score * RACE_SCORE_WEIGHTS["jockey_score"] +
        trainer_score * RACE_SCORE_WEIGHTS["trainer_score"]
    )
    return round(total_score, 2)


def calculate_same_course_score_from_cache(horse_id: str, venue: str, past_performances_v2: List[Dict]) -> float:
    """从缓存的往绩中计算同马场评分"""
    venue_performances = [p for p in past_performances_v2 if p.get('venue') == venue]
    if not venue_performances:
        return 50.0
    
    recent = venue_performances[:3] if len(venue_performances) >= 3 else venue_performances
    scores = []
    for p in recent:
        pos = p.get('finishing_position', 0)
        if pos == 1:
            scores.append(100)
        elif pos == 2:
            scores.append(85)
        elif pos == 3:
            scores.append(70)
        elif 4 <= pos <= 5:
            scores.append(55)
        else:
            scores.append(35)
    
    return sum(scores) / len(scores) if scores else 50.0


def calculate_same_distance_score_from_cache(horse_id: str, distance: int, past_performances_v2: List[Dict]) -> float:
    """从缓存的往绩中计算同路程评分"""
    distance_performances = [p for p in past_performances_v2 if p.get('distance') == distance]
    if not distance_performances:
        return 50.0
    
    recent = distance_performances[:3] if len(distance_performances) >= 3 else distance_performances
    scores = []
    for p in recent:
        pos = p.get('finishing_position', 0)
        if pos == 1:
            scores.append(100)
        elif pos == 2:
            scores.append(85)
        elif pos == 3:
            scores.append(70)
        elif 4 <= pos <= 5:
            scores.append(55)
        else:
            scores.append(35)
    
    return sum(scores) / len(scores) if scores else 50.0


# ==================== 6. 数据库写入函数 ====================

def save_race_runners_with_scores(race_id: int, runners_with_scores: List[Dict]) -> bool:
    """将评分结果保存到数据库"""
    try:
        headers = get_supabase_headers(use_secret=True)
        for runner in runners_with_scores:
            data = {
                "basic_score": runner.get("basic_score"),
                "race_score": runner.get("race_score"),
                "odds_score": runner.get("odds_score"),
                "overall_score": runner.get("combined_score"),
                "win_probability": runner.get("win_probability", 0) / 100
            }
            url = f"{SUPABASE_URL}/rest/v1/race_runners?runner_id=eq.{runner.get('runner_id')}"
            response = requests.patch(url, headers=headers, json=data)
            if response.status_code not in [200, 204]:
                print(f"保存评分失败: {response.text}")
                return False
        return True
    except Exception as e:
        print(f"保存评分失败: {e}")
        return False


def get_race_runners_from_db(race_id: int) -> List[Dict]:
    """从数据库获取一场赛事的出赛马匹列表"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/race_runners?race_id=eq.{race_id}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"获取出赛马匹失败: {e}")
        return []


def update_race_result(race_id: int, results: List[Dict]) -> bool:
    """更新赛事结果"""
    try:
        headers = get_supabase_headers(use_secret=True)
        for result in results:
            data = {
                "finishing_position": result.get("finishing_position"),
                "winning_distance": result.get("winning_distance")
            }
            url = f"{SUPABASE_URL}/rest/v1/race_runners?runner_id=eq.{result.get('runner_id')}"
            response = requests.patch(url, headers=headers, json=data)
            if response.status_code not in [200, 204]:
                print(f"更新赛果失败: {response.text}")
                return False
        race_url = f"{SUPABASE_URL}/rest/v1/races?race_id=eq.{race_id}"
        race_response = requests.patch(race_url, headers=headers, json={"race_status": "RESULT"})
        return race_response.status_code in [200, 204]
    except Exception as e:
        print(f"更新赛果失败: {e}")
        return False


# ==================== 7. 数据更新函数 ====================

def fetch_race_data_from_api(race_date: str, venue: str, race_no: int) -> Optional[Dict]:
    """从Node.js API获取赛事数据"""
    API_BASE_URL = st.secrets.get("HKJC_API_URL", "http://localhost:3000/api")
    try:
        url = f"{API_BASE_URL}/race"
        params = {"date": race_date, "venue": venue, "race_no": race_no}
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API请求失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"API请求异常: {e}")
        return None
#--------------
# ==================== 导入爬虫模块 ====================
try:
    from hkjc_advanced_scraper_v2 import parse_race_result
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False
    print("爬虫模块不可用，请确保 hkjc_advanced_scraper_v2.py 在项目根目录")


def save_race_result_to_db(record: Dict) -> bool:
    """保存单条成绩记录到数据库（去重）"""
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 检查是否已存在（根据唯一键：race_date + venue + race_no + horse_no）
        check_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?race_date=eq.{record['race_date']}&venue=eq.{record['venue']}&race_no=eq.{record['race_no']}&horse_no=eq.{record['horse_no']}"
        check_response = requests.get(check_url, headers=headers)
        
        if check_response.status_code == 200 and check_response.json():
            # 已存在，跳过
            return True
        
        # 插入新记录
        insert_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2"
        insert_response = requests.post(insert_url, headers=headers, json=record)
        
        if insert_response.status_code not in [200, 201]:
            print(f"保存失败: {insert_response.text}")
            return False
        
        return True
    except Exception as e:
        print(f"保存异常: {e}")
        return False

#---------------
def get_latest_race_date_from_db() -> Optional[str]:
    """从 past_performances_v2 表获取最新的赛事日期"""
    try:
        headers = get_supabase_headers(use_secret=True)
        # ✅ 改为查询 past_performances_v2 表
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?order=race_date.desc&limit=1&select=race_date"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('race_date')
        return None
    except Exception as e:
        print(f"获取最新赛事日期失败: {e}")
        return None


def run_database_cleanup(keep_count: int = 20000) -> Dict:
    """调用 Supabase manual_cleanup，各数据表超过 keep_count 行时删除最旧记录。"""
    result: Dict = {
        "deleted": 0,
        "kept": 0,
        "tables": [],
        "error": None,
    }
    if not SUPABASE_URL:
        result["error"] = "Supabase 未配置"
        return result
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/rpc/manual_cleanup"
        response = requests.post(
            url,
            headers=headers,
            json={"p_keep": keep_count},
            timeout=120,
        )
        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}: {response.text[:300]}"
            return result

        payload = response.json() or {}
        tables = payload.get("tables") or []
        result["tables"] = tables
        result["deleted"] = int(payload.get("total_deleted") or 0)
        result["kept"] = keep_count

        for row in tables:
            if row.get("error"):
                print(f"cleanup {row.get('table')}: {row.get('error')}")
            elif row.get("skipped"):
                print(f"cleanup {row.get('table')}: skipped ({row.get('reason')})")

        return result
    except Exception as exc:
        result["error"] = str(exc)
        print(f"run_database_cleanup failed: {exc}")
        return result


def cleanup_old_records(keep_count: int = 20000) -> Dict:
    """兼容旧调用：统一走 Supabase manual_cleanup RPC。"""
    return run_database_cleanup(keep_count=keep_count)


#----------------
# ==================== 智能赛期获取（从官网下拉菜单）====================

def get_official_race_dates_from_hkjc() -> List[str]:
    """
    从香港赛马会官网解析下拉菜单，获取所有可用赛期日期
    返回：日期列表，格式 YYYY-MM-DD
    """
    race_dates = []
    
    try:
        # 使用一个已知有数据的日期作为入口（如最近一场赛事）
        url = "https://racing.hkjc.com/zh-hk/local/information/localresults?racedate=2026/06/07"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找赛期下拉菜单（通常是一个 select 元素）
        # 方法1：查找 name="selectDate" 或 id="selectDate" 的 select
        select_elem = soup.find('select', {'name': 'selectDate'})
        if not select_elem:
            select_elem = soup.find('select', {'id': 'selectDate'})
        
        if select_elem:
            for option in select_elem.find_all('option'):
                value = option.get('value', '')
                if value and value.strip():
                    # value 格式可能是 YYYY/MM/DD 或 YYYY-MM-DD
                    # 统一转换为 YYYY-MM-DD
                    if '/' in value:
                        date_str = value.replace('/', '-')
                    else:
                        date_str = value
                    
                    # 只保留有效日期格式
                    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                        race_dates.append(date_str)
        else:
            # 方法2：如果没有下拉菜单，尝试从页面链接中提取
            # 查找所有包含 racedate= 的链接
            for link in soup.find_all('a', href=True):
                href = link['href']
                match = re.search(r'racedate=(\d{4}/\d{2}/\d{2})', href)
                if match:
                    date_str = match.group(1).replace('/', '-')
                    if date_str not in race_dates:
                        race_dates.append(date_str)
        
        # 去重并排序
        race_dates = sorted(list(set(race_dates)))
        
        print(f"从官网获取到 {len(race_dates)} 个赛期: {race_dates[:5]}...")
        return race_dates
        
    except Exception as e:
        print(f"获取官方赛期失败: {e}")
        return []

#----------------
def get_db_latest_race_date() -> Optional[str]:
    """从 past_performances_v2
    表获取最新的赛事日期"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?order=race_date.desc&limit=1&select=race_date"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('race_date')
        return None
    except Exception as e:
        print(f"获取数据库最新日期失败: {e}")
        return None

#-----------------
def save_race_results_batch(results: List[Dict]) -> bool:
    """
    批量保存一场赛事的全部结果到 past_performances_v2 表
    并自动更新 horses_v2 表
    """
    if not results:
        return True
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 1. 清理每条记录，确保字段名与 past_performances_v2 表匹配
        clean_results = []
        for record in results:
            clean_record = {}
            
            # 字段名映射（爬虫返回的字段名 → 表字段名）
            field_mapping = {
                'race_date': 'race_date',
                'venue': 'venue',
                'race_no': 'race_no',
                'position': 'position',
                'horse_no': 'horse_no',
                'horse_name': 'horse_name',
                'horse_name_en': 'horse_name_en',
                'horse_id': 'horse_id',
                'age': 'age',
                'sex': 'sex',
                'jockey': 'jockey',
                'trainer': 'trainer',
                'actual_weight': 'actual_weight',
                'body_weight': 'body_weight',
                'draw': 'draw',
                'lbw_raw': 'lbw_raw',
                'running_position': 'running_position',
                'finish_time': 'finish_time',
                'finish_seconds': 'finish_seconds',
                'odds': 'odds',
                'closing_profile': 'closing_profile',
                'incident': 'incident',
                'race_class': 'race_class',
                'distance': 'distance',
                'going': 'going',
                'sectional_times': 'sectional_times',
                'dividends_json': 'dividends_json'
            }
            
            for old_key, new_key in field_mapping.items():
                if old_key in record:
                    value = record[old_key]
                    if value is None or value == '':
                        clean_record[new_key] = None
                    else:
                        clean_record[new_key] = value
            
            clean_results.append(clean_record)
        
        # 批量 upsert 到 past_performances_v2
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/past_performances_v2",
            headers={
                **headers,
                "Prefer": "resolution=merge-duplicates"
            },
            json=clean_results
        )
        
        if response.status_code not in [200, 201]:
            print(f"保存成绩失败: {response.text}")
            return False
        
        # 2. 提取新马匹并更新 horses_v2
        new_horses = []
        for record in results:
            horse_id = record.get('horse_id')
            horse_name = record.get('horse_name')
            horse_name_en = record.get('horse_name_en', '')
            sex = record.get('sex', '')
            
            if not horse_id or not horse_name:
                continue
            
            import re
            birth_year = None
            match = re.search(r'HK_(\d{4})_', horse_id)
            if match:
                arrival_year = int(match.group(1))
                birth_year = arrival_year - 3
            
            new_horses.append({
                'horse_id': horse_id,
                'name_zh': horse_name,
                'name_en': horse_name_en,
                'sex': sex,
                'birth_year': birth_year
            })
        
        # 去重并插入 horses_v2（跳过已存在的）
        if new_horses:
            unique_horses = {h['horse_id']: h for h in new_horses}.values()
            for horse in unique_horses:
                supabase_request('POST', 'horses_v2', data=horse)
        
        print(f"批量保存成功: {len(results)} 条成绩, {len(unique_horses)} 匹马")
        return True
        
    except Exception as e:
        print(f"批量保存异常: {e}")
        return False
#-------
# ==================== 从赛期表获取官方赛期 ====================

def get_race_dates_from_fixture(year: int, month: int) -> List[str]:
    """
    从香港赛马会赛期表页面获取指定月份的所有赛期日期
    参数：
        year: 年份，如 2026
        month: 月份，如 6
    返回：
        日期列表，格式 YYYY-MM-DD
    """
    race_dates = []
    
    try:
        url = f"https://racing.hkjc.com/zh-hk/local/information/fixture?calyear={year}&calmonth={month}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找所有包含日期数字的单元格
        all_tds = soup.find_all('td')
        
        for td in all_tds:
            # 获取单元格文本
            td_text = td.get_text(strip=True)
            
            # 检查是否是纯数字日期（1-31）
            if td_text.isdigit() and 1 <= int(td_text) <= 31:
                day = int(td_text)
                
                # 检查这个单元格内是否包含赛事信息
                # 有赛事信息（如"班"、"米"等）的才是赛马日
                full_text = td.get_text()
                has_race_info = False
                
                race_indicators = ['班', '米', '賽', '草地', '泥地', '讓賽', '盃', '級賽']
                for indicator in race_indicators:
                    if indicator in full_text:
                        has_race_info = True
                        break
                
                # 检查是否有 class 包含 race/fixture 等关键字
                if td.get('class'):
                    class_str = ' '.join(td.get('class'))
                    if re.search(r'race|fixture|event', class_str, re.I):
                        has_race_info = True
                
                if has_race_info:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    race_dates.append(date_str)
        
        return sorted(list(set(race_dates)))
        
    except Exception as e:
        print(f"获取 {year}-{month} 赛期表失败: {e}")
        return []


def get_all_race_dates(start_year: int = 2025, end_year: int = None) -> List[str]:
    """
    获取指定年份范围内所有月份的赛期
    """
    if end_year is None:
        end_year = datetime.now().year
    
    all_dates = []
    
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            # 不获取未来太远的月份
            if year == end_year and month > datetime.now().month + 1:
                break
            
            dates = get_race_dates_from_fixture(year, month)
            all_dates.extend(dates)
            
            # 避免请求过快
            time.sleep(0.3)
    
    return sorted(list(set(all_dates)))


def get_db_latest_race_date() -> Optional[str]:
    """从 past_performances_v2
    表获取最新的赛事日期"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?order=race_date.desc&limit=1&select=race_date"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('race_date')
        return None
    except Exception as e:
        print(f"获取数据库最新日期失败: {e}")
        return None

#----------------
def sync_all_data() -> Dict:
    """
    智能同步所有数据（优化版）
    1. 从数据库获取最新日期
    2. 从最新日期遍历到今天
    3. 爬虫自动判断是否有赛事
    4. 批量写入，提高性能
    5. 提前终止无效场次循环
    6. 清理超过 20000 行的旧数据
    """
    result = {"success": False, "new_races": 0, "new_records": 0, "error": None}
    
    if not SCRAPER_AVAILABLE:
        result["error"] = "爬虫模块不可用，请确保 hkjc_advanced_scraper_v2.py 在项目根目录"
        return result
    
    try:
        # ==================== 第1步：获取数据库最新日期 ====================
        db_latest_date = get_db_latest_race_date()
        print(f"数据库最新日期: {db_latest_date}")
        
        # ==================== 第2步：确定需要遍历的日期范围 ====================
        if db_latest_date:
            start_date = datetime.strptime(db_latest_date, '%Y-%m-%d') + timedelta(days=1)
        else:
            start_date = datetime(2025, 1, 1)
        
        end_date = datetime.now() - timedelta(days=1)  # 排除当天
        
        if start_date > end_date:
            result["success"] = True
            st.info("所有数据已是最新，无需更新")
            return result
        
        total_days = (end_date - start_date).days + 1
        st.info(f"📅 将检查 {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')} 共 {total_days} 天")
        
        # ==================== 第3步：遍历日期范围 ====================
        venues = ['ST', 'HV']
        current = start_date
        total_new_races = 0
        total_new_records = 0
        
        # 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        days_processed = 0
        
        while current <= end_date:
            days_processed += 1
            progress_bar.progress(days_processed / total_days)
            
            date_str = current.strftime("%Y/%m/%d")
            display_date = current.strftime("%Y-%m-%d")
            status_text.text(f"正在检查 {display_date}... ({days_processed}/{total_days})")
            
            date_has_races = False  # 标记当天是否有赛事
            
            for venue in venues:
                empty_count = 0  # ⭐ 连续空场次计数器
                
                for race_no in range(1, 13):
                    try:
                        # ⭐ 提前终止：连续 3 场无数据，跳出循环
                        if empty_count >= 3:
                            print(f"  连续 3 场无数据，提前结束 {venue} 的检查")
                            break
                        
                        # 显示当前检查的场次（可选，用于调试）
                        # status_text.text(f"正在检查 {display_date} {venue} 第{race_no}场...")
                        
                        race_info, results = parse_race_result(date_str, venue, race_no)
                        
                        if results and len(results) > 0:
                            # 有数据，重置空场次计数
                            empty_count = 0
                            date_has_races = True
                            
                            # 为每条记录添加赛事元数据
                            for record in results:
                                record['race_class'] = race_info.get('race_class', '')
                                record['distance'] = race_info.get('distance', 0)
                                record['going'] = race_info.get('going', '')
                                record['sectional_times'] = json.dumps(race_info.get('sectional_times', []))
                            
                            # 批量保存
                            success = save_race_results_batch(results)
                            if success:
                                total_new_races += 1
                                total_new_records += len(results)
                                print(f"✅ {display_date} {venue} 第{race_no}场: {len(results)} 条记录")
                            else:
                                print(f"❌ {display_date} {venue} 第{race_no}场: 保存失败")
                            
                            # ⭐ 有数据时轻微延迟（避免请求过快）
                            time.sleep(0.3)
                        else:
                            # 无数据，增加空场次计数
                            empty_count += 1
                            # ⭐ 无数据时不需要延迟，直接继续
                        
                    except Exception as e:
                        print(f"⚠️ {display_date} {venue} 第{race_no}场: {e}")
                        empty_count += 1
                        continue
            
            # 更新状态显示
            if date_has_races:
                status_text.text(f"✅ {display_date} 完成，发现赛事")
            else:
                status_text.text(f"⏭️ {display_date} 无赛事")
            
            current += timedelta(days=1)
        
        progress_bar.empty()
        status_text.empty()
        
        # ==================== 第4步：显示结果 ====================
        result["success"] = True
        result["new_races"] = total_new_races
        result["new_records"] = total_new_records
        
        if total_new_races > 0:
            st.success(f"✅ 更新完成！新增 {total_new_races} 场赛事，{total_new_records} 条成绩记录")
        else:
            st.info("未发现新数据")
        
        # ==================== 第5步：清理旧数据（各表超过 20000 行删最旧）====================
        with st.spinner("正在检查并清理旧数据..."):
            cleanup_result = run_database_cleanup(keep_count=20000)
            if cleanup_result.get("error"):
                st.warning(
                    f"数据清理未执行：{cleanup_result['error']}（请先在 Supabase 执行 scripts/manual_cleanup.sql）"
                )
            elif cleanup_result.get("deleted", 0) > 0:
                st.info(
                    f"已清理 {cleanup_result['deleted']} 条旧记录，各数据表保持在 20000 行以内"
                )
            else:
                st.info("各数据表均未超过 20000 行上限，无需清理")
        
        # ==================== 第6步：清除缓存 ====================
        st.cache_data.clear()
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        st.error(f"更新失败: {e}")
        print(f"更新异常: {e}")
        return result

#-------------
def update_all_data_for_date(race_date: str, show_progress: bool = True) -> Dict:
    """更新指定日期的所有赛事数据 - 直接从 API 获取并同步"""
    result = {"success": 0, "failed": 0, "total": 0}
    
    try:
        API_BASE_URL = st.secrets.get("HKJC_API_URL", "")
        
        if not API_BASE_URL:
            if show_progress:
                st.error("API地址未配置")
            return {"success": 0, "failed": 0, "total": 0, "error": "API地址未配置"}
        
        # 1. 直接从 API 获取该日期的赛事列表
        meetings_url = f"{API_BASE_URL}/meetings"
        if show_progress:
            st.info(f"正在调用 API: {meetings_url}")
        meetings_response = requests.get(meetings_url, timeout=30)
        
        if meetings_response.status_code != 200:
            if show_progress:
                st.error(f"API返回错误: {meetings_response.status_code}")
            return result
        
        meetings_data = meetings_response.json()
        meetings = meetings_data.get("data", [])
        
        # 2. 找到目标日期的赛事
        target_meeting = None
        for meeting in meetings:
            if meeting.get("date") == race_date:
                target_meeting = meeting
                break
        
        if not target_meeting:
            if show_progress:
                st.info(f"{race_date} 暫無賽事")
            return result
        
        # 3. 从 races 数组获取赛事数量和列表
        races_list = target_meeting.get("races", [])
        result["total"] = len(races_list)
        
        if result["total"] == 0:
            if show_progress:
                st.info(f"{race_date} 没有赛事")
            return result
        
        # 4. 获取场地代码
        venue = target_meeting.get("venueCode", "ST")
        
        # 5. 逐场同步
        for race_info in races_list:
            race_no = race_info.get("no")
            try:
                sync_url = f"{API_BASE_URL}/sync/race"
                sync_response = requests.post(sync_url, json={
                    "date": race_date,
                    "venue": venue,
                    "raceNo": race_no
                }, timeout=60)
                
                if sync_response.status_code == 200 and sync_response.json().get("success"):
                    result["success"] += 1
                    if show_progress:
                        st.success(f"✅ 第{race_no}场同步成功")
                else:
                    result["failed"] += 1
                    if show_progress:
                        st.warning(f"❌ 第{race_no}场同步失败")
            except Exception as e:
                result["failed"] += 1
                if show_progress:
                    st.error(f"❌ 第{race_no}场异常: {e}")
        
        return result
        
    except Exception as e:
        if show_progress:
            st.error(f"更新数据失败: {e}")
        return result
        
    except Exception as e:
        st.error(f"更新数据失败: {e}")
        return {"success": 0, "failed": result.get("total", 0), "total": result.get("total", 0), "error": str(e)}
#---------------
def sync_future_races(days: int = 14) -> Dict:
    """从数据库获取未来赛事（不再调用API）"""
    results = {"success": 0, "failed": 0, "total": 0}
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        future_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/races?race_date=gte.{today}&race_date=lte.{future_date}&order=race_date.asc,race_no.asc"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            races = response.json()
            results["success"] = len(races)
            results["total"] = len(races)
            return results
        else:
            return results
    except Exception as e:
        print(f"获取未来赛事失败: {e}")
        return results
# ==================== 第2次代码结束 ====================
# 注意：没有 if __name__ == "__main__"，因为主入口在第1次代码中

if __name__ == "__main__":
    main()
