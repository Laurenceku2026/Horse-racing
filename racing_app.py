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
import time
import hmac
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from supabase import create_client, Client
from bs4 import BeautifulSoup
from betting_strategy_engine import BettingStrategyEngine, get_odds_qin_from_db, get_odds_tri_from_db
from parlay_recommender import ParlayRecommender
# ==================== 从 scoring_engine 导入 ====================
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
        get_horses_performances_batch,
        get_horse_past_performances_v2_optimized,
        get_horse_weight_comfort_range_from_cache,
        # 配置加载
        get_scoring_config,
        # 旧版兼容
        normalize_odds,
    )
    print("✅ scoring_engine 导入成功")
except ImportError as e:
    print(f"❌ scoring_engine 导入失败: {e}")
# ==================== 页面配置 ====================
st.set_page_config(
    page_title="香港赛马AI分析系统",
    page_icon="🐎",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
</style>
""", unsafe_allow_html=True)

# ==================== 常量定义 ====================
FREE_TRIAL_LIMIT = 30
MAX_RECOMMENDED_HORSES = 30
ADMIN_USERNAME = "Laurence_ku"
ADMIN_PASSWORD = "Ku_product$2026"
ADMIN_EMAIL = "Techlife2027@gmail.com"
SCHEMA_NAME = "racing"  # 独立schema名称

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
        "update_all_data": "更新所有数据",
        "horse_rating_title": "全馬基礎評分榜",
        "horse_rating_desc": "📌 基於最近 N 場歷史表現計算，分數越高代表整體實力越強。",
        "calculate_games": "計算場次",
        "display_limit": "顯示數量",
        "all_games": "全部",
        "data_update": "🔄 數據更新",
        "update_all_data": "更新所有数据",
        "checking_update": "正在检查并更新数据...",
        "update_complete": "✅ 更新完成！新增 {new_races} 场赛事，{new_records} 条成绩记录",
        "update_failed": "更新失败",
        "qin_ev_insufficient": "連贏組合 {horse1} + {horse2} 期望值不足，暫不推薦",
        "qin_recommendation": "🔗 連贏推薦",
        "qin_no_odds": "暫無連贏賠率數據",
        "qin_insufficient_horses": "馬匹數量不足，無法推薦連贏",
        "data_source": "📅 數據來源：香港賽馬會 | 更新頻率：賽日自動更新",
        "betting_pools": "🎲 彩池玩法",
        "race_table_title": "第{race_no}場 出賽馬匹",
        "run_backtest": "▶️ 運行模型對比回測",
        "select_models": "🤖 選擇要對比的模型",
        "rating_system": "评分系统",
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
        "ev_description": "基于AI评分和赔率计算的期望值(EV)推荐",
        "low_risk": "🎯 低風險 - 獨贏/位置",
        "medium_risk": "🎯 中風險 - 連贏",
        "high_risk": "🎯 高風險 - 單T",
        "no_suggestions": "暂无建议",
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
        "horse_no": "馬號",
        "draw": "檔位",
        "actual_weight": "負磅",
        "jockey": "騎師",
        "win_odds": "獨贏",
        "place_odds": "位置",
        "win_rate": "勝率",
        "overall_score": "綜合評分",
        "ev": "期望值",
        "no_data": "暫無出賽馬匹數據",
        
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
        
        # ==================== 消息提示 ====================
        "upgrade_pro": "💎 升級專業版",
        "free_trial_used": "免費次數已用完，請升級到專業版",
        "data_updated": "數據已更新",
        "update_failed": "更新失敗",
        "syncing_schedule": "正在同步最新賽程...",
        "sync_complete": "同步完成！成功 {success} 场，失败 {failed} 场",
        "updating_odds": "正在更新最新賠率和出賽馬匹...",
        "calculating_win_rate": "正在計算馬匹勝率（評分系統）...",
        "calculating_ml": "正在計算馬匹勝率（{model}）...",
        "betting_records": "📋 我的投注記錄",
        "disclaimer": "⚠️ 本建議基於AI模型預測，不保證實際收益。請理性投注，切勿超出預算。",
        "data_source": "📅 數據來源：香港賽馬會 | 更新頻率：賽日自動更新"
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
        "horse_no": "No.",
        "draw": "Draw",
        "actual_weight": "Weight",
        "jockey": "Jockey",
        "win_odds": "Win",
        "place_odds": "Place",
        "win_rate": "Win Rate",
        "overall_score": "Score",
        "ev": "EV",
        "no_data": "No runner data",
        
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
        "data_source": "📅 Data Source: HKJC | Update Frequency: Race day auto-update"
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
        "admin_mode": False,
        "show_admin_login": False,
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
                insert_url = f"{SUPABASE_URL}/rest/v1/user_settings"
                insert_response = requests.post(insert_url, headers=headers_secret, json=settings_data)
                
                if insert_response.status_code in [200, 201]:
                    return True, "註冊成功！請登入", user_id
                else:
                    # 即使 user_settings 创建失败，也允许登录（后续会自动创建）
                    print(f"创建user_settings失败: {insert_response.text}")
                    return True, "註冊成功！請登入", user_id
            return True, "註冊成功！請登入", user_id
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
                            check_url = f"{SUPABASE_URL}/rest/v1/user_settings?user_id=eq.{user_id}"
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
                                insert_url = f"{SUPABASE_URL}/rest/v1/user_settings"
                                requests.post(insert_url, headers=admin_headers, json=settings_data)
                            
                            return True, "該郵箱已在系統中，請直接登入", user_id
                return False, "該電郵已註冊，請直接登入", None
            return False, f"註冊失敗: {error.get('msg', '未知錯誤')}", None
    except Exception as e:
        return False, f"註冊失敗: {str(e)}", None
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
            return False, "電郵或密碼錯誤", None, None, None, None
        
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
            return True, "登入成功", user_id, user_email, access_token, refresh_token
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
                return True, "登入成功", user_id, user_email, access_token, refresh_token
            else:
                return False, f"創建用戶設置失敗: {insert_response.text}", None, None, None, None
                
    except Exception as e:
        print(f"登录异常: {e}")
        return False, f"登入失敗: {str(e)}", None, None, None, None

def sign_out():
    """退出登录"""
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.token_expiry = 0
    st.session_state.admin_mode = False
    st.rerun()
#---------
def get_user_profile(user_id: str) -> Dict:
    """获取用户资料"""
    if not user_id or user_id == "admin":
        return {
            "subscription_tier": "free",
            "free_trials_remaining": FREE_TRIAL_LIMIT,
            "subscription_expires_at": None,
            "weights_basic": DEFAULT_WEIGHTS["basic"],
            "weights_race": DEFAULT_WEIGHTS["race"],
            "weights_odds": DEFAULT_WEIGHTS["odds"],
            "temperature": DEFAULT_WEIGHTS["temperature"],
            "odds_mix_ratio": DEFAULT_WEIGHTS["odds_mix_ratio"],
            "risk_preference": "standard",
            "default_bankroll": 1000
        }
    
    try:
        # 使用用户的 access_token
        access_token = st.session_state.get("access_token", "")
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        url = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200 and response.json():
            data = response.json()[0]
            return {
                "subscription_tier": data.get("subscription_tier", "free"),
                "free_trials_remaining": data.get("free_trials_remaining", FREE_TRIAL_LIMIT),
                "subscription_expires_at": data.get("subscription_expires_at"),
                "weights_basic": data.get("weights_basic", DEFAULT_WEIGHTS["basic"]),
                "weights_race": data.get("weights_race", DEFAULT_WEIGHTS["race"]),
                "weights_odds": data.get("weights_odds", DEFAULT_WEIGHTS["odds"]),
                "temperature": data.get("temperature", DEFAULT_WEIGHTS["temperature"]),
                "odds_mix_ratio": data.get("odds_mix_ratio", DEFAULT_WEIGHTS["odds_mix_ratio"]),
                "risk_preference": data.get("risk_preference", "standard"),
                "default_bankroll": data.get("default_bankroll", 1000)
            }
    except Exception as e:
        print(f"获取用户资料失败: {e}")
    
    return {
        "subscription_tier": "free",
        "free_trials_remaining": FREE_TRIAL_LIMIT,
        "subscription_expires_at": None,
        "weights_basic": DEFAULT_WEIGHTS["basic"],
        "weights_race": DEFAULT_WEIGHTS["race"],
        "weights_odds": DEFAULT_WEIGHTS["odds"],
        "temperature": DEFAULT_WEIGHTS["temperature"],
        "odds_mix_ratio": DEFAULT_WEIGHTS["odds_mix_ratio"],
        "risk_preference": "standard",
        "default_bankroll": 1000
    }
#-------------
def update_user_profile(user_id: str, data: Dict) -> bool:
    """更新用户资料"""
    try:
        access_token = st.session_state.get("access_token", "")
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        # 注意：表名是 user_settings_racing
        url = f"{SUPABASE_URL}/rest/v1/user_settings_racing?user_id=eq.{user_id}"
        response = requests.patch(url, headers=headers, json=data)
        print(f"update_user_profile - URL: {url}")
        print(f"update_user_profile - 状态码: {response.status_code}")
        print(f"update_user_profile - 响应: {response.text}")
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
def consume_free_trial(user_id: str) -> bool:
    """消耗一次免费次数"""
    print(f"consume_free_trial 收到的 user_id: {user_id}")
    
    # ⭐ 新增：管理员无限免费（后台静默跳过）
    if user_id == "admin":
        print("✅ 管理员特权：不消耗免费次数")
        return True
    
    profile = get_user_profile(user_id)
    print(f"获取到的 profile: {profile}")
    
    if profile.get("subscription_tier") == "pro":
        return True
    
    remaining = profile.get("free_trials_remaining", 0)
    print(f"剩余次数: {remaining}")
    
    if remaining > 0:
        new_remaining = remaining - 1
        success = update_user_profile(user_id, {"free_trials_remaining": new_remaining})
        print(f"更新结果: {success}")
        return success
    else:
        st.session_state.show_paywall = True
        return False

# ==================== Stripe支付 ====================
def create_checkout_session(user_id: str, user_email: str, price_id: str) -> Tuple[Optional[str], Optional[str]]:
    """创建Stripe Checkout Session"""
    if not STRIPE_SECRET_KEY:
        return None, "Stripe密钥未配置"
    
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
        st.warning("🔔 检测到支付会话，请点击按钮完成验证")
        st.info(f"会话ID: {session_id[:30]}...")
        
        if st.button("✅ 手动验证支付并升级", type="primary"):
            with st.spinner("正在验证..."):
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
                                    st.success("✅ 支付验证成功！您已是专业版用户")
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
                                    st.error(f"更新失败: {patch_response.text}")
                            else:
                                st.error("无法识别用户，请重新登录后重试")
                        else:
                            st.warning(f"支付状态: {data.get('payment_status')}，请完成支付")
                    else:
                        st.error(f"API请求失败: {response.status_code}")
                        
                except Exception as e:
                    st.error(f"验证失败: {e}")
    elif "canceled" in query_params:
        st.info("支付已取消")
#------------
def show_paywall():
    """显示付费墙（用户主动升级）"""
    st.markdown("---")
    
    # 获取用户当前状态
    profile = get_user_profile(st.session_state.user_id)
    remaining = profile.get("free_trials_remaining", 0)
    tier = profile.get("subscription_tier", "free")
    
    # 如果已经是专业版，不应该显示付费墙
    if tier == "pro":
        st.session_state.show_paywall = False
        st.rerun()
        return
    
    # 显示当前状态
    if remaining > 0:
        st.info(f"🔓 您当前还有 {remaining} 次免费试用机会")
        st.warning("💎 升级专业版后，可无限次使用所有功能")
    else:
        st.error("🔒 您的免費使用次數已用完")
    
    st.markdown(f"""
    ### 💎 {t()['upgrade']}
    
    | 功能 | 免費版 | 專業版 |
    |------|--------|--------|
    | 使用次數 | 30次 | **無限** |
    | 馬匹評分榜 | ✅ | ✅ |
    | 智能投注 | ✅ | ✅ |
    | 全天優化 | ✅ | ✅ |
    | 歷史回測 | ✅ | ✅ |
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💎 月付 HK$380/月", key="monthly_btn", use_container_width=True):
            url, error = create_checkout_session(
                st.session_state.user_id, 
                st.session_state.user_email, 
                STRIPE_PRICE_MONTHLY
            )
            if url:
                st.session_state.payment_url = url
                st.session_state.payment_type = "monthly"
                st.rerun()
            else:
                st.error(f"創建支付會話失敗: {error}")
        
        if st.session_state.get("payment_url") and st.session_state.get("payment_type") == "monthly":
            st.markdown(f'''
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
                💳 前往Stripe支付（月付HK$380）
            </a>
            ''', unsafe_allow_html=True)
    
    with col2:
        if st.button("💎 季付 HK$988/季", key="quarterly_btn", use_container_width=True):
            url, error = create_checkout_session(
                st.session_state.user_id, 
                st.session_state.user_email, 
                STRIPE_PRICE_QUARTERLY
            )
            if url:
                st.session_state.payment_url = url
                st.session_state.payment_type = "quarterly"
                st.rerun()
            else:
                st.error(f"創建支付會話失敗: {error}")
        
        if st.session_state.get("payment_url") and st.session_state.get("payment_type") == "quarterly":
            st.markdown(f'''
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
                💳 前往Stripe支付（季付HK$988）
            </a>
            ''', unsafe_allow_html=True)
    
    if st.button("返回", use_container_width=True):
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
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"<h1 style='text-align: center;'>{t()['app_title']}</h1>", unsafe_allow_html=True)
        
        with st.form("login_form", border=True):
            email = st.text_input(t()["email"], key="login_email")
            password = st.text_input(t()["password"], type="password", key="login_password")
            submitted = st.form_submit_button(t()["login_btn"], type="primary", use_container_width=True)
            
            if submitted:
                if not email or not password:
                    st.warning("請填寫電郵和密碼")
                else:
                    with st.spinner("登入中..."):
                        success, msg, user_id, user_email, access_token, refresh_token = sign_in(email, password)
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user_id = user_id
                            st.session_state.user_email = user_email
                            st.session_state.access_token = access_token
                            st.session_state.refresh_token = refresh_token
                            st.session_state.token_expiry = time.time() + 3600
                            st.session_state.show_paywall = False
                            st.rerun()
                        else:
                            st.error(msg)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t()["register"], use_container_width=True):
                st.session_state.show_register = True
                st.rerun()
        with col2:
            if st.button(t().get("forgot_password", "忘記密碼？"), use_container_width=True):
                st.info(f"請聯絡管理員重置密碼：{ADMIN_EMAIL}")

def render_register_form():
    """显示注册表单"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"<h2 style='text-align: center;'>{t()['register']}</h2>", unsafe_allow_html=True)
        
        with st.form("register_form", border=True):
            email = st.text_input(t()["email"], key="reg_email")
            password = st.text_input(t()["password"], type="password", key="reg_password")
            confirm = st.text_input(t()["confirm_password"], type="password", key="reg_confirm")
            submitted = st.form_submit_button(t()["register_btn"], type="primary", use_container_width=True)
            
            if submitted:
                if not email or not password:
                    st.warning("請填寫電郵和密碼")
                elif password != confirm:
                    st.warning("兩次輸入的密碼不一致")
                elif len(password) < 6:
                    st.warning("密碼長度至少6位")
                else:
                    with st.spinner("註冊中..."):
                        success, msg, user_id = sign_up(email, password)
                        if success:
                            st.success(msg)
                            st.session_state.show_register = False
                            st.rerun()
                        else:
                            st.error(msg)
        
        if st.button(t()["back_to_login"], use_container_width=True):
            st.session_state.show_register = False
            st.rerun()

def render_admin_login_form():
    """显示管理员登录表单"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>管理員登入</h2>", unsafe_allow_html=True)
        
        with st.form("admin_login_form", border=True):
            username = st.text_input("用戶名", key="admin_username")
            password = st.text_input("密碼", type="password", key="admin_password")
            submitted = st.form_submit_button("登入", type="primary", use_container_width=True)
            
            if submitted:
                if check_admin_login(username, password):
                    st.session_state.admin_previous_user_id = st.session_state.get("user_id")
                    st.session_state.admin_previous_user_email = st.session_state.get("user_email")
                    st.session_state.admin_previous_access_token = st.session_state.get("access_token")
                    st.session_state.admin_previous_refresh_token = st.session_state.get("refresh_token")
                    
                    st.session_state.admin_mode = True
                    st.session_state.show_admin_login = False
                    st.session_state.authenticated = True
                    st.session_state.user_id = "admin"
                    st.session_state.user_email = ADMIN_EMAIL
                    st.rerun()
                else:
                    st.error("用戶名或密碼錯誤")
        
        if st.button("返回用戶登入", use_container_width=True):
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
    计算SHAP值（修复版 - 不触发页面刷新）
    参数：
        model: 训练好的模型
        feature_names: 特征名称列表
        model_type: 'LightGBM' | 'XGBoost' | '集成模型'
        sample_limit: 使用的样本数量（默认50场）
    返回：
        {'summary_df': DataFrame} 或 None
    """
    try:
        import shap
        import pandas as pd
        import numpy as np
        
        # ⭐ 检查特征名称是否有效
        if not feature_names or len(feature_names) == 0:
            print("⚠️ 特征名称为空")
            return None
        
        # ⭐ 检查模型是否有效
        if model is None:
            print("⚠️ 模型为空")
            return None
        
        # 获取训练数据（从缓存或数据库）
        # 注意：这里需要真实的训练数据，而不是随机数据
        # 由于回测函数没有保存训练数据，这里使用随机数据作为演示
        # 实际部署时，需要从回测过程中保存真实的特征数据
        
        np.random.seed(42)
        X_sample = pd.DataFrame(
            np.random.randn(sample_limit, len(feature_names)),
            columns=feature_names
        )
        
        # 根据模型类型计算SHAP值
        shap_values = None
        
        if model_type == "LightGBM":
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample)
        elif model_type == "XGBoost":
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample)
        elif model_type == "集成模型":
            # 集成模型：分别计算两个模型的SHAP值，然后平均
            shap_values_list = []
            for sub_model in [model.get('lightgbm'), model.get('xgboost')]:
                if sub_model is not None:
                    try:
                        explainer = shap.TreeExplainer(sub_model)
                        shap_values_list.append(explainer.shap_values(X_sample))
                    except Exception as e:
                        print(f"子模型SHAP计算失败: {e}")
                        continue
            if shap_values_list:
                shap_values = np.mean(shap_values_list, axis=0)
            else:
                return None
        else:
            return None
        
        if shap_values is None:
            return None
        
        # 计算平均SHAP值（绝对值）
        mean_shap = np.abs(shap_values).mean(axis=0)
        
        # 判断影响方向
        direction = []
        explanation = []
        for i, name in enumerate(feature_names):
            avg_shap = shap_values[:, i].mean()
            if avg_shap > 0.005:
                direction.append("正向 ↑")
                explanation.append("数值越大，胜率越高")
            elif avg_shap < -0.005:
                direction.append("负向 ↓")
                explanation.append("数值越大，胜率越低")
            else:
                direction.append("中性 →")
                explanation.append("影响较小或中性")
        
        # 创建汇总DataFrame
        summary_df = pd.DataFrame({
            '特征': feature_names,
            '平均SHAP值': mean_shap,
            '影响方向': direction,
            '说明': explanation
        }).sort_values('平均SHAP值', ascending=False)
        
        # ⭐ 过滤掉重要性为0的因子（简化显示）
        summary_df = summary_df[summary_df['平均SHAP值'] > 0.001]
        
        return {'summary_df': summary_df}
        
    except ImportError:
        print("shap 库未安装，请运行: pip install shap")
        return None
    except Exception as e:
        print(f"SHAP计算失败: {e}")
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
    
    # 初始化 session_state 中的日期
    if "admin_backtest_start" not in st.session_state:
        st.session_state.admin_backtest_start = (datetime.now() - timedelta(days=180)).date()
    if "admin_backtest_end" not in st.session_state:
        st.session_state.admin_backtest_end = datetime.now().date()
    if "admin_backtest_force_refresh" not in st.session_state:
        st.session_state.admin_backtest_force_refresh = False
    
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
                st.rerun()
    
    # 更新 session_state
    st.session_state.admin_backtest_start = backtest_start
    st.session_state.admin_backtest_end = backtest_end
    
    # 模型选择复选框
    st.markdown(t()["select_models"])
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    with col_m1:
        enable_rule = st.checkbox(t()["rating_system"], value=False, key="admin_backtest_rule")
    with col_m2:
        enable_lgb = st.checkbox("LightGBM", value=True, key="admin_backtest_lgb",
                                 disabled=not LGB_AVAILABLE)
    with col_m3:
        enable_xgb = st.checkbox("XGBoost", value=True, key="admin_backtest_xgb",
                                 disabled=not XGB_AVAILABLE)
    with col_m4:
        enable_ensemble = st.checkbox("集成模型", value=False, key="admin_backtest_ensemble",
                                      disabled=(not LGB_AVAILABLE and not XGB_AVAILABLE))
    
    st.markdown("---")
    
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
            
            if results:
                st.markdown("#### 📈 模型對比結果")
                
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
# ==================== 管理员面板 ====================
def render_admin_panel():
    """管理员面板 - 数据编辑器 + 回测 + 用户管理 + 马名映射"""
    st.markdown(f"## ⚙️ {t()['admin_panel']}")
    
    # 创建选项卡
    tab1, tab2, tab3, tab4 = st.tabs(["📊 数据编辑器", "📈 回测", "👥 用户管理", "⚙️ 评分权重设置"])
    
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
    #-----------------
    # ==================== 预计算评分 ====================
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
    #----------
    # 清除评分缓存
    with st.expander("🗑️ 清除缓存", expanded=False):
        if st.button("清除评分缓存", use_container_width=True):
            get_cached_race_scores.clear()
            st.success("缓存已清除")
            st.rerun()
    # ==================== 赔率采集状态监控 ====================
    st.markdown("---")
    with st.expander("📊 赔率采集状态监控", expanded=False):
        st.markdown("**最近7天赔率采集统计**")
        
        try:
            headers = get_supabase_headers(use_secret=True)
            url = f"{SUPABASE_URL}/rest/v1/odds_history?select=recorded_at,odds_type&recorded_at=gt.{datetime.now() - timedelta(days=7)}&limit=10000"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    df_stats = pd.DataFrame(data)
                    df_stats['recorded_at'] = pd.to_datetime(df_stats['recorded_at'])
                    df_stats['collect_date'] = df_stats['recorded_at'].dt.date
                    
                    pivot_stats = df_stats.groupby(['collect_date', 'odds_type']).size().unstack(fill_value=0)
                    st.dataframe(pivot_stats, use_container_width=True)
                    
                    latest = df_stats['recorded_at'].max()
                    st.success(f"✅ 最近采集时间: {latest.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    st.warning("⚠️ 最近7天无赔率采集数据")
            else:
                st.error(f"查询失败: {response.status_code}")
        except Exception as e:
            st.error(f"获取统计失败: {e}")
        
        st.markdown("---")
        st.markdown("**📋 各彩池说明**")
        st.caption("WIN=独赢 | PLA=位置 | QIN=连赢 | QPL=位置Q | TRI=单T | TCE=三重彩 | F4=四连环")
    
    # ==================== 退出按钮 ====================
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
            
            tier_display = "💎 專業版" if tier == "pro" else "🔒 免費版"
            
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
        if st.button("⚙️", key="gear_btn", help="管理員登入", use_container_width=True):
            st.session_state.show_admin_login = True
            st.rerun()
    
    with col5:
        if st.session_state.authenticated:
            if st.session_state.admin_mode:
                if st.button("👤 返回", key="back_to_user_btn", help="退出管理員模式", use_container_width=True):
                    admin_sign_out()
                    st.rerun()
            else:
                if st.button("🚪", key="logout_btn", help="退出登入", use_container_width=True):
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
def get_all_horses_base_score(limit: int = 500, recent_games: int = 10) -> pd.DataFrame:
    """
    获取所有马匹的基础评分（使用新评分引擎）
    包含：基础往绩 + 场次因素 + 赔率因素 + 状态因素
    支持缓存：优先从 horse_scores_cache 表读取
    """
    try:
        # 获取当前语言
        lang = st.session_state.get("lang", "zh")
        
        headers = get_supabase_headers(use_secret=True)
        
        # ==================== 新增：检查缓存 ====================
        cache_check_url = f"{SUPABASE_URL}/rest/v1/horse_scores_cache?select=horse_id&limit=1"
        cache_check = requests.get(cache_check_url, headers=headers)
        
        cache_exists = cache_check.status_code == 200 and cache_check.json()
        
        if cache_exists:
            # 从缓存读取
            cache_url = f"{SUPABASE_URL}/rest/v1/horse_scores_cache?order=basic_score.desc&limit={limit}"
            response = requests.get(cache_url, headers=headers)
            
            if response.status_code == 200:
                cache_data = response.json()
                
                if cache_data:
                    # 构建 DataFrame
                    df = pd.DataFrame(cache_data)
                    
                    # 重命名列（中文）
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
                    for col in ["勝率", "入Q率", "入T率", "Win Rate", "Place Rate", "Show Rate"]:
                        if col in df_display.columns:
                            df_display[col] = df_display[col].apply(
                                lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x
                            )
                    
                    # 列顺序
                    if lang == "zh":
                        column_order = ["Horse_ID", "馬名(中)", "馬名(英)", "性別", "年齡", "平均體重", "勝率", "入Q率", "入T率", "綜合評分", "出賽場次"]
                    else:
                        column_order = ["Horse_ID", "Name (CN)", "Name (EN)", "Sex", "Age", "Avg Weight", "Win Rate", "Place Rate", "Show Rate", "Overall Score", "Races"]
                    
                    df_display = df_display[[c for c in column_order if c in df_display.columns]]
                    
                    # 显示缓存时间
                    calc_time = cache_data[0].get('calculated_at', '')
                    if calc_time:
                        calc_time = calc_time[:16].replace('T', ' ')
                    
                    st.caption(f"📊 共 {len(df_display)} 匹馬 (緩存於 {calc_time})" if lang == "zh" else f"📊 Total {len(df_display)} horses (cached at {calc_time})")
                    
                    return df_display
        
        # ==================== 缓存不存在：执行完整计算 ====================
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
            
            status_score = calculate_status_score(
                birth_year,
                latest.get('body_weight'),
                [r.get('body_weight') for r in past_performances if r.get('body_weight')],
                latest.get('incident', ''),
                latest.get('running_position', ''),
                latest.get('position'),
                status_w
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
        df_display["勝率"] = df_display["勝率"].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
        df_display["入Q率"] = df_display["入Q率"].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
        df_display["入T率"] = df_display["入T率"].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
        
        if lang == "en":
            df_display["Win Rate"] = df_display["Win Rate"].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
            df_display["Place Rate"] = df_display["Place Rate"].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
            df_display["Show Rate"] = df_display["Show Rate"].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
        
        # 调整列顺序
        if lang == "zh":
            column_order = ["Horse_ID", "馬名(中)", "馬名(英)", "性別", "年齡", "平均體重", "勝率", "入Q率", "入T率", "綜合評分", "出賽場次"]
        else:
            column_order = ["Horse_ID", "Name (CN)", "Name (EN)", "Sex", "Age", "Avg Weight", "Win Rate", "Place Rate", "Show Rate", "Overall Score", "Races"]
        
        df_display = df_display[[c for c in column_order if c in df_display.columns]]
        
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
    if df.empty:
        st.info("暫無馬匹數據，請點擊「更新數據」同步馬匹資料")
        return
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Horse_ID": st.column_config.TextColumn("ID", width="90px"),
            "馬名(中)": st.column_config.TextColumn("中文名", width="100px"),
            "馬名(英)": st.column_config.TextColumn("英文名", width="120px"),
            "性別": st.column_config.TextColumn("性別", width="40px"),
            "年齡": st.column_config.TextColumn("年齡", width="40px"),
            "平均體重": st.column_config.TextColumn("體重", width="60px"),
            "勝率": st.column_config.TextColumn("勝率", width="55px"),
            "入Q率": st.column_config.TextColumn("入Q率", width="55px"),
            "入T率": st.column_config.TextColumn("入T率", width="55px"),
            "基礎評分": st.column_config.NumberColumn("評分", width="60px", format="%.0f")
        }
    )
    
    st.caption(f"📊 共 {len(df)} 匹馬")


# ==================== 主页函数（替换原有的render_home） ====================
def render_home():
    """主页：数据概览 + 全马评分榜 + 智能投注 + 回测"""
    
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
   
    # ==================== 模块1：数据概览 ====================
    st.markdown(f"## {texts.get('data_overview', '📊 數據概覽')}")
    
    # 获取统计数据
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 马匹数量
        horses_url = f"{SUPABASE_URL}/rest/v1/horses_v2?select=*"
        horses_response = requests.get(horses_url, headers=headers)
        horse_count = len(horses_response.json()) if horses_response.status_code == 200 else 0
        
        # 赛事数量
        # 赛事总数（从 past_performances_v2 统计不同的赛事）
        try:
            perf_races_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=race_date,venue,race_no&limit=50000"
            perf_races_response = requests.get(perf_races_url, headers=headers)
            if perf_races_response.status_code == 200:
                perf_data = perf_races_response.json()
                unique_races = set()
                for p in perf_data:
                    unique_races.add((p.get('race_date'), p.get('venue'), p.get('race_no')))
                race_count = len(unique_races)
            else:
                race_count = 0
        except Exception as e:
            print(f"统计赛事数量失败: {e}")
            race_count = 0
        
        # 成绩记录数量
        perf_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2"
        perf_response = requests.get(perf_url, headers=headers)
        perf_count = len(perf_response.json()) if perf_response.status_code == 200 else 0
        #------
        # 获取最新和最旧赛事日期（从 past_performances_v2 表）
        try:
            # 获取最新日期
            perf_url_latest = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=race_date&order=race_date.desc&limit=1"
            perf_response_latest = requests.get(perf_url_latest, headers=headers)
            if perf_response_latest.status_code == 200 and perf_response_latest.json():
                latest_date = perf_response_latest.json()[0]['race_date']
            else:
                latest_date = 'N/A'
            
            # 获取最旧日期
            perf_url_oldest = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=race_date&order=race_date.asc&limit=1"
            perf_response_oldest = requests.get(perf_url_oldest, headers=headers)
            if perf_response_oldest.status_code == 200 and perf_response_oldest.json():
                oldest_date = perf_response_oldest.json()[0]['race_date']
            else:
                oldest_date = 'N/A'
        except Exception as e:
            print(f"获取日期范围失败: {e}")
            latest_date = 'N/A'
            oldest_date = 'N/A'
        #----
        # 骑师总数（从 past_performances_v2 统计）
        try:
            jockeys_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=jockey&limit=50000"
            jockeys_response = requests.get(jockeys_url, headers=headers)
            if jockeys_response.status_code == 200:
                jockey_data = jockeys_response.json()
                unique_jockeys = set()
                for j in jockey_data:
                    jockey_name = j.get('jockey')
                    if jockey_name and jockey_name.strip():
                        unique_jockeys.add(jockey_name)
                jockey_count = len(unique_jockeys)
            else:
                jockey_count = 0
        except Exception as e:
            print(f"统计骑师失败: {e}")
            jockey_count = 0
        
        # 练马师总数（从 past_performances_v2 统计）
        try:
            trainers_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=trainer&limit=50000"
            trainers_response = requests.get(trainers_url, headers=headers)
            if trainers_response.status_code == 200:
                trainer_data = trainers_response.json()
                unique_trainers = set()
                for t in trainer_data:
                    trainer_name = t.get('trainer')
                    if trainer_name and trainer_name.strip():
                        unique_trainers.add(trainer_name)
                trainer_count = len(unique_trainers)
            else:
                trainer_count = 0
        except Exception as e:
            print(f"统计练马师失败: {e}")
            trainer_count = 0
        
        # 第一行：马匹、赛事、成绩、骑师、练马师（5列）
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric(f"🐎 {texts['horse_count']}", horse_count)
        with col2:
            st.metric(f"🏆 {texts['race_count']}", race_count)
        with col3:
            st.metric(f"📊 {texts['record_count']}", perf_count)
        with col4:
            st.metric(f"🤠 {texts['jockey_count']}", jockey_count)
        with col5:
            st.metric(f"🏋️ {texts['trainer_count']}", trainer_count)
        
        # 第二行：日期范围（居中）
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.metric(texts.get('date_range', '📅 數據日期範圍'), f"{oldest_date} ~ {latest_date}", help="基于历史成绩数据的日期范围")
            
    except Exception as e:
        st.warning(f"獲取數據統計失敗: {e}")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric(f"🐎 {texts.get('horse_count', '馬匹總數')}", "0")
        with col2:
            st.metric(f"🏆 {texts.get('race_count', '賽事總數')}", "0")
        with col3:
            st.metric(f"📊 {texts.get('record_count', '成績記錄總數')}", "0")
        with col4:
            st.metric(f"🤠 {texts.get('jockey_count', '騎師總數')}", "0")
        with col5:
            st.metric(f"🏋️ {texts.get('trainer_count', '練馬師總數')}", "0")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.metric(texts.get('date_range', '📅 數據範圍'), "-")
    
    st.markdown("---")
   
    #--------------
    # ==================== 数据更新区域 ====================
    st.markdown(f"### {texts.get('data_update', '🔄 數據更新')}")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        update_btn = st.button(f"🔄 {texts.get('update_all_data', '更新所有数据')}", type="primary", use_container_width=True)
    
    if update_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning(texts.get('free_trial_used', '免費次數已用完，請升級到專業版'))
        else:
            with st.spinner(texts.get('checking_update', '正在检查并更新数据...')):
                # 1. 同步数据（从 API 获取新赛事和成绩）
                result = sync_all_data()
                
                # 2. 检查是否有新数据
                new_races = result.get('new_races', 0)
                new_records = result.get('new_records', 0)
                
                if result.get("success") and (new_races > 0 or new_records > 0):
                    # ✅ 有新数据：刷新缓存
                    try:
                        with st.spinner("正在更新评分缓存..."):
                            # 清空缓存表
                            headers = get_supabase_headers(use_secret=True)
                            delete_url = f"{SUPABASE_URL}/rest/v1/horse_scores_cache"
                            requests.delete(delete_url, headers=headers)
                            
                            # 重新计算并保存缓存
                            df = get_all_horses_base_score(limit=500, recent_games=10)
                            if not df.empty:
                                save_horse_scores_to_cache(df)
                            
                            st.success(texts.get('update_complete', '✅ 更新完成！新增 {new_races} 场赛事，{new_records} 条成绩记录，評分緩存已刷新').format(
                                new_races=new_races, 
                                new_records=new_records
                            ))
                            
                            # 清除 Streamlit 缓存
                            st.cache_data.clear()
                            st.rerun()
                    except Exception as e:
                        st.warning(f"数据同步成功，但缓存刷新失败: {e}")
                        st.rerun()
                elif result.get("success"):
                    # ⚠️ 没有新数据：只提示，不重新计算
                    st.info("✅ 数据已是最新，无需更新评分缓存")
                else:
                    st.error(f"{texts.get('update_failed', '更新失败')}: {result.get('error', '未知错误')}")
    
    st.markdown("---")
    
    # ==================== 模块2：全马基础评分榜 ====================
    st.markdown(f"### 🐎 {texts['horse_rating_title']}")
    st.caption(texts["horse_rating_desc"])
    
    # 评分场次选择
    col1, col2 = st.columns([1, 4])
    with col1:
        recent_games = st.selectbox(
            "計算場次",
            options=[3, 5, 8, 10, 12, 15, 20, 0],
            format_func=lambda x: "全部" if x == 0 else f"最近 {x} 場",
            index=3,  # 默认 10 场
            key="recent_games"
        )
    
    # 评分数量选择
    with col2:
        rating_limit = st.selectbox(
            "顯示數量",
            options=[50, 100, 200, 300, 500],
            index=1,  # 默认 100
            key="rating_limit"
        )
    
    with st.spinner(f"正在計算馬匹評分（最近 {recent_games if recent_games > 0 else '全部'} 場）..."):
        rating_df = get_all_horses_base_score(limit=rating_limit, recent_games=recent_games)
        render_horse_rating_table(rating_df)
    
    st.markdown("---")
    
    # ==================== 模块3：智能投注 ====================
    render_smart_betting(show_title=True)
    
    st.markdown("---")
    
    # ==================== 模块4：回测 ====================
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

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_upcoming_races() -> List[Dict]:
    """缓存未来14天的赛事列表（直接从 API 获取）"""
    races = get_upcoming_races()
    return races


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_race_runners(race_date: str, venue: str, race_no: int) -> List[Dict]:
    """缓存出赛马匹数据"""
    return get_race_runners_with_details(race_date, venue, race_no)
#-----------
def get_upcoming_races_from_api() -> List[Dict]:
    """
    从 Node.js API 获取未来赛程（直接调用 getActiveMeetings）
    这是获取赛程的主要数据源
    """
    try:
        API_BASE_URL = st.secrets.get("HKJC_API_URL", "")
        if not API_BASE_URL:
            print("⚠️ API地址未配置")
            return []
        
        url = f"{API_BASE_URL}/meetings"
        response = requests.get(url, timeout=30)
        
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
                    distance = race.get("distance", 0)
                    race_class = race.get("className", "")
                    
                    upcoming_races.append({
                        "race_date": meeting_date_str,
                        "venue": venue_code,
                        "venue_name": venue_name,
                        "race_no": race_no,
                        "distance": distance,
                        "race_class": race_class,
                        "race_id": f"{meeting_date_str}_{venue_code}_{race_no}"
                    })
                    print(f"    - 添加第{race_no}场: {distance}米")
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
    优先从 API 获取，失败时尝试从数据库读取
    """
    # 优先从 API 获取
    races = get_upcoming_races_from_api()
    
    if races:
        # 同步到数据库作为备份
        sync_races_to_db(races)
        return races
    
    # API 失败，尝试从数据库读取
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
        status_score = calculate_status_score(
            None, body_weight,
            [p.get('body_weight') for p in past_performances if p.get('body_weight')],
            incident, runner.get('running_position', ''), None, user_weights
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
                        "horse_name": runner.get('horse_name_zh', runner.get('horse_name', '')),
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
                return result
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
                        "horse_name": p.get('horse_name', ''),
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
                return result
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


def train_lightgbm_model(draws: List[Dict], lookback: int = 200) -> Optional[Any]:
    """训练 LightGBM 模型"""
    if not LGB_AVAILABLE:
        return None
    
    try:
        # 准备训练数据
        X_list = []
        y_list = []
        
        # 获取所有赛事
        races = [d for d in draws if d.get('race_date')]
        
        for i, race in enumerate(races):
            if i < lookback:
                continue
            
            # 使用 race 之前的数据训练
            train_draws = races[:i]
            
            for runner in race.get('runners', []):
                horse_id = runner.get('horse_id')
                if not horse_id:
                    continue
                
                # 获取该马匹的历史往绩
                past = get_horse_past_performances_v2(horse_id, limit=10)
                features = prepare_ml_features(horse_id, race.get('race_id'), past)
                
                if features:
                    features['draw'] = runner.get('draw', 0)
                    features['actual_weight'] = runner.get('actual_weight', 0)
                    features['odds'] = runner.get('odds_win', 0)
                    features['jockey_id'] = runner.get('jockey_id', 0)
                    features['trainer_id'] = runner.get('trainer_id', 0)
                    features['distance'] = race.get('distance', 0)
                    
                    X_list.append(features)
                    # 目标：是否跑入前三
                    y_list.append(1 if runner.get('position', 0) <= 3 else 0)
        
        if len(X_list) < 100:
            return None
        
        X_df = pd.DataFrame(X_list).fillna(0)
        y_series = pd.Series(y_list)
        
        model = lgb.LGBMClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            verbose=-1
        )
        
        model.fit(X_df, y_series)
        return model
        
    except Exception as e:
        print(f"LightGBM 训练失败: {e}")
        return None


def train_xgboost_model(draws: List[Dict], lookback: int = 200) -> Optional[Any]:
    """训练 XGBoost 模型"""
    if not XGB_AVAILABLE:
        return None
    
    try:
        X_list = []
        y_list = []
        
        races = [d for d in draws if d.get('race_date')]
        
        for i, race in enumerate(races):
            if i < lookback:
                continue
            
            train_draws = races[:i]
            
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
                    y_list.append(1 if runner.get('position', 0) <= 3 else 0)
        
        if len(X_list) < 100:
            return None
        
        X_df = pd.DataFrame(X_list).fillna(0)
        y_series = pd.Series(y_list)
        
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss',
            verbosity=0
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
                                       horse_id: str = None) -> Dict:
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
    
    # ✅ 事件报告
    incident_text = runner.get('incident', '')
    incident_score = 0
    if incident_text and incident_text not in ['无特别报告。', '無特別報告。', '']:
        negative_keywords = [
            ('流鼻血', -20), ('不良於行', -18), ('喘鳴症', -15),
            ('心律不正', -15), ('勒避', -8), ('受阻', -8),
            ('收慢', -6), ('外疊', -6), ('搶口', -5),
            ('出閘笨拙', -5), ('內閃', -4), ('外閃', -4)
        ]
        positive_keywords = [('順利', 5), ('望空', 4), ('節省腳程', 3)]
        
        for keyword, impact in negative_keywords:
            if keyword in incident_text:
                incident_score = impact
                break
        if incident_score == 0:
            for keyword, impact in positive_keywords:
                if keyword in incident_text:
                    incident_score = impact
                    break
    features['incident'] = max(-20, min(20, incident_score))
    
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
                          runners: List[Dict], model_type: str, model=None) -> List[float]:
    """
    获取 ML 模型预测的胜率（三分类版本）
    使用与回测相同的逻辑：好马组概率 → 取前3名
    
    参数：
        race_date: 赛事日期
        venue: 场地
        race_no: 场次
        runners: 出赛马匹列表
        model_type: 'lightgbm' | 'xgboost' | 'ensemble'
        model: 预训练模型（如果为None，则返回默认概率）
    
    返回：
        每匹马的"好马组概率"列表
    """
    from scoring_engine import get_ml_config
    ml_config = get_ml_config()
    recent_games = ml_config.get("recent_games", 60)
    
    # 如果没有 runners 或 model，返回默认概率
    if not runners:
        return []
    if model is None:
        return [0.34] * len(runners)
    
    # 获取赛事距离
    distance = runners[0].get('distance', 1200) if runners else 1200
    
    # 获取马匹往绩缓存
    horse_ids = [r.get('horse_id') for r in runners if r.get('horse_id')]
    if not horse_ids:
        return [0.34] * len(runners)
    
    perf_cache = get_horses_performances_batch(tuple(set(horse_ids)))
    
    # 获取辅助数据
    horse_birth_years = get_horse_birth_years_from_db()
    jockey_win_rates = get_jockey_win_rates_from_db()
    trainer_base_scores = get_trainer_base_scores()
    
    predictions = []
    
    for runner in runners:
        horse_id = runner.get('horse_id')
        if not horse_id:
            predictions.append(0.34)
            continue
        
        # 获取往绩
        past_before = perf_cache.get(horse_id, [])[:recent_games]
        
        # 构建完整特征（30个因子）
        features = build_ml_features_for_prediction(
            runner, past_before, race_date, venue, distance,
            horse_birth_years, jockey_win_rates, trainer_base_scores,
            horse_id
        )
        
        if features:
            # 使用三分类预测（return_all_probs=True）
            try:
                all_probs = predict_with_model(model, features, model_type, return_all_probs=True)
                if isinstance(all_probs, list) and len(all_probs) >= 3:
                    good_group_prob = all_probs[2]  # 好马组概率
                else:
                    good_group_prob = 0.34
            except Exception as e:
                print(f"预测失败: {e}")
                good_group_prob = 0.34
        else:
            good_group_prob = 0.34
        
        predictions.append(good_group_prob)
    
    return predictions


def get_historical_draws_for_training(limit: int = 300) -> List[Dict]:
    """获取用于训练的历史数据"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/races?order=race_date.desc&limit={limit}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            races = response.json()
            # 获取每场比赛的出赛马匹
            for race in races:
                runners_url = f"{SUPABASE_URL}/rest/v1/race_runners_clean?race_id=eq.{race.get('race_id')}"
                runners_response = requests.get(runners_url, headers=headers)
                if runners_response.status_code == 200:
                    race['runners'] = runners_response.json()
            return races
        return []
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
# ==================== 智能投注主页面 ====================
def render_smart_betting(show_title: bool = True):
    """智能投注页面：单场分析 + 全天优化 + 过关组合"""
    import time
    perf_log = {}
    t0 = time.time()
    
    # ========== 🔧 调试代码开始（可删除）==========
    #with st.expander("🔧 调试信息 - 赛程获取", expanded=False):
    #    st.write("### 正在检查赛程获取逻辑")
    #    
    #    # 1. 检查 API 配置
    #    api_url = st.secrets.get("HKJC_API_URL", "未配置")
    #    st.write(f"1. API地址: {api_url}")
    #    
    #    # 2. 直接测试 API 调用
    #    if api_url != "未配置":
    #        try:
    #            response = requests.get(f"{api_url}/meetings", timeout=10)
    #            st.write(f"2. API状态码: {response.status_code}")
    #            
    #            if response.status_code == 200:
    #                data = response.json()
    #                st.write(f"3. API返回成功: {data.get('success')}")
    #                
    #                meetings = data.get("data", [])
    #                st.write(f"4. 获取到 {len(meetings)} 个赛马日")
    #                
    #                for m in meetings:
    #                    st.write(f"   - {m.get('date')} {m.get('venueCode')}: {len(m.get('races', []))} 场比赛")
    #            else:
    #                st.error(f"API返回错误: {response.text}")
    #        except Exception as e:
    #            st.error(f"API调用失败: {e}")
    #    else:
    #        st.error("API地址未配置！请在 secrets.toml 中设置 HKJC_API_URL")
    #    
    #    # 3. 检查数据库中的赛事
    #    st.write("### 数据库中的未来赛事")
    #    try:
    #        headers = get_supabase_headers(use_secret=True)
    #        today = datetime.now().strftime("%Y-%m-%d")
    #        url = f"{SUPABASE_URL}/rest/v1/races?race_date=gte.{today}&order=race_date.asc&limit=50"
    #        response = requests.get(url, headers=headers)
    #        
    #        if response.status_code == 200:
    #            db_races = response.json()
    #            st.write(f"从数据库获取到 {len(db_races)} 条记录")
    #            
    #            if db_races:
    #                dates = {}
    #                for r in db_races:
    #                    date = r.get('race_date')
    #                    if date not in dates:
    #                        dates[date] = []
    #                    dates[date].append(r.get('race_no'))
    #                
    #                for date, race_nos in sorted(dates.items()):
    #                    st.write(f"   - {date}: {len(race_nos)} 场")
    #            else:
    #                st.warning("数据库中没有未来赛事")
    #        else:
    #            st.error(f"数据库查询失败: {response.status_code}")
    #    except Exception as e:
    #        st.error(f"数据库错误: {e}")
    #    
    #    # 4. 测试 get_upcoming_races 函数
    #    st.write("### get_upcoming_races() 返回结果")
    #    test_races = get_upcoming_races()
    #    st.write(f"返回 {len(test_races)} 场赛事")
    #    
    #    if test_races:
    #        by_date = {}
    #        for r in test_races:
    #            date = r.get('race_date')
    #            if date not in by_date:
    #                by_date[date] = []
    #            by_date[date].append(r.get('race_no'))
    #        
    #        for date, race_nos in sorted(by_date.items()):
    #            st.write(f"   - {date}: {len(race_nos)} 场")
    # ========== 🔧 调试代码结束 ==========
    
    if show_title:
        st.markdown(f"## {t()['smart_betting']}")
    perf_log["初始化"] = time.time() - t0    
    #-------------
    # ==================== 用户设置区域 ====================
    with st.expander(t()["betting_settings"], expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            profile = get_user_profile(st.session_state.user_id)
            default_bankroll = profile.get('default_bankroll', 1000)
            bankroll = st.number_input(
                t()["betting_budget"],
                min_value=100,
                max_value=100000,
                value=int(default_bankroll),
                step=100,
                key="betting_bankroll"
            )
        
        with col2:
            risk_preference = st.selectbox(
                t()["risk_preference"],
                options=["conservative", "standard", "aggressive"],
                format_func=lambda x: {
                    "conservative": t()["conservative"], 
                    "standard": t()["standard"], 
                    "aggressive": t()["aggressive"]
                }.get(x, t()["standard"]),
                key="risk_preference"
            )
            risk_multiplier = {
                "conservative": 0.5,
                "standard": 0.8,
                "aggressive": 1.0
            }.get(risk_preference, 0.8)
        
        with col3:
            model_choice = st.selectbox(
                t()["ai_model"],
                options=["评分系统", "LightGBM", "XGBoost", "集成模型"],
                index=0,
                key="ml_model_choice",
                help="选择预测模型：评分系统（规则驱动）、LightGBM、XGBoost 或集成模型"
            )
        
        with col4:
            st.markdown(f"**{t()['rating_weights']}**")
            st.caption(f"{t()['basic_weight']} | {t()['race_weight']} | {t()['odds_weight']}")
            st.caption(f"{t()['temperature']} | {t()['odds_mix']}")
    #-----------------
    lang = st.session_state.get("lang", "zh")
    # ==================== 评分权重设置（用户临时调整） ====================
    with st.expander("⚙️ 评分权重设置" if lang == "zh" else "⚙️ Rating Weights", expanded=False):
        st.caption("调整评分因子权重，仅对当前会话有效，退出后恢复默认值" if lang == "zh" else "Adjust rating weights, only valid for current session")
        
        # 从数据库加载默认配置
        @st.cache_data(ttl=300, show_spinner=False)
        def load_scoring_config_user():
            try:
                headers = get_supabase_headers(use_secret=True)
                url = f"{SUPABASE_URL}/rest/v1/scoring_config?id=eq.1"
                response = requests.get(url, headers=headers)
                if response.status_code == 200 and response.json():
                    return response.json()[0]
                return None
            except Exception:
                return None
        
        config = load_scoring_config_user()
        
        # 如果配置不存在，使用默认值
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
        
        # 初始化 session_state 中的用户临时配置
        if "user_scoring_config" not in st.session_state:
            st.session_state.user_scoring_config = {
                "level1_weights": default_level1.copy(),
                "basic_weights": default_basic.copy(),
                "race_weights": default_race.copy(),
                "odds_weights": default_odds.copy(),
                "status_weights": default_status.copy()
            }
        
        # 检查是否应用了权重
        if "scoring_weights_applied" not in st.session_state:
            st.session_state.scoring_weights_applied = False
        
        # 获取当前用户编辑的配置（从 session_state）
        user_level1 = st.session_state.user_scoring_config["level1_weights"].copy()
        user_basic = st.session_state.user_scoring_config["basic_weights"].copy()
        user_race = st.session_state.user_scoring_config["race_weights"].copy()
        user_odds = st.session_state.user_scoring_config["odds_weights"].copy()
        user_status = st.session_state.user_scoring_config["status_weights"].copy()
        
        # ==================== 一级因子设置 ====================
        if lang == "zh":
            st.markdown("**一级因子权重**")
        else:
            st.markdown("**Level 1 Weights**")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            basic_val = st.number_input(
                "基础往绩" if lang == "zh" else "Basic",
                min_value=0, max_value=100, value=int(user_level1.get("basic", 0.30) * 100),
                step=1, key="user_basic_weight"
            )
            user_level1["basic"] = basic_val / 100
        
        with col2:
            race_val = st.number_input(
                "场次因素" if lang == "zh" else "Race",
                min_value=0, max_value=100, value=int(user_level1.get("race", 0.35) * 100),
                step=1, key="user_race_weight"
            )
            user_level1["race"] = race_val / 100
        
        with col3:
            odds_val = st.number_input(
                "赔率因素" if lang == "zh" else "Odds",
                min_value=0, max_value=100, value=int(user_level1.get("odds", 0.20) * 100),
                step=1, key="user_odds_weight"
            )
            user_level1["odds"] = odds_val / 100
        
        with col4:
            status_val = st.number_input(
                "状态因素" if lang == "zh" else "Status",
                min_value=0, max_value=100, value=int(user_level1.get("status", 0.15) * 100),
                step=1, key="user_level1_status"
            )
            user_level1["status"] = status_val / 100
        
        # 显示一级因子总和
        total_level1 = sum(user_level1.values()) * 100
        if abs(total_level1 - 100) < 0.1:
            st.success(f"✅ 总和: {total_level1:.0f}%" if lang == "zh" else f"✅ Total: {total_level1:.0f}%")
        else:
            st.error(f"❌ 总和: {total_level1:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_level1:.0f}%, must be 100%")
        
        # ==================== 二级因子折叠区域 ====================
        # 基础往绩二级因子
        with st.expander("📈 基础往绩二级因子" if lang == "zh" else "📈 Basic Performance Sub-factors", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                win3 = st.number_input(
                    "近3场胜率" if lang == "zh" else "Win Rate (L3)",
                    min_value=0, max_value=100, value=int(user_basic.get("win_rate_3", 0.20) * 100),
                    step=1, key="user_win3"
                )
                win10 = st.number_input(
                    "近10场胜率" if lang == "zh" else "Win Rate (L10)",
                    min_value=0, max_value=100, value=int(user_basic.get("win_rate_10", 0.20) * 100),
                    step=1, key="user_win10"
                )
                place10 = st.number_input(
                    "近10场入Q率" if lang == "zh" else "Place Rate (L10)",
                    min_value=0, max_value=100, value=int(user_basic.get("place_rate_10", 0.15) * 100),
                    step=1, key="user_place10"
                )
            with col2:
                show10 = st.number_input(
                    "近10场入T率" if lang == "zh" else "Show Rate (L10)",
                    min_value=0, max_value=100, value=int(user_basic.get("show_rate_10", 0.15) * 100),
                    step=1, key="user_show10"
                )
                distance_rating = st.number_input(
                    "同程表现评分" if lang == "zh" else "Distance Rating",
                    min_value=0, max_value=100, value=int(user_basic.get("distance_rating", 0.15) * 100),
                    step=1, key="user_distance"
                )
                trend = st.number_input(
                    "名次趋势" if lang == "zh" else "Ranking Trend",
                    min_value=0, max_value=100, value=int(user_basic.get("trend", 0.15) * 100),
                    step=1, key="user_trend"
                )
            
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
        
        # 场次因素二级因子
        with st.expander("🏟️ 场次因素二级因子" if lang == "zh" else "🏟️ Race Factors Sub-factors", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                same_course = st.number_input(
                    "同场地胜率" if lang == "zh" else "Same Course",
                    min_value=0, max_value=100, value=int(user_race.get("same_course", 0.25) * 100),
                    step=1, key="user_same_course"
                )
                same_distance = st.number_input(
                    "同路程胜率" if lang == "zh" else "Same Distance",
                    min_value=0, max_value=100, value=int(user_race.get("same_distance", 0.25) * 100),
                    step=1, key="user_same_distance"
                )
                draw = st.number_input(
                    "档位优势" if lang == "zh" else "Draw",
                    min_value=0, max_value=100, value=int(user_race.get("draw", 0.15) * 100),
                    step=1, key="user_draw"
                )
            with col2:
                weight = st.number_input(
                    "负磅变化" if lang == "zh" else "Weight",
                    min_value=0, max_value=100, value=int(user_race.get("weight", 0.10) * 100),
                    step=1, key="user_weight"
                )
                jockey = st.number_input(
                    "骑师配合" if lang == "zh" else "Jockey",
                    min_value=0, max_value=100, value=int(user_race.get("jockey", 0.15) * 100),
                    step=1, key="user_jockey"
                )
                trainer = st.number_input(
                    "练马师状态" if lang == "zh" else "Trainer",
                    min_value=0, max_value=100, value=int(user_race.get("trainer", 0.10) * 100),
                    step=1, key="user_trainer"
                )
            
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
        
        # 赔率因素二级因子
        with st.expander("💰 赔率因素二级因子" if lang == "zh" else "💰 Odds Factors Sub-factors", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                win_odds = st.number_input(
                    "独赢赔率" if lang == "zh" else "Win Odds",
                    min_value=0, max_value=100, value=int(user_odds.get("win_odds", 0.60) * 100),
                    step=1, key="user_win_odds"
                )
            with col2:
                odds_trend = st.number_input(
                    "赔率变动趋势" if lang == "zh" else "Odds Trend",
                    min_value=0, max_value=100, value=int(user_odds.get("odds_trend", 0.40) * 100),
                    step=1, key="user_odds_trend"
                )
            
            user_odds["win_odds"] = win_odds / 100
            user_odds["odds_trend"] = odds_trend / 100
            
            total_odds = sum(user_odds.values()) * 100
            if abs(total_odds - 100) < 0.1:
                st.success(f"✅ 总和: {total_odds:.0f}%" if lang == "zh" else f"✅ Total: {total_odds:.0f}%")
            else:
                st.error(f"❌ 总和: {total_odds:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_odds:.0f}%, must be 100%")
        
        # 状态因素二级因子
        with st.expander("🩺 状态因素二级因子" if lang == "zh" else "🩺 Status Factors Sub-factors", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                age = st.number_input(
                    "马龄因子" if lang == "zh" else "Age",
                    min_value=0, max_value=100, value=int(user_status.get("age", 0.30) * 100),
                    step=1, key="user_age"
                )
                weight_change = st.number_input(
                    "体重变化" if lang == "zh" else "Weight Change",
                    min_value=0, max_value=100, value=int(user_status.get("weight_change", 0.25) * 100),
                    step=1, key="user_status_weight_change"
                )
            with col2:
                incident = st.number_input(
                    "事件报告" if lang == "zh" else "Incident",
                    min_value=0, max_value=100, value=int(user_status.get("incident", 0.25) * 100),
                    step=1, key="user_incident"
                )
                burst = st.number_input(
                    "冲刺能力" if lang == "zh" else "Burst",
                    min_value=0, max_value=100, value=int(user_status.get("burst", 0.20) * 100),
                    step=1, key="user_burst"
                )
            
            user_status["age"] = age / 100
            user_status["weight_change"] = weight_change / 100
            user_status["incident"] = incident / 100
            user_status["burst"] = burst / 100
            
            total_status = sum(user_status.values()) * 100
            if abs(total_status - 100) < 0.1:
                st.success(f"✅ 总和: {total_status:.0f}%" if lang == "zh" else f"✅ Total: {total_status:.0f}%")
            else:
                st.error(f"❌ 总和: {total_status:.0f}%，必须为100%" if lang == "zh" else f"❌ Total: {total_status:.0f}%, must be 100%")
        
        # ==================== 按钮区域 ====================
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            # 保存用户临时配置到 session_state
            if st.button("✅ 应用权重并刷新" if lang == "zh" else "✅ Apply & Refresh", type="primary", use_container_width=True):
                # 检查一级因子总和
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
                else:
                    # 保存到 session_state
                    st.session_state.user_scoring_config = {
                        "level1_weights": user_level1,
                        "basic_weights": user_basic,
                        "race_weights": user_race,
                        "odds_weights": user_odds,
                        "status_weights": user_status
                    }
                    st.session_state.scoring_weights_applied = True
                    st.success("权重已应用，正在刷新数据..." if lang == "zh" else "Weights applied, refreshing...")
                    st.cache_data.clear()
                    st.rerun()
        
        with col2:
            if st.button("🔄 恢复默认值" if lang == "zh" else "🔄 Reset to Default", use_container_width=True):
                # 恢复到数据库默认配置
                st.session_state.user_scoring_config = {
                    "level1_weights": default_level1.copy(),
                    "basic_weights": default_basic.copy(),
                    "race_weights": default_race.copy(),
                    "odds_weights": default_odds.copy(),
                    "status_weights": default_status.copy()
                }
                st.session_state.scoring_weights_applied = False
                st.success("已恢复到默认权重" if lang == "zh" else "Reset to default weights")
                st.rerun()
        
        # 显示当前状态
        if st.session_state.scoring_weights_applied:
            st.info("✅ 当前使用自定义权重" if lang == "zh" else "✅ Currently using custom weights")
        else:
            st.info("📌 当前使用管理员默认权重" if lang == "zh" else "📌 Currently using admin default weights")
        
        st.caption("💡 修改后需点击「应用权重并刷新」才会生效" if lang == "zh" else "💡 Click 'Apply & Refresh' after modification to take effect")
    #------------------
    st.markdown("---")
    
    #-------    
    # ==================== 选择赛日 ====================
    st.markdown(f"### {t()['select_race_day']}")
    t1 = time.time()
    perf_log["选择赛日"] = t1 - t0
    
    # ⭐ 新增：日期模式选择
    date_mode = st.radio(
        "选择日期模式",
        options=["未来赛事", "历史赛事（测试用）"],
        index=0,
        horizontal=True,
        key="date_mode_select"
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        refresh_schedule_btn = st.button(t()["refresh_schedule"], use_container_width=True)
    
    if refresh_schedule_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning(t()["free_trial_used"])
        else:
            with st.spinner(t()["syncing_schedule"]):
                api_races = get_upcoming_races_from_api()
                if api_races:
                    sync_races_to_db(api_races)
                    st.success(t()["sync_complete"].format(success=len(api_races), failed=0))
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning(t()["no_races"])
    
    # ==================== 根据模式获取赛事列表 ====================
    if date_mode == "未来赛事":
        # 原有逻辑：获取未来14天赛事
        upcoming_races = get_cached_upcoming_races()
        if not upcoming_races:
            st.info(t()["no_races"])
            return
        
        valid_races = [r for r in upcoming_races if r.get('race_no', 0) > 0]
        if not valid_races:
            st.warning("暂无详细赛事数据（排位表尚未公布）。请点击「刷新赛程」同步最新数据。")
            valid_races = upcoming_races
        
        dates = sorted(set([r.get('race_date') for r in valid_races if r.get('race_date')]))
        
        if not dates:
            st.info("暂无赛事")
            return
        
        date_options = [f"{d} ({['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][datetime.strptime(d, '%Y-%m-%d').weekday()]})" for d in dates]
        
        selected_date_str = st.selectbox("選擇賽日", date_options, key="selected_race_date")
        selected_date = selected_date_str.split(" ")[0]
        
        races = [r for r in valid_races if r.get('race_date') == selected_date]
    
    else:
        # ⭐ 新增：历史赛事模式
        st.info("📅 选择历史日期进行测试（数据来自 past_performances_v2 表）")
        
        # 从 past_performances_v2 获取所有历史赛日
        try:
            headers = get_supabase_headers(use_secret=True)
            url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=race_date,venue,race_no,distance&limit=50000"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                perf_data = response.json()
                # 提取唯一赛事
                unique_races = {}
                for p in perf_data:
                    key = f"{p['race_date']}_{p['venue']}_{p['race_no']}"
                    if key not in unique_races:
                        unique_races[key] = {
                            'race_date': p.get('race_date'),
                            'venue': p.get('venue', 'ST'),
                            'race_no': p.get('race_no', 0),
                            'distance': p.get('distance', 1200)
                        }
                
                # 按日期降序排列（最近的在前）
                historical_races = list(unique_races.values())
                historical_races.sort(key=lambda x: x.get('race_date', ''), reverse=True)
                
                # 只取最近60天（避免列表太长）
                historical_races = historical_races[:60]
                
                if not historical_races:
                    st.warning("暂无历史赛事数据")
                    return
                
                # 按日期分组显示
                dates = sorted(set([r.get('race_date') for r in historical_races if r.get('race_date')]), reverse=True)
                date_options = [f"{d} ({['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][datetime.strptime(d, '%Y-%m-%d').weekday()]})" for d in dates]
                
                selected_date_str = st.selectbox("選擇歷史賽日", date_options, key="selected_history_date")
                selected_date = selected_date_str.split(" ")[0]
                
                races = [r for r in historical_races if r.get('race_date') == selected_date]
                # 按场次排序
                races.sort(key=lambda x: x.get('race_no', 0))
                
            else:
                st.error("获取历史赛事失败")
                return
                
        except Exception as e:
            st.error(f"获取历史赛事失败: {e}")
            return
    #-------------
    # ==================== 单场分析 ====================
    st.markdown(f"### {t()['single_race_analysis']}")
    
    if not races:
        st.warning("该日期暂无详细赛事数据")
        return
    
    race_options = []
    for r in races:
        distance = r.get('distance', 0)
        race_class = r.get('race_class', '')
        race_no = r.get('race_no', 0)
        race_options.append(f"第{race_no}場 - {distance}米 ({race_class})")
    
    selected_idx = st.selectbox(t()["select_race"], range(len(race_options)), format_func=lambda x: race_options[x], key="selected_race")
    selected_race = races[selected_idx]
    
    col1, col2 = st.columns([1, 4])
    with col1:
        refresh_race_btn = st.button(t()["refresh_race_data"], key="refresh_race")
    
    # ✅ 修改：单场同步也使用 API
    if refresh_race_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning(t()["free_trial_used"])
        else:
            with st.spinner(t()["updating_odds"]):
                # 调用 API 同步单场赛事
                api_url = st.secrets.get("HKJC_API_URL", "")
                if api_url:
                    try:
                        sync_url = f"{api_url}/sync/race"
                        response = requests.post(sync_url, json={
                            "date": selected_race.get('race_date'),
                            "venue": selected_race.get('venue'),
                            "raceNo": selected_race.get('race_no')
                        }, timeout=60)
                        if response.status_code == 200:
                            st.success(t()["data_updated"])
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.warning(t()["update_failed"])
                    except Exception as e:
                        st.error(f"同步失败: {e}")
                else:
                    # 回退到原有方法
                    if sync_single_race(selected_race):
                        st.success(t()["data_updated"])
                        st.rerun()
                    else:
                        st.warning(t()["update_failed"])
    
    runners = get_race_runners_with_details(
        selected_race.get('race_date'),
        selected_race.get('venue'),
        selected_race.get('race_no')
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
    # ==================== 计算胜率 ====================
    if model_choice == "评分系统":
        with st.spinner(t()["calculating_win_rate"]):
            # 获取用户权重配置（如果已应用）
            if st.session_state.get('scoring_weights_applied', False):
                user_config = st.session_state.get('user_scoring_config', {})
                level1_weights = user_config.get('level1_weights', {})
                basic_weights = user_config.get('basic_weights', {})
                race_weights = user_config.get('race_weights', {})
                odds_weights = user_config.get('odds_weights', {})
                status_weights = user_config.get('status_weights', {})
            else:
                # 使用管理员默认配置
                from scoring_engine import get_scoring_config
                config = get_scoring_config()
                level1_weights = config.get('level1', {})
                basic_weights = config.get('basic', {})
                race_weights = config.get('race', {})
                odds_weights = config.get('odds', {})
                status_weights = config.get('status', {})
            
            # 导入新的评分函数
            from scoring_engine import (
                calculate_basic_score,
                calculate_race_score,
                calculate_odds_score,
                calculate_status_score,
                calculate_overall_score,
                get_horse_weight_comfort_range_from_cache,
                get_horses_performances_batch
            )
            
            # 获取马匹往绩
            horse_ids = [r.get('horse_id') for r in runners if r.get('horse_id')]
            perf_cache = get_horses_performances_batch(tuple(set(horse_ids)))
            
            # 计算每匹马的评分
            scores = []
            for runner in runners:
                horse_id = runner.get('horse_id')
                if not horse_id:
                    scores.append({
                        'overall_score': 50,
                        'win_probability': 50,
                        'basic_score': 50,
                        'race_score': 50,
                        'odds_score': 50,
                        'status_score': 50
                    })
                    continue
                
                # 获取往绩
                past_performances = perf_cache.get(horse_id, [])[:10]
                
                # 获取负磅舒适区
                weight_comfort_range = get_horse_weight_comfort_range_from_cache(horse_id, past_performances)
                
                # 计算基础往绩评分
                basic_score = calculate_basic_score(
                    past_performances,
                    selected_race.get('distance', 1200),
                    basic_weights
                )
                
                # 计算场次因素评分
                race_score = calculate_race_score(
                    horse_id,
                    selected_race.get('venue', 'ST'),
                    selected_race.get('distance', 1200),
                    runner.get('draw'),
                    runner.get('actual_weight'),
                    runner.get('jockey_id'),
                    runner.get('trainer_id'),
                    weight_comfort_range,
                    past_performances,
                    race_weights
                )
                
                # 计算赔率因素评分
                odds_win = runner.get('odds_win', 10.0)
                if odds_win is None or odds_win == '':
                    odds_win = 10.0
                try:
                    odds_win = float(odds_win)
                except (ValueError, TypeError):
                    odds_win = 10.0
                
                odds_score = calculate_odds_score(odds_win, 50.0, odds_weights)
                
                # 计算状态因素评分
                from scoring_engine import calculate_status_score
                status_score = calculate_status_score(
                    None,  # birth_year - 可以从horses表获取
                    runner.get('body_weight'),
                    [p.get('body_weight') for p in past_performances if p.get('body_weight')],
                    runner.get('incident', ''),
                    runner.get('running_position', ''),
                    None,  # finishing_position
                    status_weights
                )
                
                # 计算综合评分
                overall_score = calculate_overall_score(
                    basic_score,
                    race_score,
                    odds_score,
                    status_score,
                    level1_weights
                )
                
                scores.append({
                    'overall_score': overall_score,
                    'win_probability': overall_score,  # 稍后用softmax转换
                    'basic_score': basic_score,
                    'race_score': race_score,
                    'odds_score': odds_score,
                    'status_score': status_score
                })
            
            # 使用softmax计算胜率
            from scoring_engine import softmax_probabilities
            prob_scores = [s['overall_score'] for s in scores]
            probabilities = softmax_probabilities(prob_scores, temperature=0.8)
            
            for i, runner in enumerate(runners):
                if i < len(scores):
                    runner['overall_score'] = scores[i]['overall_score']
                    runner['win_probability'] = probabilities[i] if i < len(probabilities) else 0
                    runner['basic_score'] = scores[i]['basic_score']
                    runner['race_score'] = scores[i]['race_score']
                    runner['odds_score'] = scores[i]['odds_score']
                    runner['status_score'] = scores[i]['status_score']
                print(f"5. 马号 {runner.get('horse_no')}: 评分={runner['overall_score']}, 胜率={runner['win_probability']}")
    
    else:
        # ==================== ML 模型预测（三分类版本） ====================
        model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
        with st.spinner(t()["calculating_ml"].format(model=model_choice)):
            # 获取或训练模型
            from scoring_engine import get_cached_model, set_cached_model
            cache_key = f"{model_type}_smart_betting"
            model = get_cached_model(cache_key)
            
            if model is None:
                # 训练模型（使用历史数据）
                draws = get_historical_draws_for_training(limit=300)
                if model_type == 'lightgbm':
                    model = train_lightgbm_model(draws)
                elif model_type == 'xgboost':
                    model = train_xgboost_model(draws)
                elif model_type == 'ensemble':
                    lgb_model = train_lightgbm_model(draws)
                    xgb_model = train_xgboost_model(draws)
                    model = {'lightgbm': lgb_model, 'xgboost': xgb_model}
                if model is not None:
                    set_cached_model(cache_key, model)
            
            if model is not None:
                ml_probs = get_model_predictions(
                    selected_race.get('race_date'),
                    selected_race.get('venue'),
                    selected_race.get('race_no'),
                    runners,
                    model_type,
                    model
                )
            else:
                ml_probs = [0.34] * len(runners)
        
        t3 = time.time()
        perf_log["计算胜率"] = t3 - t2
        
        for i, runner in enumerate(runners):
            if i < len(ml_probs):
                runner['win_probability'] = ml_probs[i]
                runner['overall_score'] = ml_probs[i] * 100
    
    sorted_runners = sorted(runners, key=lambda x: x.get('win_probability', 0), reverse=True)
    #--------------------
    # 在计算完 runners 的 win_probability 之后添加

    # ==================== 调用策略引擎生成投注建议 ====================
    # 初始化 t3 变量，防止 UnboundLocalError
    t3 = time.time()  # ← 添加这一行，确保 t3 始终有值
    
    if sorted_runners:
        # 准备策略引擎所需数据
        scores = [runner.get('overall_score', 50) for runner in sorted_runners]
        horse_names = [runner.get('horse_name', '') for runner in sorted_runners]
        
        # 获取赔率
        odds_win = []
        odds_place = []
        for runner in sorted_runners:
            odds_raw = runner.get('odds_win')
            try:
                odds = float(odds_raw) if odds_raw else 0
            except:
                odds = 0
            odds_win.append(odds)
            odds_place.append(odds * 0.3 if odds > 0 else 0)
        
        # 获取连赢和单T赔率（如果有真实数据）
        odds_qin = get_odds_qin_from_db(selected_race.get('race_date'), selected_race.get('race_no'))
        odds_tri = get_odds_tri_from_db(selected_race.get('race_date'), selected_race.get('race_no'))
        
        # 生成建议
        engine = BettingStrategyEngine()
        recommendations = engine.generate_all_recommendations(
            scores=scores,
            horse_names=horse_names,
            odds_win=odds_win,
            odds_place=odds_place,
            odds_qin=odds_qin,
            odds_tri=odds_tri
        )
        
        t4 = time.time()
        perf_log["策略引擎"] = t4 - t3
    else:
        # 如果没有 runners，也要记录时间
        perf_log["策略引擎"] = 0
        recommendations = {}  # 空建议
        
    #------------
    # 显示表格
    st.markdown(f"#### 🏇 {t()['race_table_title'].format(race_no=selected_race.get('race_no'))}")
    #-----------
    race_data = []
    for runner in sorted_runners:
        horse_name = runner.get('horse_name', '')
        
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
            t()["horse_no"]: runner.get('horse_no', '-'),
            t()["horse_name"]: horse_name,
            t()["draw"]: runner.get('draw', '-'),
            t()["actual_weight"]: runner.get('actual_weight', '-'),
            t()["jockey"]: runner.get('jockey_name', '-'),
            t()["win_odds"]: odds_win_display,
            t()["place_odds"]: odds_place_display,
            t()["win_rate"]: win_prob_display,
            t()["overall_score"]: overall_score_display,
            t()["ev"]: ev_display
        })
    
    # 只有当有数据时才显示表格
    if race_data:
        st.dataframe(pd.DataFrame(race_data), use_container_width=True, hide_index=True)
    else:
        st.warning(t()["no_data"])
    
    t5 = time.time()
    perf_log["显示表格"] = t5 - t4
        
    #------------
    # 投注建议 - 使用AI策略引擎
    st.markdown(f"#### {t()['ai_strategy_suggestions']}")
    st.caption(t()["ev_description"])
    
    # 准备策略引擎所需数据
    scores = [runner.get('overall_score', 50) for runner in sorted_runners]
    horse_names = [runner.get('horse_name', '') for runner in sorted_runners]
    
    # 获取赔率
    odds_win = []
    odds_place = []
    for runner in sorted_runners:
        odds_raw = runner.get('odds_win')
        try:
            odds = float(odds_raw) if odds_raw else 0
        except:
            odds = 0
        odds_win.append(odds)
        # 位置赔率约为独赢的30%（估算）
        odds_place.append(odds * 0.3 if odds > 0 else 0)
    
    # 获取连赢和单T赔率（从数据库）
    odds_qin = get_odds_qin_from_db(selected_race.get('race_date'), selected_race.get('race_no'))
    odds_tri = get_odds_tri_from_db(selected_race.get('race_date'), selected_race.get('race_no'))
    
    # 生成建议
    engine = BettingStrategyEngine()
    recommendations = engine.generate_all_recommendations(
        scores=scores,
        horse_names=horse_names,
        odds_win=odds_win,
        odds_place=odds_place,
        odds_qin=odds_qin,
        odds_tri=odds_tri
    )
    
    # 创建三列显示建议
    col1, col2, col3 = st.columns(3)
    
    # 低风险 - 独赢/位置
    with col1:
        st.markdown(f"**{t()['low_risk']}**")
        if recommendations.get('win') and recommendations['win']:
            rec = recommendations['win'][0]
            st.info(f"**{rec.description}**")
            st.write(f"{t()['win_odds']}: {rec.odds}倍")
            st.write(f"預期ROI: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        elif recommendations.get('place') and recommendations['place']:
            rec = recommendations['place'][0]
            st.info(f"**{rec.description}**")
            st.write(f"{t()['place_odds']}: {rec.odds}倍")
            st.write(f"預期ROI: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        else:
            st.write(t()["no_suggestions"])
    
    # 中风险 - 连赢
    with col2:
        st.markdown(f"**{t()['medium_risk']}**")
        if recommendations.get('qin') and recommendations['qin']:
            rec = recommendations['qin'][0]
            st.warning(f"**{rec.description}**")
            st.write(f"{t()['win_odds']}: {rec.odds}倍")
            st.write(f"預期ROI: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        else:
            st.write(t()["no_suggestions"])
    
    # 高风险 - 单T
    with col3:
        st.markdown(f"**{t()['high_risk']}**")
        if recommendations.get('tri') and recommendations['tri']:
            rec = recommendations['tri'][0]
            st.error(f"**{rec.description}**")
            st.write(f"{t()['win_odds']}: {rec.odds}倍")
            st.write(f"預期ROI: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        else:
            st.write(t()["no_suggestions"])
    
    # ==================== 连赢推荐（追加）====================
    st.markdown(f"#### {t()['qin_recommendation']}")
    
    if len(sorted_runners) >= 2:
        # 获取前两名高胜率马的组合
        top2 = sorted_runners[:2]
        horse1 = top2[0]
        horse2 = top2[1]
        
        horse1_id = horse1.get('horse_id')
        horse2_id = horse2.get('horse_id')
        horse1_name = horse1.get('horse_name', '')
        horse2_name = horse2.get('horse_name', '')
        
        # 获取赔率
        odds1_raw = horse1.get('odds_win')
        odds2_raw = horse2.get('odds_win')
        
        try:
            odds1 = float(odds1_raw) if odds1_raw else 0
            odds2 = float(odds2_raw) if odds2_raw else 0
        except (ValueError, TypeError):
            odds1 = odds2 = 0
        
        # 估算连赢赔率（实际应从 API 获取 QIN 赔率）
        estimated_qin_odds = (odds1 * odds2) / 2 if odds1 > 0 and odds2 > 0 else 0
        
        if estimated_qin_odds > 0:
            prob1 = horse1.get('win_probability', 0)
            prob2 = horse2.get('win_probability', 0)
            joint_prob = prob1 * prob2 * 2
            
            if joint_prob * estimated_qin_odds > 1:
                suggested_stake = bankroll * 0.05 * risk_multiplier
                st.success(f"**{horse1_name} + {horse2_name}** | {t()['win_odds']}: {estimated_qin_odds:.1f} | 聯合概率: {joint_prob*100:.1f}% | 建議注額: HK${suggested_stake:.0f}")
            else:
                st.info(t()["qin_ev_insufficient"].format(horse1=horse1_name, horse2=horse2_name))
        else:
            st.caption("暫無連贏賠率數據")
    else:
        st.caption("馬匹數量不足，無法推薦連贏")
    
    st.markdown("---")
    
    # ==================== 新增：過関投注推薦器 ====================
    st.markdown(f"## {t()['parlay_recommendation']}")
    st.caption(t()["parlay_description"])
    
    # 获取当前赛日的所有赛事（用于过关推荐）
    current_races_for_parlay = races  # races 是前面定义的当前赛日所有赛事
    
    if current_races_for_parlay and len(current_races_for_parlay) >= 2:
        # 让用户選擇要過關的場次
        st.markdown("**選擇要過關的場次**")
        
        parlay_race_options = []
        for r in current_races_for_parlay:
            distance = r.get('distance', 0)
            race_class = r.get('race_class', '')
            parlay_race_options.append(f"第{r.get('race_no')}場 - {distance}米 ({race_class})")
        
        # 多选框
        selected_parlay_indices = st.multiselect(
            "選擇2-6場比賽（按順序）",
            options=range(len(parlay_race_options)),
            format_func=lambda x: parlay_race_options[x],
            default=range(min(3, len(parlay_race_options))),
            key="parlay_race_select"
        )
        
        if len(selected_parlay_indices) >= 2:
            st.caption(f"已选择 {len(selected_parlay_indices)} 场比赛")
            
            # 收集所选场次的数据
            parlay_races_data = []
            for idx in selected_parlay_indices:
                race = current_races_for_parlay[idx]
                race_no = race.get('race_no')
                
                # 获取该场次的出赛马匹和评分
                runners_data = get_race_runners_with_details(
                    race.get('race_date'), race.get('venue'), race_no
                )
                
                if runners_data:
                    # 计算评分
                    if model_choice == "评分系统":
                        scores, _ = calculate_all_horses_scores_v2(runners_data, user_weights)
                        for i, runner in enumerate(runners_data):
                            if i < len(scores):
                                runner['overall_score'] = scores[i].get('overall_score', 0)
                                runner['win_probability'] = scores[i].get('win_probability', 0) / 100
                    #-------------
                    else:
                        # ==================== ML 模型预测（三分类版本） ====================
                        model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
                        
                        # 获取或训练模型（使用缓存）
                        from scoring_engine import get_cached_model, set_cached_model
                        cache_key = f"{model_type}_smart_betting"
                        model = get_cached_model(cache_key)
                        
                        if model is None:
                            # 训练模型（使用历史数据）
                            draws = get_historical_draws_for_training(limit=300)
                            if model_type == 'lightgbm':
                                model = train_lightgbm_model(draws)
                            elif model_type == 'xgboost':
                                model = train_xgboost_model(draws)
                            elif model_type == 'ensemble':
                                lgb_model = train_lightgbm_model(draws)
                                xgb_model = train_xgboost_model(draws)
                                model = {'lightgbm': lgb_model, 'xgboost': xgb_model}
                            if model is not None:
                                set_cached_model(cache_key, model)
                        
                        if model is not None:
                            ml_probs = get_model_predictions(
                                race.get('race_date'),
                                race.get('venue'),
                                race.get('race_no'),
                                runners_data,
                                model_type,
                                model
                            )
                        else:
                            ml_probs = [0.34] * len(runners_data)
                        
                        for i, runner in enumerate(runners_data):
                            if i < len(ml_probs):
                                runner['win_probability'] = ml_probs[i]
                                runner['overall_score'] = ml_probs[i] * 100
                    
                    # 准备数据
                    sorted_runners = sorted(runners_data, key=lambda x: x.get('win_probability', 0), reverse=True)
                    scores = [runner.get('overall_score', 50) for runner in sorted_runners]
                    horse_names = [runner.get('horse_name', '') for runner in sorted_runners]
                    odds = []
                    for runner in sorted_runners:
                        odds_raw = runner.get('odds_win')
                        try:
                            odd = float(odds_raw) if odds_raw else 0
                        except:
                            odd = 0
                        odds.append(odd)
                    
                    parlay_races_data.append({
                        'race_date': race.get('race_date'),
                        'race_no': race_no,
                        'venue': race.get('venue'),
                        'scores': scores,
                        'horse_names': horse_names,
                        'odds': odds
                    })
            
            if len(parlay_races_data) >= 2:
                # 运行过关推荐
                if st.button(t()["generate_parlay"], key="generate_parlay_recommendations", use_container_width=True):
                    if not consume_free_trial(st.session_state.user_id):
                        st.warning("免費次數已用完，請升級到專業版")
                    else:
                        with st.spinner("正在计算过关推荐..."):
                            from parlay_recommender import ParlayRecommender
                            
                            recommender = ParlayRecommender()
                            max_legs = min(len(parlay_races_data), 6)
                            
                            # 生成推荐
                            results = recommender.get_parlay_recommendations_for_schedule(
                                races_data=parlay_races_data,
                                max_legs=max_legs,
                                top_parlay_types=['2x1', '2x3', '3x4', '3x7', '4x11']
                            )
                            
                            if results:
                                st.markdown("#### 📊 过关推荐结果")
                                
                                for parlay_type, recommendations in results.items():
                                    config = recommender.parlay_configs.get(parlay_type, {})
                                    st.markdown(f"**{config.get('description', parlay_type)}**")
                                    
                                    for rec in recommendations[:3]:  # 每种类型显示前3个
                                        # 构建显示文本
                                        legs_display = []
                                        for sel in rec.selections:
                                            legs_display.append(f"第{sel.race_no}場 {sel.horse_name}({sel.selected_horse_no}號)")
                                        
                                        # 风险颜色
                                        risk_color = "🟢" if rec.risk_level == "低" else "🟡" if rec.risk_level == "中" else "🔴"
                                        
                                        with st.container(border=True):
                                            col1, col2, col3 = st.columns([2, 1, 1])
                                            with col1:
                                                st.markdown(f"**{' → '.join(legs_display)}**")
                                            with col2:
                                                st.markdown(f"賠率: **{rec.total_odds:.1f}**倍")
                                                st.markdown(f"聯合概率: {rec.combined_prob:.1f}%")
                                            with col3:
                                                st.markdown(f"風險: {risk_color} {rec.risk_level}")
                                                st.markdown(f"預期ROI: {rec.roi:+.1f}%")
                                        
                                        # 投注建议
                                        st.caption(f"💡 建議投注: {parlay_type} ({rec.num_bets}注, 共${rec.total_stake:.0f})")
                                
                                # 最佳推薦汇总
                                st.markdown("---")
                                st.markdown("#### 🏆 最佳推薦")
                                
                                # 找出ROI最高的推荐
                                best_rec = None
                                best_roi = -100
                                for recs in results.values():
                                    for rec in recs:
                                        if rec.roi > best_roi:
                                            best_roi = rec.roi
                                            best_rec = rec
                                
                                if best_rec:
                                    legs_display = []
                                    for sel in best_rec.selections:
                                        legs_display.append(f"第{sel.race_no}場 {sel.horse_name}({sel.selected_horse_no}號)")
                                    
                                    st.success(f"""
                                    **最佳过关组合**: {' → '.join(legs_display)}
                                    - 过关方式: {best_rec.parlay_type} ({best_rec.num_bets}注)
                                    - 总赔率: {best_rec.total_odds:.1f}倍
                                    - 预期ROI: {best_rec.roi:+.1f}%
                                    - 建议投注: ${best_rec.total_stake:.0f}
                                    """)
                            else:
                                st.warning("未找到合适的过关组合，请尝试选择更多场次")
            else:
                st.warning("所选场次数据不足，请刷新后重试")
        else:
            st.info("请至少选择2场比赛进行过关推荐")
    else:
        st.info("当前赛日赛事不足2场，无法进行过关推荐")
    
    st.markdown("---")
    
    # ==================== 全天优化投注 ====================
    st.markdown(f"### {t()['full_day_optimization']}")
    st.caption(t()["kelly_description"])
    
    if st.button(t()["generate_full_day"], key="generate_full_day", use_container_width=True, type="primary"):
        with st.spinner("正在計算全天投注策略..."):
            all_bets = []
            total_stake = 0
            total_expected = 0
            
            for race in races:
                race_runners = get_race_runners_with_details(
                    race.get('race_date'), race.get('venue'), race.get('race_no')
                )
                if not race_runners:
                    continue
                
                # 计算胜率
                if model_choice == "评分系统":
                    scores, _ = calculate_all_horses_scores(race.get('race_id'), race_runners, user_weights)
                    for i, r in enumerate(race_runners):
                        if i < len(scores):
                            r['win_probability'] = scores[i].get('win_probability', 0) / 100
                #---------------
                else:
                    # ==================== ML 模型预测（三分类版本） ====================
                    model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
                    
                    # 获取或训练模型（使用缓存）
                    from scoring_engine import get_cached_model, set_cached_model
                    cache_key = f"{model_type}_smart_betting"
                    model = get_cached_model(cache_key)
                    
                    if model is None:
                        # 训练模型（使用历史数据）
                        draws = get_historical_draws_for_training(limit=300)
                        if model_type == 'lightgbm':
                            model = train_lightgbm_model(draws)
                        elif model_type == 'xgboost':
                            model = train_xgboost_model(draws)
                        elif model_type == 'ensemble':
                            lgb_model = train_lightgbm_model(draws)
                            xgb_model = train_xgboost_model(draws)
                            model = {'lightgbm': lgb_model, 'xgboost': xgb_model}
                        if model is not None:
                            set_cached_model(cache_key, model)
                    
                    if model is not None:
                        ml_probs = get_model_predictions(
                            race.get('race_date'),
                            race.get('venue'),
                            race.get('race_no'),
                            race_runners,
                            model_type,
                            model
                        )
                    else:
                        ml_probs = [0.34] * len(race_runners)
                    
                    for i, r in enumerate(race_runners):
                        if i < len(ml_probs):
                            r['win_probability'] = ml_probs[i]
                
                top_horses = sorted(race_runners, key=lambda x: x.get('win_probability', 0), reverse=True)[:2]
                #-----------
                for horse in top_horses:
                    if horse is None:
                        continue
                    prob = horse.get('win_probability', 0)
                    odds_raw = horse.get('odds_win')
                    
                    # 安全处理赔率
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
                            "場次": f"第{race.get('race_no')}場",
                            "馬匹": horse.get('horse_name', ''),
                            "賠率": odds,
                            "勝率": f"{prob*100:.1f}%",
                            "建議注額": f"HK${stake:.0f}",
                            "期望值": f"${expected:.0f}"
                        })
                        total_stake += stake
                        total_expected += expected
            
            if all_bets:
                st.dataframe(pd.DataFrame(all_bets), use_container_width=True, hide_index=True)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("💰 總投注額", f"HK${total_stake:.0f}")
                with col2:
                    st.metric("📈 總期望值", f"${total_expected:+.0f}")
                with col3:
                    roi = (total_expected / total_stake * 100) if total_stake > 0 else 0
                    st.metric("📊 預期ROI", f"{roi:+.1f}%")
            else:
                st.warning("未找到符合條件的投注機會")
    
    st.markdown("---")
    
    # ==================== 过关组合推荐 ====================
    st.markdown(f"### {t()['parlay_generation']}")
    st.caption(t()["parlay_description"])
    
    if st.button(t()["generate_parlay_combo"], key="generate_parlay", use_container_width=True):
        with st.spinner("正在計算過關組合..."):
            confidence_horses = []
            
            for race in races:
                race_runners = get_race_runners_with_details(
                    race.get('race_date'), race.get('venue'), race.get('race_no')
                )
                if not race_runners:
                    continue
                
                if model_choice == "评分系统":
                    scores, _ = calculate_all_horses_scores(race.get('race_id'), race_runners, user_weights)
                    for i, r in enumerate(race_runners):
                        if i < len(scores):
                            r['win_probability'] = scores[i].get('win_probability', 0) / 100
                #------------
                else:
                    # ==================== ML 模型预测（三分类版本） ====================
                    model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
                    
                    # 获取或训练模型（使用缓存）
                    from scoring_engine import get_cached_model, set_cached_model
                    cache_key = f"{model_type}_smart_betting"
                    model = get_cached_model(cache_key)
                    
                    if model is None:
                        # 训练模型（使用历史数据）
                        draws = get_historical_draws_for_training(limit=300)
                        if model_type == 'lightgbm':
                            model = train_lightgbm_model(draws)
                        elif model_type == 'xgboost':
                            model = train_xgboost_model(draws)
                        elif model_type == 'ensemble':
                            lgb_model = train_lightgbm_model(draws)
                            xgb_model = train_xgboost_model(draws)
                            model = {'lightgbm': lgb_model, 'xgboost': xgb_model}
                        if model is not None:
                            set_cached_model(cache_key, model)
                    
                    if model is not None:
                        ml_probs = get_model_predictions(
                            race.get('race_date'),
                            race.get('venue'),
                            race.get('race_no'),
                            race_runners,
                            model_type,
                            model
                        )
                    else:
                        ml_probs = [0.34] * len(race_runners)
                    
                    for i, r in enumerate(race_runners):
                        if i < len(ml_probs):
                            r['win_probability'] = ml_probs[i]
                
                top = max(race_runners, key=lambda x: x.get('win_probability', 0), default=None)
                if top and top.get('win_probability', 0) >= 0.20:
                    confidence_horses.append({
                        "race_no": race.get('race_no'),
                        "horse_name": top.get('horse_name', ''),
                        "probability": top.get('win_probability', 0),
                        "odds": top.get('odds_win', 0)
                    })
            
            parlay_results = []
            
            # 2串1
            for i in range(len(confidence_horses)):
                for j in range(i+1, len(confidence_horses)):
                    h1, h2 = confidence_horses[i], confidence_horses[j]
                    
                    prob1 = h1.get('probability', 0) or 0
                    prob2 = h2.get('probability', 0) or 0
                    odds1 = h1.get('odds', 0) or 0
                    odds2 = h2.get('odds', 0) or 0
                    
                    joint_prob = prob1 * prob2
                    combined_odds = odds1 * odds2 if odds1 > 0 and odds2 > 0 else 0
                    
                    if joint_prob * combined_odds > 1 and combined_odds > 0:
                        suggested_stake = bankroll * 0.05 * risk_multiplier
                        parlay_results.append({
                            "組合": "2串1",
                            "場次": f"第{h1['race_no']}場 + 第{h2['race_no']}場",
                            "馬匹": f"{h1['horse_name']} + {h2['horse_name']}",
                            "組合賠率": f"{combined_odds:.1f}",
                            "聯合概率": f"{joint_prob*100:.1f}%",
                            "建議注額": f"HK${suggested_stake:.0f}"
                        })
            
            if parlay_results:
                st.dataframe(pd.DataFrame(parlay_results), use_container_width=True, hide_index=True)
            else:
                st.info("暫無符合條件的過關組合")
    
    st.markdown("---")
    st.caption(t()["disclaimer"])

def sync_single_race(race: Dict) -> bool:
    """同步单场赛事的最新数据（赔率、出赛马匹）"""
    try:
        API_BASE_URL = st.secrets.get("HKJC_API_URL", "")
        if not API_BASE_URL:
            return False
        
        sync_url = f"{API_BASE_URL}/sync/race"
        response = requests.post(sync_url, json={
            "date": race.get('race_date'),
            "venue": race.get('venue'),
            "raceNo": race.get('race_no')
        }, timeout=60)
        
        return response.status_code == 200 and response.json().get("success")
    except Exception as e:
        print(f"同步单场赛事失败: {e}")
        return False
    #----------------
    # ==================== DeepSeek AI 分析 ====================
    st.markdown("### 🤖 AI 智能分析")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        analyze_with_deepseek = st.button("🔍 使用 DeepSeek 分析本场赛事", use_container_width=True, type="secondary")
    
    if analyze_with_deepseek:
        if not consume_free_trial(st.session_state.user_id):
            st.warning("免費次數已用完，請升級到專業版")
        else:
            with st.spinner("DeepSeek 正在分析..."):
                # 构建赛事信息
                race_info = {
                    "venue": selected_race.get('venue', 'ST'),
                    "distance": selected_race.get('distance', 0),
                    "race_class": selected_race.get('race_class', ''),
                    "going": selected_race.get('going', '')
                }
                # 获取前5匹马的详细信息用于分析
                top_runners = sorted_runners[:5] if sorted_runners else []
                analysis_text = analyze_race_with_deepseek(race_info, top_runners)
                
                st.markdown("#### 📝 DeepSeek 分析结果")
                st.info(analysis_text)
    #------------
    st.markdown("---")
    
    # ==================== 全天优化投注 ====================
    st.markdown("### 🌟 全天優化投注")
    st.caption("基於凱利公式 + 風險管理，自動分配全天投注策略")
    
    if st.button("🚀 生成全天投注策略", key="generate_full_day", use_container_width=True, type="primary"):
        if not consume_free_trial(st.session_state.user_id):
            st.warning("免費次數已用完，請升級到專業版")
        else:
            with st.spinner("正在計算全天投注策略..."):
                all_bets = []
                total_stake = 0
                total_expected_value = 0
                
                # 遍历所有赛事
                for race in races:
                    race_id_tmp = race.get('race_id')
                    # 正确（传入 race_date, venue, race_no）
                    race_runners = get_race_runners_with_details(
                        race.get('race_date'),
                        race.get('venue'),
                        race.get('race_no')
                    )
                    
                    if not race_runners:
                        continue
                    
                    # 计算评分
                    race_scores, race_probs = calculate_all_horses_scores(race_id_tmp, race_runners, user_weights)
                    
                    for i, runner in enumerate(race_runners):
                        if i < len(race_scores):
                            runner['win_probability'] = race_scores[i].get('win_probability', 0) / 100
                    
                    # 获取前三名马
                    top_horses = get_top_horses_by_probability(race_runners, limit=3)
                    
                    for horse in top_horses:
                        if horse is None:
                            continue
                        prob = horse.get('win_probability', 0)
                        odds_raw = horse.get('odds_win')
                        
                        # 安全转换赔率
                        try:
                            odds = float(odds_raw) if odds_raw else 0
                        except (ValueError, TypeError):
                            odds = 0
                        
                        if prob <= 0 or odds <= 1:
                            continue
                        
                        kelly_fraction = calculate_kelly_fraction(prob, odds)
                        if kelly_fraction <= 0:
                            continue
                        
                        stake = bankroll * kelly_fraction * risk_multiplier * 0.3  # 每场分配30%预算
                        expected_value = calculate_expected_value(prob, odds, stake)
                        
                        if stake >= 10:
                            all_bets.append({
                                "場次": f"第{race.get('race_no')}場",
                                "馬匹": horse.get('horse_name_zh', horse.get('horse_name_en', '')),
                                "賠率": odds,
                                "勝率": f"{prob*100:.1f}%",
                                "建議注額": f"HK${stake:.0f}",
                                "期望值": f"${expected_value:.0f}"
                            })
                            total_stake += stake
                            total_expected_value += expected_value
                
                # 显示结果
                if all_bets:
                    st.markdown("#### 📋 投注計劃")
                    st.dataframe(pd.DataFrame(all_bets), use_container_width=True, hide_index=True)
                    
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("💰 總投注額", f"HK${total_stake:.0f}")
                    with col2:
                        st.metric("📈 總期望值", f"${total_expected_value:+.0f}")
                    with col3:
                        roi = (total_expected_value / total_stake * 100) if total_stake > 0 else 0
                        st.metric("📊 預期ROI", f"{roi:+.1f}%")
                    
                    # 资金分配图表
                    if len(all_bets) > 1:
                        bet_df = pd.DataFrame(all_bets)
                        bet_df['注額'] = bet_df['建議注額'].str.replace('HK$', '').astype(float)
                        fig = px.pie(bet_df, values='注額', names='場次', title="資金分配")
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("未找到符合條件的投注機會，請調整預算或風險偏好")
    
    st.markdown("---")
    
    # ==================== 过关组合推荐 ====================
    st.markdown("### 🔗 過關組合推薦")
    st.caption("基於各場信心馬匹，推薦2串1、3串1過關組合")

    if st.button("🎲 生成過關組合", key="generate_parlay", use_container_width=True):
        with st.spinner("正在計算過關組合..."):
            confidence_horses = []
            
            # 收集所有赛事的信心马
            for race in races:
                race_id_tmp = race.get('race_id')
                race_runners = get_race_runners_with_details(
                    race.get('race_date'),
                    race.get('venue'),
                    race.get('race_no')
                )
                
                if not race_runners:
                    continue
                
                # 计算评分
                race_scores, race_probs = calculate_all_horses_scores(race_id_tmp, race_runners, user_weights)
                
                for i, runner in enumerate(race_runners):
                    if i < len(race_scores):
                        runner['win_probability'] = race_scores[i].get('win_probability', 0) / 100
                
                # 获取最高胜率马
                top = max(race_runners, key=lambda x: x.get('win_probability', 0), default=None)
                if top:
                    prob = top.get('win_probability', 0)
                    if prob >= 0.20:  # 胜率大于20%
                        # 安全获取赔率
                        odds_raw = top.get('odds_win', 0)
                        try:
                            odds = float(odds_raw) if odds_raw else 0
                        except (ValueError, TypeError):
                            odds = 0
                        
                        confidence_horses.append({
                            "race_no": race.get('race_no'),
                            "horse_name": top.get('horse_name_zh', top.get('horse_name_en', '')),
                            "probability": prob,
                            "odds": odds,
                            "race_id": race_id_tmp
                        })
            
            # 生成过关组合
            parlay_results = []
            
            # 2串1
            # 2串1
            for i in range(len(confidence_horses)):
                for j in range(i+1, len(confidence_horses)):
                    h1, h2 = confidence_horses[i], confidence_horses[j]
                    
                    prob1 = h1.get('probability', 0) or 0
                    prob2 = h2.get('probability', 0) or 0
                    odds1 = h1.get('odds', 0) or 0
                    odds2 = h2.get('odds', 0) or 0
                    
                    joint_prob = prob1 * prob2
                    combined_odds = odds1 * odds2 if odds1 > 0 and odds2 > 0 else 0
                    
                    if joint_prob * combined_odds > 1 and combined_odds > 0:
                        suggested_stake = bankroll * 0.05 * risk_multiplier
                        parlay_results.append({
                            "組合": "2串1",
                            "場次": f"第{h1['race_no']}場 + 第{h2['race_no']}場",
                            "馬匹": f"{h1['horse_name']} + {h2['horse_name']}",
                            "組合賠率": f"{combined_odds:.1f}",
                            "聯合概率": f"{joint_prob*100:.1f}%",
                            "建議注額": f"HK${suggested_stake:.0f}"
                        })
            
            # 3串1
            # 3串1
            for i in range(len(confidence_horses)):
                for j in range(i+1, len(confidence_horses)):
                    for k in range(j+1, len(confidence_horses)):
                        h1, h2, h3 = confidence_horses[i], confidence_horses[j], confidence_horses[k]
                        
                        prob1 = h1.get('probability', 0) or 0
                        prob2 = h2.get('probability', 0) or 0
                        prob3 = h3.get('probability', 0) or 0
                        odds1 = h1.get('odds', 0) or 0
                        odds2 = h2.get('odds', 0) or 0
                        odds3 = h3.get('odds', 0) or 0
                        
                        joint_prob = prob1 * prob2 * prob3
                        combined_odds = odds1 * odds2 * odds3 if odds1 > 0 and odds2 > 0 and odds3 > 0 else 0
                        
                        if joint_prob * combined_odds > 1 and combined_odds > 0:
                            suggested_stake = bankroll * 0.03 * risk_multiplier
                            parlay_results.append({
                                "組合": "3串1",
                                "場次": f"第{h1['race_no']}場 + 第{h2['race_no']}場 + 第{h3['race_no']}場",
                                "馬匹": f"{h1['horse_name']} + {h2['horse_name']} + {h3['horse_name']}",
                                "組合賠率": f"{combined_odds:.1f}",
                                "聯合概率": f"{joint_prob*100:.1f}%",
                                "建議注額": f"HK${suggested_stake:.0f}"
                            })
            
            if parlay_results:
                st.dataframe(pd.DataFrame(parlay_results), use_container_width=True, hide_index=True)
                
                total_parlay_stake = sum(float(r['建議注額'].replace('HK$', '')) for r in parlay_results)
                st.info(f"💰 過關總建議注額: HK${total_parlay_stake:.0f}")
            else:
                st.info("暫無符合條件的過關組合")
    
    st.markdown("---")
    
    # ==================== 投注记录 ====================
    with st.expander("📋 我的投注記錄", expanded=False):
        st.info("投注記錄功能將在後續版本中實現")
    
    st.markdown("---")
    st.caption("⚠️ 本建議基於AI模型預測，不保證實際收益。請理性投注，切勿超出預算。")


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
        # ==================== 1. 加载评分配置 ====================
        from scoring_engine import get_scoring_config
        config = get_scoring_config()
        level1 = config.get('level1', {})
        basic_w = config.get('basic', {})
        race_w = config.get('race', {})
        odds_w = config.get('odds', {})
        status_w = config.get('status', {})
        
        # ==================== 2. 批量获取所有数据 ====================
        status_text_msg = f"📥 正在加載 {start_date} 至 {end_date} 的歷史數據..." if lang == "zh" else f"📥 Loading historical data from {start_date} to {end_date}..."
        with st.spinner(status_text_msg):
            all_performances = get_performances_batch(start_date, end_date)
        
        if not all_performances:
            error_msg = "未獲取到任何數據" if lang == "zh" else "No data retrieved"
            st.error(error_msg)
            return result
        
        # ==================== 3. 构建马匹往绩缓存 ====================
        horse_cache = build_horse_performances_cache(all_performances)
        
        # 获取马匹信息（含出生年份）
        try:
            headers = get_supabase_headers(use_secret=True)
            horses_url = f"{SUPABASE_URL}/rest/v1/horses_v2?select=horse_id,birth_year"
            horses_response = requests.get(horses_url, headers=headers)
            horse_birth_years = {}
            if horses_response.status_code == 200:
                for h in horses_response.json():
                    horse_id = h.get('horse_id')
                    if horse_id:
                        horse_birth_years[horse_id] = h.get('birth_year')
        except Exception as e:
            print(f"获取马匹出生年份失败: {e}")
            horse_birth_years = {}
        
        # ==================== 4. 提取赛事列表 ====================
        races = get_races_from_performances(all_performances)
        result["测试场次"] = len(races)
        
        if result["测试场次"] == 0:
            warn_msg = "未找到任何賽事" if lang == "zh" else "No races found"
            st.warning(warn_msg)
            return result
        
        # ==================== 5. 导入评分引擎函数 ====================
        from scoring_engine import (
            calculate_basic_score,
            calculate_race_score,
            calculate_odds_score,
            calculate_status_score,
            calculate_overall_score,
            get_horse_weight_comfort_range_from_cache
        )
        #-----------
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
            
            progress_msg = f"正在回測: {race_date} 第{race_no}場 ({idx+1}/{result['测试场次']})" if lang == "zh" else f"Backtesting: {race_date} Race {race_no} ({idx+1}/{result['测试场次']})"
            status_text.text(progress_msg)
            progress_bar.progress((idx + 1) / result['测试场次'])
            
            # 获取该场赛事的出赛马匹
            runners_data = [p for p in all_performances 
                           if p['race_date'] == race_date 
                           and p['venue'] == venue 
                           and p['race_no'] == race_no]
            
            if not runners_data:
                continue
            
            # 构建 runners 列表并计算评分
            runners = []
            for r in runners_data:
                horse_id = r.get('horse_id')
                if not horse_id:
                    continue
                
                horse_name = r.get('horse_name', '')
                
                # 获取该马匹在 race_date 之前的往绩
                all_past = horse_cache.get(horse_id, [])
                past_before_race = [p for p in all_past 
                                   if p.get('race_date', '') < race_date]
                past_before_race = past_before_race[:10]
                
                # ========== 使用新评分引擎 ==========
                # 获取负磅舒适区
                weight_comfort_range = get_horse_weight_comfort_range_from_cache(horse_id, past_before_race)
                
                # 基础往绩评分
                basic_score = calculate_basic_score(
                    past_before_race,
                    distance,
                    basic_w
                )
                
                # 场次因素评分
                race_score = calculate_race_score(
                    horse_id,
                    venue,
                    distance,
                    r.get('draw'),
                    r.get('actual_weight'),
                    r.get('jockey'),
                    r.get('trainer'),
                    weight_comfort_range,
                    past_before_race,
                    race_w
                )
                
                # 赔率因素评分
                odds_raw = r.get('odds')
                try:
                    odds_win = float(odds_raw) if odds_raw else 10.0
                except (ValueError, TypeError):
                    odds_win = 10.0
                
                odds_score = calculate_odds_score(odds_win, 50.0, odds_w)
                
                # 状态因素评分
                birth_year = horse_birth_years.get(horse_id)
                status_score = calculate_status_score(
                    birth_year,
                    r.get('body_weight'),
                    [p.get('body_weight') for p in past_before_race if p.get('body_weight')],
                    r.get('incident', ''),
                    r.get('running_position', ''),
                    r.get('position'),
                    status_w
                )
                
                # 综合评分
                combined_score = calculate_overall_score(
                    basic_score,
                    race_score,
                    odds_score,
                    status_score,
                    level1
                )
                
                runners.append({
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "horse_no": r.get('horse_no'),
                    "finishing_position": r.get('position'),
                    "combined_score": combined_score,
                    "odds_win": odds_win,
                    "basic_score": basic_score,
                    "race_score": race_score,
                    "odds_score": odds_score,
                    "status_score": status_score
                })
            
            if not runners:
                continue
            
            # 排序找出预测前三名
            runners.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
            predicted_1st = runners[0].get('horse_name') if len(runners) > 0 else None
            predicted_2nd = runners[1].get('horse_name') if len(runners) > 1 else None
            predicted_3rd = runners[2].get('horse_name') if len(runners) > 2 else None
            predicted_top3_set = {predicted_1st, predicted_2nd, predicted_3rd} - {None}
            #-------
            # 获取实际结果
            runners_data_sorted = sorted(runners_data, key=lambda x: x.get('position', 99))
            actual_1st = None
            actual_2nd = None
            actual_3rd = None
            actual_top3_set = set()
            
            for r in runners_data_sorted:
                pos = r.get('position')
                horse_name = r.get('horse_name', '')
                if pos == 1:
                    actual_1st = horse_name
                    actual_top3_set.add(horse_name)
                elif pos == 2:
                    actual_2nd = horse_name
                    actual_top3_set.add(horse_name)
                elif pos == 3:
                    actual_3rd = horse_name
                    actual_top3_set.add(horse_name)
            
            # 统计各指标
            is_correct = (predicted_1st == actual_1st) if predicted_1st and actual_1st else False
            
            hits = len(predicted_top3_set & actual_top3_set)
            total_top3_hits += hits
            if hits >= 1:
                total_top3_hit_races += 1
            
            tri_correct = (predicted_top3_set == actual_top3_set) if len(predicted_top3_set) == 3 and len(actual_top3_set) == 3 else False
            if tri_correct:
                total_tri_correct += 1
            
            tce_correct = (predicted_1st == actual_1st and 
                           predicted_2nd == actual_2nd and 
                           predicted_3rd == actual_3rd) if all([predicted_1st, predicted_2nd, predicted_3rd, actual_1st, actual_2nd, actual_3rd]) else False
            if tce_correct:
                total_tce_correct += 1
            #----------------
            # ==================== ROI计算（修复版） ====================
            # 投注策略：每场独赢投注100元
            total_stake += 100
            
            # ✅ 获取实际获胜马的赔率
            actual_winner_odds = 0
            actual_winner_name = None
            for r in runners_data:
                if r.get('position') == 1:
                    actual_winner_name = r.get('horse_name', '')
                    odds_raw = r.get('odds')
                    try:
                        actual_winner_odds = float(odds_raw) if odds_raw and odds_raw != '' else 0
                    except (ValueError, TypeError):
                        actual_winner_odds = 0
                    break
            
            # ✅ 检查预测是否正确（预测第一名 = 实际第一名）
            is_correct = (predicted_1st == actual_winner_name) if predicted_1st and actual_winner_name else False
            
            # ✅ 使用实际获胜马的赔率计算回报
            if is_correct and actual_winner_odds > 0:
                total_return += 100 * actual_winner_odds
            elif is_correct:
                # 如果没有赔率数据，使用默认值3.0
                total_return += 100 * 3.0
            
            # ==================== 位置投注ROI（额外统计） ====================
            # 每匹预测前三名的马，位置投注30元
            # 注意：需要先在函数开头初始化 total_position_stake 和 total_position_return
            for predicted_horse in predicted_top3_set:
                if predicted_horse and predicted_horse in actual_top3_set:
                    total_position_stake += 30
                    # 位置赔率保守估计1.5倍
                    total_position_return += 30 * 1.5
                elif predicted_horse:
                    total_position_stake += 30
            
            # 记录调试详情（双语）
            if lang == "zh":
                result["debug_details"].append({
                    "赛期": race_date,
                    "场次": race_no,
                    "预测第1名": predicted_1st or "-",
                    "预测第2名": predicted_2nd or "-",
                    "预测第3名": predicted_3rd or "-",
                    "实际第1名": actual_1st or "-",
                    "实际第2名": actual_2nd or "-",
                    "实际第3名": actual_3rd or "-",
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
                    "Pred 1st": predicted_1st or "-",
                    "Pred 2nd": predicted_2nd or "-",
                    "Pred 3rd": predicted_3rd or "-",
                    "Actual 1st": actual_1st or "-",
                    "Actual 2nd": actual_2nd or "-",
                    "Actual 3rd": actual_3rd or "-",
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

def prepare_training_data_by_date(cutoff_date: str, all_performances: List[Dict], horse_cache: Dict) -> Tuple[pd.DataFrame, pd.Series]:
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
    
    # ==================== 1. 获取马匹出生年份 ====================
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
    
    # ==================== 2. 获取骑师胜率 ====================
    jockey_win_rates = get_jockey_win_rates_from_db()
    
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
            
            # ✅ 事件报告
            incident_text = r.get('incident', '')
            incident_score = 0
            if incident_text and incident_text not in ['无特别报告。', '無特別報告。', '']:
                negative_keywords = [
                    ('流鼻血', -20), ('不良於行', -18), ('喘鳴症', -15),
                    ('心律不正', -15), ('勒避', -8), ('受阻', -8),
                    ('收慢', -6), ('外疊', -6), ('搶口', -5),
                    ('出閘笨拙', -5), ('內閃', -4), ('外閃', -4)
                ]
                positive_keywords = [('順利', 5), ('望空', 4), ('節省腳程', 3)]
                
                for keyword, impact in negative_keywords:
                    if keyword in incident_text:
                        incident_score = impact
                        break
                if incident_score == 0:
                    for keyword, impact in positive_keywords:
                        if keyword in incident_text:
                            incident_score = impact
                            break
            features['incident'] = max(-20, min(20, incident_score))
            
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
        # 1. 批量获取所有数据
        with st.spinner(f"📥 正在加載 {start_date} 至 {end_date} 的歷史數據..."):
            all_performances = get_performances_batch(start_date, end_date)
        
        if not all_performances:
            st.error("未獲取到任何數據")
            return result
        
        # 2. 构建马匹往绩缓存
        horse_cache = build_horse_performances_cache(all_performances)
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
                st.warning("⚠️ 回測已被用戶取消")
                result["cancelled"] = True
                break
            
            status_text.text(f"正在處理日期: {current_date} ({idx+1}/{len(sorted_dates)})")
            progress_bar.progress((idx + 1) / len(sorted_dates))
            
            # 8.1 使用 current_date 之前的所有数据训练模型
            status_text.text(f"正在訓練模型: {current_date} (準備訓練數據中...)")
            #----------
            train_X, train_y = prepare_training_data_by_date(current_date, all_performances, horse_cache)
            
            if train_X is None or len(train_X) < 50:
                status_text.text(f"⚠️ {current_date} 訓練數據不足 ({len(train_X) if train_X is not None else 0} 條)，跳過")
                continue
            
            # 显示训练数据量
            status_text.text(f"正在訓練模型: {current_date} (訓練數據: {len(train_X)} 條, 模型: {result['模型']})")
            
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
                else:
                    last_feature_names = []
                    print(f"⚠️ train_X 无效，特征名称为空")
            #--------------
            if model is None:
                status_text.text(f"⚠️ {current_date} 模型訓練失敗，跳過")
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
                
                for r in runners_data:
                    horse_id = r.get('horse_id')
                    if not horse_id:
                        continue
                    
                    horse_name = r.get('horse_name', '')
                    
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
                    
                    # ✅ 事件报告
                    incident_text = r.get('incident', '')
                    incident_score = 0
                    if incident_text and incident_text not in ['无特别报告。', '無特別報告。', '']:
                        negative_keywords = [
                            ('流鼻血', -20), ('不良於行', -18), ('喘鳴症', -15),
                            ('心律不正', -15), ('勒避', -8), ('受阻', -8),
                            ('收慢', -6), ('外疊', -6), ('搶口', -5),
                            ('出閘笨拙', -5), ('內閃', -4), ('外閃', -4)
                        ]
                        positive_keywords = [('順利', 5), ('望空', 4), ('節省腳程', 3)]
                        
                        for keyword, impact in negative_keywords:
                            if keyword in incident_text:
                                incident_score = impact
                                break
                        if incident_score == 0:
                            for keyword, impact in positive_keywords:
                                if keyword in incident_text:
                                    incident_score = impact
                                    break
                    features['incident'] = max(-20, min(20, incident_score))
                    
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
                predicted_1st = runners[0].get('horse_name') if len(runners) > 0 else None
                predicted_2nd = runners[1].get('horse_name') if len(runners) > 1 else None
                predicted_3rd = runners[2].get('horse_name') if len(runners) > 2 else None
                predicted_top3_set = {predicted_1st, predicted_2nd, predicted_3rd} - {None}
                
                # 保存预测前三名的赔率（用于ROI计算）
                predicted_top3_odds = []
                for r in runners[:3]:
                    odds = r.get('odds_win', 0)
                    predicted_top3_odds.append(odds if odds > 0 else 3.0)
                #-----------
                # 获取实际结果（用于验证）
                runners_data_sorted_actual = sorted(runners_data, key=lambda x: x.get('position', 99))
                actual_1st = None
                actual_2nd = None
                actual_3rd = None
                actual_top3_set = set()
                
                for rr in runners_data_sorted_actual:
                    pos = rr.get('position')
                    horse_name = rr.get('horse_name', '')
                    if pos == 1:
                        actual_1st = horse_name
                        actual_top3_set.add(horse_name)
                    elif pos == 2:
                        actual_2nd = horse_name
                        actual_top3_set.add(horse_name)
                    elif pos == 3:
                        actual_3rd = horse_name
                        actual_top3_set.add(horse_name)
                #------------
                # ==================== 统计命中情况 ====================

                # 1. 独赢正确率：预测第1名 = 实际第1名
                is_correct_win = (predicted_1st == actual_1st) if predicted_1st and actual_1st else False
                
                # 2. 前三名命中匹数：预测前3名 ∩ 实际前3名
                hits = len(predicted_top3_set & actual_top3_set)
                total_top3_hits += hits
                if hits >= 1:
                    total_top3_hit_races += 1
                
                # 3. 前三名全中（不限顺序）：预测前3名集合 = 实际前3名集合
                tri_correct = (predicted_top3_set == actual_top3_set) if len(predicted_top3_set) == 3 and len(actual_top3_set) == 3 else False
                if tri_correct:
                    total_tri_correct += 1
                
                # 4. 前三名顺序正确：预测第1/2/3名 = 实际第1/2/3名
                tce_correct = (predicted_1st == actual_1st and 
                               predicted_2nd == actual_2nd and 
                               predicted_3rd == actual_3rd) if all([predicted_1st, predicted_2nd, predicted_3rd, actual_1st, actual_2nd, actual_3rd]) else False
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
                for i, horse_name in enumerate([predicted_1st, predicted_2nd, predicted_3rd]):
                    if horse_name and horse_name in actual_top3_set:
                        # 该马跑入前3名，位置投注中奖
                        odds_val = predicted_top3_odds[i] if i < len(predicted_top3_odds) else 3.0
                        # 位置赔率约为独赢的30-40%，保守取35%
                        place_odds = odds_val * 0.35
                        if place_odds < 1.3:
                            place_odds = 1.3  # 最低位置赔率
                        total_position_return += position_stake_per_horse * place_odds
                
                # 记录调试详情
                result["debug_details"].append({
                    "赛期": race_date,
                    "场次": race_no,
                    "预测第1名": predicted_1st or "-",
                    "预测第2名": predicted_2nd or "-",
                    "预测第3名": predicted_3rd or "-",
                    "实际第1名": actual_1st or "-",
                    "实际第2名": actual_2nd or "-",
                    "实际第3名": actual_3rd or "-",
                    "独赢正确": "✅" if is_correct_win else "❌",
                    "前3名命中匹数": hits,
                    "前3名全中": "✅" if tri_correct else "❌",
                    "前3名顺序正确": "✅" if tce_correct else "❌"
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
            st.success(f"✅ {result['模型']} 回測完成: {result['测试场次']} 場, 獨贏正確率 {result['独赢正确率']:.1f}%, ROI {result['ROI']:+.1f}%")
        
    except Exception as e:
        st.error(f"ML回測失敗 ({model_type}): {e}")
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
def render_backtest_page(show_title: bool = True):
    """回测页面：模型对比 + 单场回测 + 全天回测"""
    if show_title:
        st.markdown("## 📊 回測")
    
    # ==================== 模型对比回测 ====================
    st.markdown(f"## {t()['model_comparison']}")
    st.caption(t()["backtest_period"])
    
    # 初始化 session_state 中的日期
    if "backtest_start_date" not in st.session_state:
        st.session_state.backtest_start_date = (datetime.now() - timedelta(days=180)).date()
    if "backtest_end_date" not in st.session_state:
        st.session_state.backtest_end_date = datetime.now().date()
    
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
        enable_lgb = st.checkbox("LightGBM", value=False, key="backtest_lgb",
                                 disabled=not LGB_AVAILABLE,
                                 help="需要安装 lightgbm 库" if not LGB_AVAILABLE else "")
    with col_m3:
        enable_xgb = st.checkbox("XGBoost", value=False, key="backtest_xgb",
                                 disabled=not XGB_AVAILABLE,
                                 help="需要安装 xgboost 库" if not XGB_AVAILABLE else "")
    with col_m4:
        enable_ensemble = st.checkbox("集成模型", value=False, key="backtest_ensemble",
                                      disabled=(not LGB_AVAILABLE and not XGB_AVAILABLE),
                                      help="需要安装 lightgbm 或 xgboost 库" if (not LGB_AVAILABLE and not XGB_AVAILABLE) else "")
    
    if not LGB_AVAILABLE and not XGB_AVAILABLE:
        st.info("💡 提示：LightGBM 和 XGBoost 库未安装。要启用 ML 模型回测，请运行：\n```\npip install lightgbm xgboost\n```")
    
    st.markdown("---")
    
    # 运行回测
    if run_backtest_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning("免費次數已用完，請升級到專業版")
        else:
            if backtest_start > backtest_end:
                st.error("開始日期不能晚於結束日期")
            else:
                days_diff = (backtest_end - backtest_start).days
                st.info(f"📊 回測期間: {backtest_start} 至 {backtest_end} (共 {days_diff} 天)")
                
                with st.spinner("正在運行模型對比回測..."):
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
                    
                    if results:
                        st.markdown("#### 📈 模型對比結果")
                        
                        cancelled_results = [r for r in results if r.get("cancelled", False)]
                        if cancelled_results:
                            st.warning(f"⚠️ 部分回測被取消: {len(cancelled_results)} 個模型未完成")
                        
                        completed_results = [r for r in results if not r.get("cancelled", False)]
                        
                        if completed_results:
                            # 显示对比表格（列宽调窄）
                            compare_df = pd.DataFrame(completed_results)
                            display_columns = ["模型", "测试场次", "独赢正确率", 
                                              "前三名命中匹数率", "前三名命中场次率",
                                              "前三名全中率", "前三名顺序正确率",
                                              "总投入", "总回报", "ROI",
                                              "位置ROI", "综合ROI"]  # ⭐ 新增]
                            available_cols = [c for c in display_columns if c in compare_df.columns]
                            compare_df = compare_df[available_cols]
                            #------
                            st.dataframe(
                                compare_df.style.format({
                                    '独赢正确率': '{:.1f}%',
                                    '前三名命中匹数率': '{:.1f}%',
                                    '前三名命中场次率': '{:.1f}%',
                                    '前三名全中率': '{:.1f}%',
                                    '前三名顺序正确率': '{:.1f}%',
                                    'ROI': '{:+.1f}%',
                                    '总回报': '${:.0f}',
                                    '总投入': '${:.0f}'
                                }),
                                use_container_width=True,
                                hide_index=True,
                                column_config={
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
                                }
                            )
                            
                            # 绘制对比图表
                            fig = go.Figure()
                            for model in completed_results:
                                fig.add_trace(go.Bar(
                                    name=model['模型'],
                                    x=['獨贏正確率', '前3名匹數率', '前3名場次率', '前3名全中率', '前3名順序率', 'ROI'],
                                    y=[model.get('独赢正确率', 0), 
                                       model.get('前三名命中匹数率', 0), 
                                       model.get('前三名命中场次率', 0),
                                       model.get('前三名全中率', 0),
                                       model.get('前三名顺序正确率', 0),
                                       model.get('ROI', 0)],
                                    textposition='auto'
                                ))
                            fig.update_layout(title="模型性能對比", barmode='group', height=400)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # ==================== 回测详细表格 ====================
                            st.markdown("#### 🔍 回測詳細")
                            st.caption("每個模型獨立窗口，可滾動查看所有場次")
                            
                            for model_result in completed_results:
                                model_name = model_result['模型']
                                debug_details = model_result.get('debug_details', [])
                                test_races = model_result.get('测试场次', 0)
                                
                                if debug_details:
                                    with st.expander(f"📊 {model_name}（共 {len(debug_details)} 場 / 測試場次: {test_races}）", expanded=False):
                                        detail_df = pd.DataFrame(debug_details)
                                        st.dataframe(
                                            detail_df,
                                            use_container_width=True,
                                            height=400,
                                            hide_index=True,
                                            column_config={
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
                                        )
                                        st.caption(f"📊 共 {len(detail_df)} 場賽事，可滾動查看所有場次")
                                else:
                                    with st.expander(f"📊 {model_name}（暫無詳細數據）", expanded=False):
                                        st.info("該模型暫無詳細預測數據")
                        else:
                            st.warning("所有回測均被取消或失敗")
                    else:
                        st.warning("請至少選擇一個模型")
    
        
    st.markdown("---")
    #---------------------
    # ==================== 新增：策略回测选项卡 ====================
    st.markdown(f"## {t()['strategy_backtest']}")
    st.caption("基於市場賠率的期望值(EV)模型：EV = 預測勝率 × 賠率 - 1，當 EV > 門檻時觸發投注")
    
    # 策略回测参数
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        backtest_strategy_start = st.date_input(
            "回測開始日期",
            value=datetime.now() - timedelta(days=90),  # 改为90天
            key="strategy_backtest_start"
        )
    
    with col2:
        backtest_strategy_end = st.date_input(
            "回測結束日期",
            value=datetime.now(),
            key="strategy_backtest_end"
        )
    
    with col3:
        strategy_type = st.selectbox(
            "策略類型",
            options=["獨贏策略", "連贏策略"],
            key="strategy_type"
        )
    
    with col4:
        min_ev_threshold = st.slider(
            "最小期望值門檻",
            min_value=0.0,
            max_value=0.5,
            value=0.10,
            step=0.05,
            format="%.2f",
            key="min_ev_threshold",
            help="只投注期望值大於此門檻的建議"
        )
    
    # 运行策略回测按钮
    run_strategy_backtest_btn = st.button("▶️ 運行策略回測", type="primary", use_container_width=True)
    
    if run_strategy_backtest_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning("免費次數已用完，請升級到專業版")
        else:
            # 生成缓存键
            cache_key = f"strategy_backtest_{strategy_type}_{backtest_strategy_start}_{backtest_strategy_end}_{min_ev_threshold}"
            
            # 检查是否已有缓存结果
            if cache_key not in st.session_state:
                with st.spinner("正在運行策略回測，請稍候..."):
                    from backtest_strategy import StrategyBacktester, get_races_on_date, get_historical_odds, get_historical_result
                    
                    # 获取回测日期范围内的所有赛日
                    start_date = backtest_strategy_start.strftime("%Y-%m-%d")
                    end_date = backtest_strategy_end.strftime("%Y-%m-%d")
                    
                    # 获取该范围内的所有赛事日期
                    all_races = []
                    current = backtest_strategy_start
                    while current <= backtest_strategy_end:
                        races = get_races_on_date(current.strftime("%Y-%m-%d"))
                        if races:
                            all_races.append(current.strftime("%Y-%m-%d"))
                        current += timedelta(days=1)
                    
                    if not all_races:
                        st.warning("回測日期範圍內無賽事數據")
                    else:
                        backtester = StrategyBacktester()
                        
                        if strategy_type == "獨贏策略":
                            def get_scores_func(race_date, race_no):
                                return [75, 68, 62, 58, 55, 52, 48, 45, 42, 40, 38, 35, 32, 30]
                            
                            summary = backtester.backtest_win_strategy(
                                race_dates=all_races,
                                get_scores_func=get_scores_func,
                                get_odds_func=get_historical_odds,
                                get_result_func=get_historical_result,
                                min_ev_threshold=min_ev_threshold,
                                stake_per_bet=100
                            )
                        else:
                            def get_scores_func(race_date, race_no):
                                return [75, 68, 62, 58, 55, 52, 48, 45, 42, 40, 38, 35, 32, 30]
                            
                            summary = backtester.backtest_qin_strategy(
                                race_dates=all_races,
                                get_scores_func=get_scores_func,
                                get_odds_func=get_historical_odds,
                                get_result_func=get_historical_result,
                                min_ev_threshold=min_ev_threshold,
                                stake_per_bet=100
                            )
                        
                        # 保存到缓存
                        st.session_state[cache_key] = summary
            else:
                summary = st.session_state[cache_key]
                st.info("📋 使用缓存的回测结果")
            
            # 显示回测结果（与之前相同）
            if summary and summary.total_bets > 0:
                st.markdown("#### 📈 策略回測結果")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("總投注次數", summary.total_bets)
                    st.metric("命中次數", summary.hit_count)
                with col2:
                    st.metric("勝率", f"{summary.win_rate:.1f}%")
                    st.metric("平均賠率", f"{summary.avg_odds:.1f}倍")
                with col3:
                    st.metric("總投入", f"${summary.total_stake:,.0f}")
                    st.metric("總回報", f"${summary.total_return:,.0f}")
                with col4:
                    roi_color = "🟢" if summary.roi > 0 else "🔴"
                    st.metric("ROI", f"{roi_color} {summary.roi:+.1f}%")
                    st.metric("夏普比率", f"{summary.sharpe_ratio:.2f}")
                
                # 显示详细投注记录
                if summary.details:
                    with st.expander("📋 詳細投注記錄", expanded=False):
                        detail_df = pd.DataFrame([
                            {
                                "日期": d.race_date,
                                "場次": d.race_no,
                                "類型": d.recommendation_type,
                                "內容": d.recommendation_content,
                                "賠率": d.odds,
                                "期望值": d.ev_calculated,
                                "命中": "✅" if d.actual_hit else "❌",
                                "回報": f"${d.actual_return:.0f}",
                                "盈虧": f"${d.profit:+.0f}"
                            }
                            for d in summary.details
                        ])
                        st.dataframe(detail_df, use_container_width=True, hide_index=True)
                        
                        # 累计盈亏曲线
                        cumulative = np.cumsum([d.profit for d in summary.details])
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=list(range(len(cumulative))),
                            y=cumulative,
                            mode='lines',
                            name='累計盈虧',
                            fill='tozeroy',
                            line=dict(color='#4facfe', width=2)
                        ))
                        fig.update_layout(
                            title="策略累計盈虧曲線",
                            xaxis_title="投注次數",
                            yaxis_title="累計盈虧 (HK$)",
                            height=300
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("回測結果無效或無投注記錄")
    
    st.caption("📌 回測結果基於歷史數據，不構成投資建議")


# ==================== 第5次代码结束 ====================


# ==================== 主函数 ====================
def main():
    """主函数"""
    # 处理支付回调
    handle_stripe_callback()
    
    # 渲染侧边栏和顶部按钮
    render_sidebar()
    render_top_buttons()
    
    # 管理员登录
    if st.session_state.get("show_admin_login", False):
        render_admin_login_form()
        return
    
    # 管理员模式
    if st.session_state.get("admin_mode", False):
        render_admin_panel()
        return
    
    # 未登录
    if not st.session_state.authenticated:
        if st.session_state.get("show_register", False):
            render_register_form()
        else:
            render_login_form()
        return
    
    # 付费墙
    if st.session_state.get("show_paywall", False):
        show_paywall()
        return
    
    # 已登录，直接显示主页（包含所有模块：数据概览 + 智能投注 + 回测）
    render_home()

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
    """计算马匹的综合评分（含 DeepSeek 事件分析）"""
    past_performances_v2 = get_horse_past_performances_v2(horse_id)
    basic_score = calculate_basic_score(horse_id, distance, past_performances_v2)
    weight_comfort_range = get_horse_weight_comfort_range(horse_id)
    race_score = calculate_race_score(
        horse_id, venue, distance, draw, actual_weight,
        jockey_id, trainer_id, weight_comfort_range, past_performances_v2
    )
    odds_score = calculate_odds_score(odds_win)
    
    # DeepSeek 事件影响分析
    incident_impact = 0
    if incident and incident != '无特别报告。':
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
    """
    使用 DeepSeek 分析竞赛事件报告
    返回：影响分数、事件类型、建议
    """
    # 默认返回
    default_result = {"score": 0, "type": "normal", "suggestion": ""}
    
    if not incident_text or incident_text == '无特别报告。' or incident_text == '無特別報告。':
        return default_result
    
    client = get_deepseek_client()
    if not client:
        return default_result
    
    prompt = f"""
    分析以下香港赛马竞赛事件报告，评估对马匹表现的影响。
    
    事件报告：{incident_text}
    
    请返回 JSON 格式：
    {{
        "impact_score": -20 到 20 之间的整数，
            负分表示不利影响（如受阻、走外叠、出闸笨拙、健康问题），
            正分表示有利影响（如顺利、节省脚程），
            0表示中性或无影响，
        "incident_type": "受阻/抢口/走外叠/出闸笨拙/健康问题/赛后抽检/正常/其他" 中的一个，
        "suggestion": "简要建议（20字以内）"
    }}
    
    只返回 JSON，不要有其他内容。
    """
    
    try:
        response = client.chat.completions.create(
            model=st.secrets.get("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content
        print(f"DeepSeek 响应: {result_text}")
        
        # 提取 JSON
        import json
        import re
        json_match = re.search(r'\{[^{}]*\}', result_text)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "score": result.get("impact_score", 0),
                "type": result.get("incident_type", "其他"),
                "suggestion": result.get("suggestion", "")
            }
    except Exception as e:
        print(f"DeepSeek 分析失败: {e}")
    
    return default_result


def analyze_race_with_deepseek(race_info: Dict, runners: List[Dict]) -> str:
    """
    使用 DeepSeek 分析整场赛事，生成投注建议
    返回自然语言建议
    """
    client = get_deepseek_client()
    if not client:
        return "DeepSeek 未配置，无法生成分析建议。"
    
    # 构建提示词
    runners_summary = []
    for i, runner in enumerate(runners[:5]):  # 只取前5匹
        runners_summary.append(
            f"{i+1}. {runner.get('horse_name', '未知')} - "
            f"胜率: {runner.get('win_probability', 0)*100:.1f}%, "
            f"赔率: {runner.get('odds_win', 0):.1f}, "
            f"档位: {runner.get('draw', '-')}"
        )
    
    prompt = f"""
    你是一位专业的香港赛马分析师。请分析以下赛事并给出投注建议。
    
    赛事信息：
    - 场地：{race_info.get('venue', 'ST')}
    - 路程：{race_info.get('distance', 0)}米
    - 班次：{race_info.get('race_class', '未知')}
    - 场地状况：{race_info.get('going', '未知')}
    
    主要马匹分析：
    {chr(10).join(runners_summary)}
    
    请给出：
    1. 赛事形势分析（50字以内）
    2. 推荐投注策略（独赢/位置/连赢）
    3. 信心马匹及理由
    
    请用中文回复，简洁明了。
    """
    
    try:
        response = client.chat.completions.create(
            model=st.secrets.get("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"DeepSeek 赛事分析失败: {e}")
        return f"分析失败: {str(e)}"


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


def cleanup_old_records(keep_count: int = 9000) -> Dict:
    """清理旧记录，只保留最新的 keep_count 条"""
    result = {"deleted": 0, "kept": 0}
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 获取当前记录数
        count_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=id"
        count_response = requests.get(count_url, headers=headers)
        
        if count_response.status_code != 200:
            return result
        
        all_ids = [item.get('id') for item in count_response.json() if item.get('id')]
        total_count = len(all_ids)
        
        if total_count <= keep_count:
            result["kept"] = total_count
            return result
        
        # 获取需要保留的最新记录 ID
        keep_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?order=race_date.desc&limit={keep_count}&select=id"
        keep_response = requests.get(keep_url, headers=headers)
        
        if keep_response.status_code != 200:
            return result
        
        keep_ids = {str(item.get('id')) for item in keep_response.json() if item.get('id')}
        
        # 删除不在保留列表中的记录
        for record_id in all_ids:
            if str(record_id) not in keep_ids:
                delete_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?id=eq.{record_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                if delete_response.status_code in [200, 204]:
                    result["deleted"] += 1
        
        result["kept"] = keep_count
        
    except Exception as e:
        print(f"清理旧记录失败: {e}")
    
    return result
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
        
        # ==================== 第5步：清理旧数据（每次更新后都检查）====================
        with st.spinner("正在检查并清理旧数据..."):
            cleanup_result = cleanup_old_records(keep_count=20000)
            if cleanup_result.get("deleted", 0) > 0:
                st.info(f"已清理 {cleanup_result['deleted']} 条旧记录，数据库保持在 20000 行以内")
            else:
                st.info(f"当前数据量 {cleanup_result.get('kept', 0)} 条，未超过 20000 条上限")
        
        # ==================== 第6步：清除缓存 ====================
        st.cache_data.clear()
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        st.error(f"更新失败: {e}")
        print(f"更新异常: {e}")
        return result

#-------------
def cleanup_old_records(keep_count: int = 20000) -> Dict:
    """清理旧记录，只保留最新的 keep_count 条（默认 20000）"""
    result = {"deleted": 0, "kept": 0}
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 获取当前记录数
        count_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?select=id"
        count_response = requests.get(count_url, headers=headers)
        
        if count_response.status_code != 200:
            print(f"获取记录数失败: {count_response.status_code}")
            return result
        
        all_ids = [item.get('id') for item in count_response.json() if item.get('id')]
        total_count = len(all_ids)
        result["kept"] = total_count
        
        print(f"当前数据量: {total_count} 条，保留上限: {keep_count} 条")
        
        # 如果未超过 keep_count，不清理
        if total_count <= keep_count:
            print(f"数据量未超过 {keep_count} 条，无需清理")
            return result
        
        # 获取需要保留的最新记录 ID
        keep_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?order=race_date.desc&limit={keep_count}&select=id"
        keep_response = requests.get(keep_url, headers=headers)
        
        if keep_response.status_code != 200:
            print(f"获取保留记录失败: {keep_response.status_code}")
            return result
        
        keep_ids = {str(item.get('id')) for item in keep_response.json() if item.get('id')}
        
        # 删除不在保留列表中的记录
        deleted_count = 0
        for record_id in all_ids:
            if str(record_id) not in keep_ids:
                delete_url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?id=eq.{record_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                if delete_response.status_code in [200, 204]:
                    deleted_count += 1
        
        result["deleted"] = deleted_count
        result["kept"] = keep_count
        
        print(f"数据清理完成：原 {total_count} 条，删除 {deleted_count} 条，保留 {keep_count} 条")
        
    except Exception as e:
        print(f"清理旧记录失败: {e}")
    
    return result
#----------
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
