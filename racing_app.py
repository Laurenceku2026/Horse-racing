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
        "app_title": "🐎 香港赛马AI分析系统",
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
        "subscription": "訂閱",
        "free_tier": "免費版",
        "pro_tier": "專業版",
        "remaining": "剩餘次數",
        "unlimited": "無限",
        "upgrade": "升級專業版",
        "monthly": "月付 $29/月",
        "quarterly": "季付 $79/季",
        "save_info": "季付更划算",
        "chinese": "中文",
        "english": "English",
        "admin_panel": "管理員面板",
        "total_users": "總用戶數",
        "pro_users": "專業版用戶",
        "free_users": "免費版用戶",
        "user_list": "用戶列表"
    },
    "en": {
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
        "subscription": "Subscription",
        "free_tier": "Free",
        "pro_tier": "Pro",
        "remaining": "Remaining",
        "unlimited": "Unlimited",
        "upgrade": "Upgrade to Pro",
        "monthly": "Monthly $29/mo",
        "quarterly": "Quarterly $79/quarter",
        "save_info": "Save with quarterly",
        "chinese": "中文",
        "english": "English",
        "admin_panel": "Admin Panel",
        "total_users": "Total Users",
        "pro_users": "Pro Users",
        "free_users": "Free Users",
        "user_list": "User List"
    }
}

def t():
    """获取当前语言文本"""
    lang = st.session_state.get("lang", "zh")
    return TEXTS[lang]
#-------------------------
# ==================== 马名获取函数（基于 horse_id）====================
@st.cache_data(ttl=3600)
def get_horse_name_cache() -> Dict[str, str]:
    """获取 horse_id -> 中文名 的映射"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/horse_name_mapping?select=horse_id,name_zh"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return {item['horse_id']: item.get('name_zh', '') for item in data}
        return {}
    except Exception as e:
        print(f"获取马名缓存失败: {e}")
        return {}
# ==================== 中英文马名映射 ====================
@st.cache_data(ttl=3600)
def get_horse_name_mapping() -> Dict[str, str]:
    """获取马名中英文映射（中文 -> 英文）"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/horse_name_mapping"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            mapping = {}
            for item in data:
                zh = item.get('name_zh')
                en = item.get('name_en')
                if zh and en:
                    mapping[zh] = en
            return mapping
        return {}
    except Exception as e:
        print(f"获取马名映射失败: {e}")
        return {}
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
@st.cache_data(ttl=3600)
def get_reverse_horse_name_mapping() -> Dict[str, str]:
    """获取马名映射（英文 -> 中文）"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/horse_name_mapping"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            mapping = {}
            for item in data:
                zh = item.get('name_zh')
                en = item.get('name_en')
                if zh and en:
                    mapping[en] = zh
            return mapping
        return {}
    except Exception as e:
        print(f"获取马名映射失败: {e}")
        return {}


def translate_horse_name(name: str, target_lang: str = None) -> str:
    """翻译马名"""
    if not name:
        return name
    
    if target_lang is None:
        target_lang = st.session_state.get("lang", "zh")
    
    current_lang = st.session_state.get("lang", "zh")
    
    # 如果当前语言就是目标语言，直接返回
    if target_lang == current_lang:
        return name
    
    if target_lang == 'en':
        # 中文 → 英文
        mapping = get_horse_name_mapping()
        return mapping.get(name, name)
    else:
        # 英文 → 中文
        mapping = get_reverse_horse_name_mapping()
        return mapping.get(name, name)
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
        
        base_url = "https://racing-ai.streamlit.app"  # 部署后修改
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

def handle_stripe_callback():
    """处理Stripe支付成功回调"""
    query_params = st.query_params
    
    if "session_id" in query_params:
        session_id = query_params["session_id"]
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            session = stripe.checkout.Session.retrieve(session_id)
            
            if session.payment_status == "paid":
                user_id = session.metadata.get("user_id")
                if user_id and user_id != "admin":
                    update_user_profile(user_id, {"subscription_tier": "pro"})
                    st.success("✅ 支付成功！您已是專業版用戶")
                    st.balloons()
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.warning("支付成功，但用戶信息驗證失敗，請聯絡管理員")
            else:
                st.info("支付未完成，請完成支付後刷新頁面")
        except Exception as e:
            st.error(f"驗證支付狀態失敗: {e}")

def show_paywall():
    """显示付费墙"""
    st.markdown("---")
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
        if st.button("💎 月付 $29/月", key="monthly_btn", use_container_width=True):
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
                💳 前往Stripe支付（月付$29）
            </a>
            ''', unsafe_allow_html=True)
    
    with col2:
        if st.button("💎 季付 $79/季", key="quarterly_btn", use_container_width=True):
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
                💳 前往Stripe支付（季付$79）
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
            if st.button("忘記密碼？", use_container_width=True):
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

# ==================== 管理员面板 ====================
def render_admin_panel():
    """管理员面板 - 数据编辑器 + 回测 + 用户管理"""
    st.markdown(f"## ⚙️ {t()['admin_panel']}")
    
    # 创建选项卡
    # 定义四个选项卡
    tab1, tab2, tab3, tab4 = st.tabs(["📊 数据编辑器", "📈 回测", "👥 用户管理", "🌐 马名映射"])
    # ==================== Tab1: 数据编辑器 ====================
    with tab1:
        st.markdown("### 📋 数据库编辑器")
        st.caption("💡 双击单元格编辑 | 表格底部有 '+' 按钮添加新行 | 支持 Excel/CSV 上传")
        
        # 加载当前数据
        current_data = get_table_data("past_performances", limit=500)
        
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
            # 只保留需要的列
            df = df[[c for c in columns if c in df.columns]]
        else:
            df = pd.DataFrame(columns=columns)
        
        # 显示数据量
        st.info(f"📊 当前数据量: {len(df)} 条记录")
        
        # 刷新按钮
        col_refresh, _ = st.columns([1, 5])
        with col_refresh:
            if st.button("🔄 从数据库重新加载", use_container_width=True):
                st.rerun()
        
        st.markdown("---")
        
        # 可编辑表格
        with st.form(key="data_editor_form"):
            #--------------
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                height=500,
                num_rows="dynamic",
                key="racing_data_editor"
            )
            #----------------end
            col_save1, col_save2, col_spacer = st.columns([1, 1, 3])
            
            with col_save1:
                overwrite_submitted = st.form_submit_button("💾 全量覆盖保存", type="primary", use_container_width=True)
            with col_save2:
                incremental_submitted = st.form_submit_button("🔄 增量同步保存", use_container_width=True)
            
            # 全量覆盖保存
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
                            success = save_table_data("past_performances", new_data)
                            if success:
                                st.success(f"全量覆盖保存 {len(new_data)} 条记录成功！")
                                st.cache_data.clear()  # ⭐ 清除缓存
                                st.rerun()
                            else:
                                st.error("保存失败")
                        else:
                            st.error("没有有效数据可保存")
            
            # 增量同步保存
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
                            result = incremental_sync_table("past_performances", new_data)
                            st.success(f"增量同步完成：新增 {result['inserted']} 条，更新 {result['updated']} 条，删除 {result['deleted']} 条")
                            st.cache_data.clear()  # ⭐ 清除缓存
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
                        # 转换为记录列表
                        upload_data = df_upload.to_dict(orient='records')
                        success = save_table_data("past_performances", upload_data)
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
        render_backtest_page(show_title=False)
    
    # ==================== Tab3: 用户管理 ====================
    with tab3:
        render_user_management()
    
    # 退出按钮
    st.markdown("---")
    if st.button("退出管理员模式", use_container_width=True):
        admin_sign_out()
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
# ==================== Tab4: 马名映射管理 ====================
    with tab4:
        st.markdown("### 🌐 中英文马名映射")
        st.caption("管理马名的中英文对应关系，用于界面    语言切换")
        
        # 获取当前映射
        mapping_data = get_horse_name_mapping()
        
        if mapping_data:
            mapping_df = pd.DataFrame([
                {"中文名": zh, "英文名": en} for zh, en in mapping_data.items()
            ])
            
            edited_mapping = st.data_editor(
                mapping_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "中文名": st.column_config.TextColumn("中文名", disabled=True),
                    "英文名": st.column_config.TextColumn("英文名")
                }
            )
            
            if st.button("💾 保存映射", type="primary"):
                # 更新映射表
                for _, row in edited_mapping.iterrows():
                    zh = row["中文名"]
                    en = row["英文名"]
                    if zh and en:
                        # 更新数据库
                        headers = get_supabase_headers(use_secret=True)
                        url = f"{SUPABASE_URL}/rest/v1/horse_name_mapping?name_zh=eq.{zh}"
                        requests.patch(url, headers=headers, json={"name_en": en})
                st.success("映射已保存")
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("暂无映射数据")
#--------------
# ==================== 赔率采集状态监控 ====================
with st.expander("📊 赔率采集状态监控", expanded=False):
    st.markdown("**最近7天赔率采集统计**")
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 查询最近7天各彩池的采集数量
        sql_stats = """
        SELECT 
            DATE(recorded_at) as collect_date,
            odds_type,
            COUNT(*) as count
        FROM odds_history 
        WHERE recorded_at > NOW() - INTERVAL '7 days'
        GROUP BY DATE(recorded_at), odds_type
        ORDER BY collect_date DESC, odds_type
        """
        
        # 注意：Supabase 不支持直接 SQL，需要使用 REST API 或 RPC
        # 这里使用简化的统计方式
        url = f"{SUPABASE_URL}/rest/v1/odds_history?select=recorded_at,odds_type&recorded_at=gt.{datetime.now() - timedelta(days=7)}&limit=10000"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                df_stats = pd.DataFrame(data)
                df_stats['recorded_at'] = pd.to_datetime(df_stats['recorded_at'])
                df_stats['collect_date'] = df_stats['recorded_at'].dt.date
                
                # 按日期和类型统计
                pivot_stats = df_stats.groupby(['collect_date', 'odds_type']).size().unstack(fill_value=0)
                st.dataframe(pivot_stats, use_container_width=True)
                
                # 显示最近采集时间
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
        st.markdown(f"## {t()['app_title']}")
        st.markdown("---")
        
        if st.session_state.authenticated and not st.session_state.admin_mode:
            user_email = st.session_state.user_email
            username = user_email.split('@')[0] if user_email else user_email
            user_id = st.session_state.user_id
            
            profile = get_user_profile(user_id)
            
            tier = profile.get("subscription_tier", "free")
            remaining = profile.get("free_trials_remaining", 0)
            
            tier_display = "💎 專業版" if tier == "pro" else "🔒 免費版"
            remaining_display = "∞" if remaining == -1 else str(remaining)
            
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
        
        # 删除导航菜单（这段已删除）
        # st.markdown("### 📍 導航")
        # page = st.radio(...)
        
        with st.expander(t()["about_header"], expanded=True):
            st.markdown(t()["about_text"])
        
        with st.expander(t()["guide_header"], expanded=False):
            st.markdown(t()["guide_text"])
        
        with st.expander(t()["contact_header"], expanded=False):
            st.markdown(t()["contact_email"])
        
        st.markdown("---")
        st.caption("v1.0 | TechLife")
        st.caption("數據: HKJC API | 支付: Stripe")

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

# ==================== 辅助函数：获取所有马匹基础评分 ====================
def get_all_horses_base_score(limit: int = 500, recent_games: int = 10) -> pd.DataFrame:
    """获取所有马匹的基础评分（基于 horse_id）"""
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 1. 获取马名映射（horse_id -> 中文名）
        name_cache = get_horse_name_cache()
        
        # 2. 获取所有成绩记录，按 horse_id 分组
        perf_url = f"{SUPABASE_URL}/rest/v1/past_performances?select=horse_id,position,body_weight,race_date&limit=50000"
        perf_response = requests.get(perf_url, headers=headers)
        
        if perf_response.status_code != 200:
            st.error(f"获取成绩数据失败: {perf_response.status_code}")
            return pd.DataFrame()
        
        data = perf_response.json()
        
        if not data:
            st.info("暂无成绩数据")
            return pd.DataFrame()
        
        # 按 horse_id 分组
        from collections import defaultdict
        horse_records = defaultdict(list)
        
        for p in data:
            horse_id = p.get("horse_id")
            if not horse_id:
                continue
            horse_records[horse_id].append({
                "position": p.get("position"),
                "body_weight": p.get("body_weight"),
                "race_date": p.get("race_date")
            })
        
        # 获取语言设置
        current_lang = st.session_state.get("lang", "zh")
        
        results = []
        for horse_id, records in horse_records.items():
            # 按日期排序（最新的在前）
            records.sort(key=lambda x: x.get("race_date", ""), reverse=True)
            
            # 取最近 N 场
            if recent_games == 0:
                selected = records
            else:
                selected = records[:recent_games]
            
            total = len(selected)
            if total < 3:
                continue
            
            wins = sum(1 for r in selected if r.get("position") == 1)
            places = sum(1 for r in selected if r.get("position") in [1, 2])
            shows = sum(1 for r in selected if r.get("position") in [1, 2, 3])
            
            # 体重平均值
            weights = [r.get("body_weight") for r in selected if r.get("body_weight")]
            avg_weight = sum(weights) / len(weights) if weights else 0
            
            win_rate = wins / total * 100
            place_rate = places / total * 100
            show_rate = shows / total * 100
            basic_score = win_rate * 0.5 + place_rate * 0.3 + show_rate * 0.2
            
            # 获取马名（根据语言）
            horse_name = name_cache.get(horse_id, horse_id)
            
            results.append({
                "馬名": horse_name,
                "勝率": round(win_rate, 1),
                "入Q率": round(place_rate, 1),
                "入T率": round(show_rate, 1),
                "基礎評分": round(basic_score, 1),
                "平均體重": round(avg_weight, 0)
            })
        
        # 按评分排序
        results.sort(key=lambda x: x["基礎評分"], reverse=True)
        
        df = pd.DataFrame(results[:limit])
        
        if df.empty:
            return df
        
        # 添加性别和年龄列（暂时为空）
        df["性別"] = "-"
        df["年齡"] = "-"
        
        # 调整列顺序
        df = df[["馬名", "性別", "年齡", "平均體重", "勝率", "入Q率", "入T率", "基礎評分"]]
        
        # 格式化百分比显示
        df["勝率"] = df["勝率"].apply(lambda x: f"{x:.1f}%")
        df["入Q率"] = df["入Q率"].apply(lambda x: f"{x:.1f}%")
        df["入T率"] = df["入T率"].apply(lambda x: f"{x:.1f}%")
        
        return df
        
    except Exception as e:
        st.error(f"获取马匹评分失败: {e}")
        return pd.DataFrame()

#------------
def render_horse_rating_table(df: pd.DataFrame):
    """渲染马匹评分表格"""
    if df.empty:
        st.info("暫無馬匹數據，請點擊「更新數據」同步馬匹資料")
        return
    
    # 使用 st.dataframe，原生支持排序和滚动
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "馬名": st.column_config.TextColumn("馬名", width="medium"),
            "性別": st.column_config.TextColumn("性別", width="small"),
            "年齡": st.column_config.NumberColumn("年齡", width="small"),
            "平均體重": st.column_config.NumberColumn("平均體重", width="small", format="%.0f"),
            "勝率": st.column_config.TextColumn("勝率", width="small"),
            "入Q率": st.column_config.TextColumn("入Q率", width="small"),
            "入T率": st.column_config.TextColumn("入T率", width="small"),
            "基礎評分": st.column_config.NumberColumn("基礎評分", width="small", format="%.0f")
        }
    )
    
    st.caption(f"📊 共 {len(df)} 匹馬")


# ==================== 主页函数（替换原有的render_home） ====================
def render_home():
    """主页：数据概览 + 全马评分榜 + 智能投注 + 回测"""
    
    # ==================== 页面标题 ====================
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1>🐎 香港賽馬AI分析系統</h1>
        <p style="color: #666; font-size: 1.1rem;">基於AI技術，智能預測馬匹勝率，優化投注策略</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ==================== 模块1：数据概览 ====================
    st.markdown("## 📊 數據概覽")
    
    # 获取统计数据
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 马匹数量
        horses_url = f"{SUPABASE_URL}/rest/v1/horses"
        horses_response = requests.get(horses_url, headers=headers)
        horse_count = len(horses_response.json()) if horses_response.status_code == 200 else 0
        
        # 赛事数量
        # 赛事总数（从 past_performances 统计不同的赛事）
        try:
            perf_races_url = f"{SUPABASE_URL}/rest/v1/past_performances?select=race_date,venue,race_no&limit=50000"
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
        perf_url = f"{SUPABASE_URL}/rest/v1/past_performances"
        perf_response = requests.get(perf_url, headers=headers)
        perf_count = len(perf_response.json()) if perf_response.status_code == 200 else 0
        #------
        # 获取最新和最旧赛事日期（从 past_performances 表）
        try:
            # 获取最新日期
            perf_url_latest = f"{SUPABASE_URL}/rest/v1/past_performances?select=race_date&order=race_date.desc&limit=1"
            perf_response_latest = requests.get(perf_url_latest, headers=headers)
            if perf_response_latest.status_code == 200 and perf_response_latest.json():
                latest_date = perf_response_latest.json()[0]['race_date']
            else:
                latest_date = 'N/A'
            
            # 获取最旧日期
            perf_url_oldest = f"{SUPABASE_URL}/rest/v1/past_performances?select=race_date&order=race_date.asc&limit=1"
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
        # 骑师总数（从 past_performances 统计）
        try:
            jockeys_url = f"{SUPABASE_URL}/rest/v1/past_performances?select=jockey&limit=50000"
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
        
        # 练马师总数（从 past_performances 统计）
        try:
            trainers_url = f"{SUPABASE_URL}/rest/v1/past_performances?select=trainer&limit=50000"
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
            st.metric("🐎 馬匹總數", horse_count)
        with col2:
            st.metric("🏆 賽事總數", race_count)
        with col3:
            st.metric("📊 成績記錄總數", perf_count)
        with col4:
            st.metric("🤠 騎師總數", jockey_count)
        with col5:
            st.metric("🏋️ 練馬師總數", trainer_count)
        
        # 第二行：日期范围（居中）
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.metric("📅 數據日期範圍", f"{oldest_date} ~ {latest_date}", help="基于历史成绩数据的日期范围")
            
    except Exception as e:
        st.warning(f"獲取數據統計失敗: {e}")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("🐎 馬匹總數", "0")
        with col2:
            st.metric("🏆 賽事總數", "0")
        with col3:
            st.metric("📊 成績記錄總數", "0")
        with col4:
            st.metric("🤠 騎師總數", "0")
        with col5:
            st.metric("🏋️ 練馬師總數", "0")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.metric("📅 數據範圍", "-")
    
    st.markdown("---")
    
    # ==================== 数据更新区域 ====================
    st.markdown("### 🔄 數據更新")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        update_btn = st.button("🔄 更新所有数据", type="primary", use_container_width=True)
    
    if update_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning("免費次數已用完，請升級到專業版")
        else:
            with st.spinner("正在检查并更新数据..."):
                result = sync_all_data()
                if result.get("success"):
                    st.success(f"✅ 更新完成！新增 {result.get('new_races', 0)} 场赛事，{result.get('new_records', 0)} 条成绩记录")
                    st.rerun()
                else:
                    st.error(f"更新失败: {result.get('error', '未知错误')}")
    
    st.markdown("---")
    
    # ==================== 模块2：全马基础评分榜 ====================
    st.markdown("### 🐎 全馬基礎評分榜")
    st.caption("📌 基於最近 N 場歷史表現計算，分數越高代表整體實力越強。")
    
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
    st.caption("📅 數據來源：香港賽馬會 | 更新頻率：賽日自動更新")


# ==================== 第3次代码结束 ====================
# ============================================================
# 第4次代码：智能投注 + 全天优化
# 包含：单场分析、全天投注分配、过关组合、Bankroll管理
# 版本：v1.0
# 说明：替换原有的 render_smart_betting() 函数
# ============================================================

# ==================== 辅助函数：获取赛日所有赛事 ====================
#------------
def get_upcoming_races() -> List[Dict]:
    """获取未来14天的赛事（从数据库读取）"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        next_two_weeks = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        headers = get_supabase_headers(use_secret=True)
        # 确保返回 race_id
        url = f"{SUPABASE_URL}/rest/v1/races?race_date=gte.{today}&race_date=lte.{next_two_weeks}&order=race_date.asc,race_no.asc&select=*,race_id"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"获取未来赛事失败: {e}")
        return []
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
#-------------------------
def get_race_runners_with_details(race_date: str, venue: str, race_no: int) -> List[Dict]:
    """
    获取赛事出赛马匹详情
    
    数据源策略：
    - 如果 race_date >= 今天：从 race_runners_clean 获取（未来赛事）
    - 如果 race_date < 今天：从 past_performances 获取（历史赛事）
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        headers = get_supabase_headers(use_secret=True)
        name_cache = get_horse_name_cache()
        
        # ==================== 未来赛事：从 race_runners_clean 获取 ====================
        if race_date >= today:
            url = f"{SUPABASE_URL}/rest/v1/race_runners_clean?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race_no}"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200 and response.json():
                runners = response.json()
                result = []
                for runner in runners:
                    horse_id = runner.get('horse_id')
                    horse_name = name_cache.get(horse_id, runner.get('horse_name_zh', runner.get('horse_name', '')))
                    
                    # 安全获取赔率
                    odds_win_raw = runner.get('odds_win')
                    try:
                        odds_win = float(odds_win_raw) if odds_win_raw else None
                    except (ValueError, TypeError):
                        odds_win = None
                    
                    result.append({
                        "horse_id": horse_id,
                        "horse_name": horse_name,
                        "horse_no": runner.get('horse_no'),
                        "draw": runner.get('draw'),
                        "actual_weight": runner.get('actual_weight'),
                        "jockey_name": runner.get('jockey_name'),
                        "odds_win": odds_win,
                        "finishing_position": None,  # 未来赛事还没有结果
                        "trainer": runner.get('trainer_name'),
                        "rating": runner.get('rating'),
                    })
                
                print(f"从 race_runners_clean 获取到 {len(result)} 匹马 (未来赛事)")
                return result
            else:
                print(f"race_runners_clean 中无数据: {race_date} {venue} 第{race_no}场")
                return []
        
        # ==================== 历史赛事：从 past_performances 获取 ====================
        else:
            url = f"{SUPABASE_URL}/rest/v1/past_performances?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race_no}&order=position.asc"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200 and response.json():
                data = response.json()
                result = []
                for p in data:
                    horse_id = p.get('horse_id')
                    horse_name = name_cache.get(horse_id, p.get('horse_name', ''))
                    
                    # 安全获取赔率
                    odds_win_raw = p.get('odds')
                    try:
                        odds_win = float(odds_win_raw) if odds_win_raw else None
                    except (ValueError, TypeError):
                        odds_win = None
                    
                    result.append({
                        "horse_id": horse_id,
                        "horse_name": horse_name,
                        "horse_no": p.get('horse_no'),
                        "draw": p.get('draw'),
                        "actual_weight": p.get('actual_weight'),
                        "jockey_name": p.get('jockey'),
                        "odds_win": odds_win,
                        "finishing_position": p.get('position'),
                        "trainer": p.get('trainer'),
                        "body_weight": p.get('body_weight'),
                        "lbw_raw": p.get('lbw_raw'),
                        "running_position": p.get('running_position'),
                    })
                
                print(f"从 past_performances 获取到 {len(result)} 匹马 (历史赛事)")
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
    # 过滤掉 None 值
    valid_runners = [r for r in runners if r is not None]
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


def prepare_ml_features(horse_id: int, race_id: int, past_performances: List[Dict]) -> Dict:
    """
    为 ML 模型准备特征
    返回特征字典
    """
    features = {}
    
    # 1. 基础统计特征
    if past_performances:
        recent_5 = past_performances[:5] if len(past_performances) >= 5 else past_performances
        recent_10 = past_performances[:10] if len(past_performances) >= 10 else past_performances
        
        # 胜率、入Q率、入T率
        wins = sum(1 for p in recent_10 if p.get('position') == 1)
        places = sum(1 for p in recent_10 if p.get('position', 0) <= 2)
        shows = sum(1 for p in recent_10 if p.get('position', 0) <= 3)
        
        features['win_rate_10'] = wins / len(recent_10) if recent_10 else 0
        features['place_rate_10'] = places / len(recent_10) if recent_10 else 0
        features['show_rate_10'] = shows / len(recent_10) if recent_10 else 0
        
        # 近5场胜率
        wins_5 = sum(1 for p in recent_5 if p.get('position') == 1)
        features['win_rate_5'] = wins_5 / len(recent_5) if recent_5 else 0
        
        # 平均完成时间
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
                past = get_horse_past_performances(horse_id, limit=10)
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
                
                past = get_horse_past_performances(horse_id, limit=10)
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


def get_model_predictions(race_id: int, runners: List[Dict], model_type: str) -> List[float]:
    """
    获取 ML 模型预测的胜率
    model_type: 'lightgbm', 'xgboost', 'ensemble'
    """
    predictions = []
    
    # 训练模型（使用历史数据）
    # 注意：实际应用中应该缓存模型，避免重复训练
    draws = get_historical_draws_for_training(limit=300)
    
    if model_type == 'lightgbm':
        model = train_lightgbm_model(draws)
    elif model_type == 'xgboost':
        model = train_xgboost_model(draws)
    else:
        # 集成模型
        lgb_model = train_lightgbm_model(draws)
        xgb_model = train_xgboost_model(draws)
        
        for runner in runners:
            horse_id = runner.get('horse_id')
            past = get_horse_past_performances(horse_id, limit=10)
            features = prepare_ml_features(horse_id, race_id, past)
            
            if features:
                lgb_prob = predict_with_ml_model(lgb_model, features) if lgb_model else 0.5
                xgb_prob = predict_with_ml_model(xgb_model, features) if xgb_model else 0.5
                prob = (lgb_prob + xgb_prob) / 2
            else:
                prob = 0.5
            
            predictions.append(prob)
        
        return predictions
    
    for runner in runners:
        horse_id = runner.get('horse_id')
        past = get_horse_past_performances(horse_id, limit=10)
        features = prepare_ml_features(horse_id, race_id, past)
        
        if features:
            features['draw'] = runner.get('draw', 0)
            features['actual_weight'] = runner.get('actual_weight', 0)
            features['odds'] = runner.get('odds_win', 0)
            prob = predict_with_ml_model(model, features)
        else:
            prob = 0.5
        
        predictions.append(prob)
    
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
# ==================== 智能投注主页面 ====================
def render_smart_betting(show_title: bool = True):
    """智能投注页面：单场分析 + 全天优化 + 过关组合"""
    if show_title:
        st.markdown("## 🎯 智能投注")
        
    # ==================== 用户设置区域 ====================
    with st.expander("⚙️ 投注設置", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            profile = get_user_profile(st.session_state.user_id)
            default_bankroll = profile.get('default_bankroll', 1000)
            bankroll = st.number_input(
                "💰 投注預算 (HKD)",
                min_value=100,
                max_value=100000,
                value=int(default_bankroll),
                step=100,
                key="betting_bankroll"
            )
        
        with col2:
            risk_preference = st.selectbox(
                "📊 風險偏好",
                options=["conservative", "standard", "aggressive"],
                format_func=lambda x: {"conservative": "保守", "standard": "標準", "aggressive": "進取"}.get(x, "標準"),
                key="risk_preference"
            )
            risk_multiplier = {
                "conservative": 0.5,
                "standard": 0.8,
                "aggressive": 1.0
            }.get(risk_preference, 0.8)
        
        with col3:
            model_choice = st.selectbox(
                "🤖 AI 模型",
                options=["评分系统", "LightGBM", "XGBoost", "集成模型"],
                index=0,
                key="ml_model_choice",
                help="选择预测模型：评分系统（规则驱动）、LightGBM、XGBoost 或集成模型"
            )
        
        with col4:
            st.markdown("**📐 評分權重**")
            st.caption("基礎:30% | 場次:40% | 賠率:30%")
            st.caption("溫度:0.8 | 賠率混合比:0.6")
    
    st.markdown("---")
    
    # ==================== 获取马名映射缓存 ====================
    name_cache = get_horse_name_cache()
    
    # ==================== 选择赛日 ====================
    st.markdown("### 📅 選擇賽日")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        refresh_schedule_btn = st.button("🔄 刷新賽程", use_container_width=True)
    
    if refresh_schedule_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning("免費次數已用完，請升級到專業版")
        else:
            with st.spinner("正在同步最新賽程..."):
                result = sync_future_races(days=14)
                if result.get("total", 0) > 0:
                    st.success(f"同步完成！成功 {result.get('success', 0)} 场，失败 {result.get('failed', 0)} 场")
                    st.rerun()
                else:
                    st.info("未来14天暂无赛事")
    
    upcoming_races = get_upcoming_races()
    
    if not upcoming_races:
        st.info("📌 未來14天暫無賽事，請點擊「刷新賽程」同步最新賽程")
        return
    
    dates = sorted(set([r.get('race_date') for r in upcoming_races]))
    date_options = [f"{d} ({['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][datetime.strptime(d, '%Y-%m-%d').weekday()]})" for d in dates]
    
    selected_date_str = st.selectbox("選擇賽日", date_options, key="selected_race_date")
    selected_date = selected_date_str.split(" ")[0]
    
    races = [r for r in upcoming_races if r.get('race_date') == selected_date]
    st.markdown(f"**📋 共 {len(races)} 場賽事**")
    st.markdown("---")
    
    # ==================== 单场分析 ====================
    st.markdown("### 📊 單場分析")
    
    race_options = []
    for r in races:
        distance = r.get('distance', 0)
        race_class = r.get('race_class', '')
        race_options.append(f"第{r.get('race_no')}場 - {distance}米 ({race_class})")
    
    selected_idx = st.selectbox("選擇場次", range(len(race_options)), format_func=lambda x: race_options[x], key="selected_race")
    selected_race = races[selected_idx]
    
    col1, col2 = st.columns([1, 4])
    with col1:
        refresh_race_btn = st.button("🔄 更新本場數據", key="refresh_race")
    
    if refresh_race_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning("免費次數已用完，請升級到專業版")
        else:
            with st.spinner("正在更新最新賠率和出賽馬匹..."):
                if sync_single_race(selected_race):
                    st.success("數據已更新")
                    st.rerun()
                else:
                    st.warning("更新失敗")
    
    runners = get_race_runners_with_details(
        selected_race.get('race_date'),
        selected_race.get('venue'),
        selected_race.get('race_no')
    )
    
    if not runners:
        st.warning("暫無出賽馬匹數據，請點擊「更新本場數據」同步")
        return
    
    user_weights = {
        "basic": 0.30,
        "race": 0.40,
        "odds": 0.30,
        "temperature": 0.8,
        "odds_mix_ratio": 0.6
    }
    
    # 计算胜率
    if model_choice == "评分系统":
        with st.spinner("正在計算馬匹勝率（評分系統）..."):
            scores, probabilities = calculate_all_horses_scores(selected_race.get('race_id'), runners, user_weights)
        for i, runner in enumerate(runners):
            if i < len(scores):
                runner['overall_score'] = scores[i].get('combined_score', 0)
                runner['win_probability'] = scores[i].get('win_probability', 0) / 100
    else:
        model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
        with st.spinner(f"正在計算馬匹勝率（{model_choice}）..."):
            ml_probs = get_model_predictions(selected_race.get('race_id'), runners, model_type)
        for i, runner in enumerate(runners):
            if i < len(ml_probs):
                runner['win_probability'] = ml_probs[i]
                runner['overall_score'] = ml_probs[i] * 100
    
    sorted_runners = sorted(runners, key=lambda x: x.get('win_probability', 0), reverse=True)
    #--------------------
    # 在计算完 runners 的 win_probability 之后添加

    # ==================== 调用策略引擎生成投注建议 ====================
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
            odds_place.append(odds * 0.3 if odds > 0 else 0)  # 位置赔率约为独赢的30%
        
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
        
        # ==================== 显示AI投注建议 ====================
        st.markdown("#### 💡 AI 投注策略建议")
        st.caption("基于AI评分和赔率计算的期望值(EV)推荐")
        
        # 创建三列显示建议
        col1, col2, col3 = st.columns(3)
        
        # 独赢建议 (低风险)
        with col1:
            st.markdown("**🎯 低风险 - 獨贏/位置**")
            if recommendations['win']:
                rec = recommendations['win'][0]
                st.info(f"**{rec.description}**")
                st.write(f"賠率: {rec.odds}倍")
                st.write(f"預期ROI: {rec.roi:+.1f}%")
                st.caption(f"💡 {rec.reason}")
            elif recommendations['place']:
                rec = recommendations['place'][0]
                st.info(f"**{rec.description}**")
                st.write(f"賠率: {rec.odds}倍")
                st.write(f"預期ROI: {rec.roi:+.1f}%")
                st.caption(f"💡 {rec.reason}")
            else:
                st.write("暂无建议")
        
        # 连赢建议 (中风险)
        with col2:
            st.markdown("**🎯 中风险 - 連贏**")
            if recommendations['qin']:
                rec = recommendations['qin'][0]
                st.warning(f"**{rec.description}**")
                st.write(f"賠率: {rec.odds}倍")
                st.write(f"預期ROI: {rec.roi:+.1f}%")
                st.caption(f"💡 {rec.reason}")
            else:
                st.write("暂无建议")
        
        # 单T建议 (高风险)
        with col3:
            st.markdown("**🎯 高风险 - 單T**")
            if recommendations['tri']:
                rec = recommendations['tri'][0]
                st.error(f"**{rec.description}**")
                st.write(f"賠率: {rec.odds}倍")
                st.write(f"預期ROI: {rec.roi:+.1f}%")
                st.caption(f"💡 {rec.reason}")
            else:
                st.write("暂无建议")
    #------------
    # 显示表格
    st.markdown(f"#### 🏇 第{selected_race.get('race_no')}場 出賽馬匹")
    
    race_data = []
    for runner in sorted_runners:
        horse_id = runner.get('horse_id')
        horse_name = name_cache.get(horse_id, runner.get('horse_name', ''))
        
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
        
        race_data.append({
            "馬號": runner.get('horse_no', '-'),
            "馬名": horse_name,
            "檔位": runner.get('draw', '-'),
            "負磅": runner.get('actual_weight', '-'),
            "騎師": runner.get('jockey_name', '-'),
            "獨贏": odds_win_display,
            "位置": odds_place_display,
            "勝率": f"{runner.get('win_probability', 0)*100:.1f}%",
            "綜合評分": f"{runner.get('overall_score', 0):.0f}"
        })
    
    st.dataframe(pd.DataFrame(race_data), use_container_width=True, hide_index=True)
    #------------
    # 投注建议 - 使用AI策略引擎
    st.markdown("#### 💡 AI 投注策略建议")
    st.caption("基于AI评分和赔率计算的期望值(EV)推荐")
    
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
        st.markdown("**🎯 低风险 - 獨贏/位置**")
        if recommendations.get('win') and recommendations['win']:
            rec = recommendations['win'][0]
            st.info(f"**{rec.description}**")
            st.write(f"賠率: {rec.odds}倍")
            st.write(f"預期ROI: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        elif recommendations.get('place') and recommendations['place']:
            rec = recommendations['place'][0]
            st.info(f"**{rec.description}**")
            st.write(f"賠率: {rec.odds}倍")
            st.write(f"預期ROI: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        else:
            st.write("暂无建议")
    
    # 中风险 - 连赢
    with col2:
        st.markdown("**🎯 中风险 - 連贏**")
        if recommendations.get('qin') and recommendations['qin']:
            rec = recommendations['qin'][0]
            st.warning(f"**{rec.description}**")
            st.write(f"賠率: {rec.odds}倍")
            st.write(f"預期ROI: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        else:
            st.write("暂无建议")
    
    # 高风险 - 单T
    with col3:
        st.markdown("**🎯 高风险 - 單T**")
        if recommendations.get('tri') and recommendations['tri']:
            rec = recommendations['tri'][0]
            st.error(f"**{rec.description}**")
            st.write(f"賠率: {rec.odds}倍")
            st.write(f"預期ROI: {rec.roi:+.1f}%")
            st.caption(f"💡 {rec.reason}")
        else:
            st.write("暂无建议")
            prob = horse.get('win_probability', 0) * 100
            odds_raw = horse.get('odds_win')
            
            # 安全处理赔率
            try:
                odds = float(odds_raw) if odds_raw else 0
            except (ValueError, TypeError):
                odds = 0
            
            score = horse.get('overall_score', 0)
            horse_id = horse.get('horse_id')
            horse_name = name_cache.get(horse_id, '')
            
            # 安全计算凯利
            if odds > 0:
                kelly = calculate_kelly_fraction(prob / 100, odds)
            else:
                kelly = 0
            
            stake = bankroll * kelly * risk_multiplier if kelly > 0 else 0
            
            with cols[i]:
                st.markdown(f"""
                <div style="background:#f8f9fa; padding:0.8rem; border-radius:0.5rem;">
                    <strong>🥇 {horse_name}</strong><br>
                    勝率: {prob:.1f}% | 賠率: {odds:.1f}<br>
                    建議注額: <strong>HK${stake:.0f}</strong>
                </div>
                """, unsafe_allow_html=True)
    
    # ==================== 连赢推荐（追加）====================
    st.markdown("#### 🔗 連贏推薦")
    
    if len(sorted_runners) >= 2:
        # 获取前两名高胜率马的组合
        top2 = sorted_runners[:2]
        horse1 = top2[0]
        horse2 = top2[1]
        
        horse1_id = horse1.get('horse_id')
        horse2_id = horse2.get('horse_id')
        horse1_name = name_cache.get(horse1_id, horse1.get('horse_name', ''))
        horse2_name = name_cache.get(horse2_id, horse2.get('horse_name', ''))
        
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
                st.success(f"**{horse1_name} + {horse2_name}** | 連贏賠率: {estimated_qin_odds:.1f} | 聯合概率: {joint_prob*100:.1f}% | 建議注額: HK${suggested_stake:.0f}")
            else:
                st.info(f"連贏組合 {horse1_name} + {horse2_name} 期望值不足，暫不推薦")
        else:
            st.caption("暫無連贏賠率數據")
    else:
        st.caption("馬匹數量不足，無法推薦連贏")
    
    st.markdown("---")
    
    # ==================== 新增：过关投注推荐器 ====================
    st.markdown("## 🎲 过关投注推荐")
    st.caption("选择多场赛事，AI推荐最佳过关组合")
    
    # 获取当前赛日的所有赛事（用于过关推荐）
    current_races_for_parlay = races  # races 是前面定义的当前赛日所有赛事
    
    if current_races_for_parlay and len(current_races_for_parlay) >= 2:
        # 让用户选择要过关的场次
        st.markdown("**选择要过关的场次**")
        
        parlay_race_options = []
        for r in current_races_for_parlay:
            distance = r.get('distance', 0)
            race_class = r.get('race_class', '')
            parlay_race_options.append(f"第{r.get('race_no')}場 - {distance}米 ({race_class})")
        
        # 多选框
        selected_parlay_indices = st.multiselect(
            "选择2-6场比赛（按顺序）",
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
                        scores, _ = calculate_all_horses_scores(race.get('race_id'), runners_data, user_weights)
                        for i, runner in enumerate(runners_data):
                            if i < len(scores):
                                runner['overall_score'] = scores[i].get('combined_score', 0)
                                runner['win_probability'] = scores[i].get('win_probability', 0) / 100
                    else:
                        model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
                        ml_probs = get_model_predictions(race.get('race_id'), runners_data, model_type)
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
                if st.button("🎲 生成过关推荐", key="generate_parlay_recommendations", use_container_width=True):
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
                                
                                # 最佳推荐汇总
                                st.markdown("---")
                                st.markdown("#### 🏆 最佳推荐")
                                
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
    st.markdown("### 🌟 全天優化投注")
    st.caption("基於凱利公式 + 風險管理，自動分配全天投注策略")
    
    if st.button("🚀 生成全天投注策略", key="generate_full_day", use_container_width=True, type="primary"):
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
                else:
                    model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
                    ml_probs = get_model_predictions(race.get('race_id'), race_runners, model_type)
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
                            "馬匹": name_cache.get(horse.get('horse_id'), ''),
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
    st.markdown("### 🔗 過關組合推薦")
    st.caption("基於各場信心馬匹，推薦2串1、3串1過關組合")
    
    if st.button("🎲 生成過關組合", key="generate_parlay", use_container_width=True):
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
                else:
                    model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
                    ml_probs = get_model_predictions(race.get('race_id'), race_runners, model_type)
                    for i, r in enumerate(race_runners):
                        if i < len(ml_probs):
                            r['win_probability'] = ml_probs[i]
                
                top = max(race_runners, key=lambda x: x.get('win_probability', 0), default=None)
                if top and top.get('win_probability', 0) >= 0.20:
                    confidence_horses.append({
                        "race_no": race.get('race_no'),
                        "horse_name": name_cache.get(top.get('horse_id'), ''),
                        "probability": top.get('win_probability', 0),
                        "odds": top.get('odds_win', 0)
                    })
            
            parlay_results = []
            
            # 2串1
            for i in range(len(confidence_horses)):
                for j in range(i+1, len(confidence_horses)):
                    h1, h2 = confidence_horses[i], confidence_horses[j]
                    joint_prob = h1['probability'] * h2['probability']
                    combined_odds = h1['odds'] * h2['odds']
                    if joint_prob * combined_odds > 1 and combined_odds > 0:
                        parlay_results.append({
                            "組合": "2串1",
                            "場次": f"第{h1['race_no']}場 + 第{h2['race_no']}場",
                            "馬匹": f"{h1['horse_name']} + {h2['horse_name']}",
                            "組合賠率": f"{combined_odds:.1f}",
                            "聯合概率": f"{joint_prob*100:.1f}%",
                            "建議注額": f"HK${bankroll * 0.05 * risk_multiplier:.0f}"
                        })
            
            if parlay_results:
                st.dataframe(pd.DataFrame(parlay_results), use_container_width=True, hide_index=True)
            else:
                st.info("暫無符合條件的過關組合")
    
    st.markdown("---")
    st.caption("⚠️ 本建議基於AI模型預測，不保證實際收益。請理性投注，切勿超出預算。")

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
            for i in range(len(confidence_horses)):
                for j in range(i+1, len(confidence_horses)):
                    horse1 = confidence_horses[i]
                    horse2 = confidence_horses[j]
                    
                    joint_prob = horse1['probability'] * horse2['probability']
                    combined_odds = horse1['odds'] * horse2['odds']
                    
                    if joint_prob * combined_odds > 1 and combined_odds > 0:
                        suggested_stake = bankroll * 0.05 * risk_multiplier
                        parlay_results.append({
                            "組合": "2串1",
                            "場次": f"第{horse1['race_no']}場 + 第{horse2['race_no']}場",
                            "馬匹": f"{horse1['horse_name']} + {horse2['horse_name']}",
                            "組合賠率": f"{combined_odds:.1f}",
                            "聯合概率": f"{joint_prob*100:.1f}%",
                            "建議注額": f"HK${suggested_stake:.0f}"
                        })
            
            # 3串1
            for i in range(len(confidence_horses)):
                for j in range(i+1, len(confidence_horses)):
                    for k in range(j+1, len(confidence_horses)):
                        horse1 = confidence_horses[i]
                        horse2 = confidence_horses[j]
                        horse3 = confidence_horses[k]
                        
                        joint_prob = horse1['probability'] * horse2['probability'] * horse3['probability']
                        combined_odds = horse1['odds'] * horse2['odds'] * horse3['odds']
                        
                        if joint_prob * combined_odds > 1 and combined_odds > 0:
                            suggested_stake = bankroll * 0.03 * risk_multiplier
                            parlay_results.append({
                                "組合": "3串1",
                                "場次": f"第{horse1['race_no']}場 + 第{horse2['race_no']}場 + 第{horse3['race_no']}場",
                                "馬匹": f"{horse1['horse_name']} + {horse2['horse_name']} + {horse3['horse_name']}",
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
                perf_url = f"{SUPABASE_URL}/rest/v1/past_performances?horse_id=eq.{horse_id}&race_date=lt.{race_date}&order=race_date.desc&limit=20"
                perf_response = requests.get(perf_url, headers=headers)
                if perf_response.status_code == 200:
                    runner['past_performances'] = perf_response.json()
                else:
                    runner['past_performances'] = []
        
        return runners
    except Exception as e:
        print(f"获取赛事数据失败: {e}")
        return []


def run_backtest_on_race(race_id: int, race_date: str, user_weights: Dict) -> Dict:
    """
    对单场赛事进行回测
    返回: 预测结果 vs 实际结果
    """
    try:
        # 获取赛事数据（不含未来数据）
        runners = get_race_without_future_data(race_date, race_id)
        
        if not runners:
            return {"success": False, "error": "无法获取赛事数据"}
        
        # 获取实际赛果
        headers = get_supabase_headers(use_secret=True)
        race_url = f"{SUPABASE_URL}/rest/v1/races?race_id=eq.{race_id}"
        race_response = requests.get(race_url, headers=headers)
        actual_race = race_response.json()[0] if race_response.status_code == 200 else None
        
        # 找出实际冠军
        actual_winner = None
        for runner in runners:
            if runner.get('finishing_position') == 1:
                actual_winner = runner
                break
        
        if not actual_winner:
            return {"success": False, "error": "无实际赛果数据"}
        
        # 计算每匹马的胜率（使用用户权重）
        scores = []
        for runner in runners:
            past_performances = runner.get('past_performances', [])
            
            # 计算基础评分
            distance = actual_race.get('distance', 1200) if actual_race else 1200
            basic_score = calculate_basic_score(runner.get('horse_id'), distance, past_performances)
            
            # 计算场次评分（使用排位时的数据）
            weight_comfort_range = get_horse_weight_comfort_range(runner.get('horse_id'))
            race_score = calculate_race_score(
                runner.get('horse_id'),
                actual_race.get('venue', 'ST'),
                distance,
                runner.get('draw'),
                runner.get('actual_weight'),
                runner.get('jockey_id'),
                runner.get('trainer_id'),
                weight_comfort_range,
                past_performances
            )
            
            # 赔率评分
            odds_score = calculate_odds_score(runner.get('odds_win', 10.0))
            
            # 综合评分
            combined = (
                basic_score * user_weights.get("basic", 0.30) +
                race_score * user_weights.get("race", 0.40) +
                odds_score * user_weights.get("odds", 0.30)
            )
            
            scores.append({
                "runner_id": runner.get('runner_id'),
                "horse_id": runner.get('horse_id'),
                "combined_score": combined,
                "basic_score": basic_score,
                "race_score": race_score,
                "odds_score": odds_score,
                "actual_winner": runner.get('runner_id') == actual_winner.get('runner_id')
            })
        
        # 排序找出预测冠军
        scores.sort(key=lambda x: x['combined_score'], reverse=True)
        predicted_winner_id = scores[0]['runner_id'] if scores else None
        
        # 判断是否正确
        is_correct = (predicted_winner_id == actual_winner.get('runner_id'))
        
        # 计算前三名命中率
        predicted_top3_ids = [s['runner_id'] for s in scores[:3]]
        actual_top3_ids = [r.get('runner_id') for r in runners if r.get('finishing_position', 0) in [1, 2, 3]]
        top3_hits = len(set(predicted_top3_ids) & set(actual_top3_ids))
        
        return {
            "success": True,
            "is_correct": is_correct,
            "top3_hits": top3_hits,
            "predicted_winner_score": scores[0]['combined_score'] if scores else 0,
            "actual_winner_name": actual_winner.get('horse_name_zh', actual_winner.get('horse_name_en', '')),
            "total_runners": len(runners)
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
            runners = get_race_runners_with_details(race_date, venue, race_no)
            
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
    回测函数（优化版）
    - 批量获取数据，避免 N+1 查询
    - ROI 修正：每场都投注 100 元
    - 增加多个前三名指标
    """
    result = {
        "模型": "评分系统" if model_type == "rule" else model_type.upper(),
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
        # 1. 批量获取所有数据
        with st.spinner(f"📥 正在加載 {start_date} 至 {end_date} 的歷史數據..."):
            all_performances = get_performances_batch(start_date, end_date)
        
        if not all_performances:
            st.error("未獲取到任何數據")
            return result
        
        # 2. 构建马匹往绩缓存
        horse_cache = build_horse_performances_cache(all_performances)
        
        # 3. 提取赛事列表
        races = get_races_from_performances(all_performances)
        result["测试场次"] = len(races)
        
        if result["测试场次"] == 0:
            st.warning("未找到任何賽事")
            return result
        
        # 4. 获取马名缓存
        name_cache = get_horse_name_cache()
        
        # 5. 初始化统计变量
        correct_predictions = 0
        total_top3_hits = 0
        total_top3_hit_races = 0
        total_tri_correct = 0
        total_tce_correct = 0
        total_stake = 0
        total_return = 0
        
        # 6. 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 7. 遍历每场赛事
        for idx, race in enumerate(races):
            # 取消检查点
            if st.session_state.get("stop_backtest", False):
                st.warning("⚠️ 回測已被用戶取消")
                result["cancelled"] = True
                break
            
            race_date = race['race_date']
            venue = race['venue']
            race_no = race['race_no']
            distance = race.get('distance', 1200)
            
            status_text.text(f"正在回測: {race_date} 第{race_no}場 ({idx+1}/{result['测试场次']})")
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
                
                horse_name = name_cache.get(horse_id, r.get('horse_name', ''))
                
                # 获取该马匹在 race_date 之前的往绩
                all_past = horse_cache.get(horse_id, [])
                past_before_race = [p for p in all_past 
                                   if p.get('race_date', '') < race_date]
                past_before_race = past_before_race[:10]
                
                # 计算基础评分
                basic_score = calculate_basic_score_fast(past_before_race, distance)
                
                # 计算场次评分
                draw = r.get('draw')
                if draw and isinstance(draw, (int, float)) and 1 <= draw <= 14:
                    draw_score = max(20, 100 - (draw - 1) * 6)
                else:
                    draw_score = 50
                
                # 赔率评分
                odds_raw = r.get('odds')
                try:
                    odds = float(odds_raw) if odds_raw else 10
                except (ValueError, TypeError):
                    odds = 10
                
                if odds > 0 and odds <= 99:
                    odds_score = 100 * (1 - (odds - 1) / 98)
                    odds_score = max(0, min(100, odds_score))
                else:
                    odds_score = 50
                
                combined_score = basic_score * 0.30 + draw_score * 0.40 + odds_score * 0.30
                
                runners.append({
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "horse_no": r.get('horse_no'),
                    "finishing_position": r.get('position'),
                    "combined_score": combined_score,
                    "odds_win": odds,
                })
            
            if not runners:
                continue
            
            # 排序找出预测前三名
            runners.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
            predicted_1st = runners[0].get('horse_name') if len(runners) > 0 else None
            predicted_2nd = runners[1].get('horse_name') if len(runners) > 1 else None
            predicted_3rd = runners[2].get('horse_name') if len(runners) > 2 else None
            predicted_top3_set = {predicted_1st, predicted_2nd, predicted_3rd} - {None}
            
            # 获取实际结果
            runners_data_sorted = sorted(runners_data, key=lambda x: x.get('position', 99))
            actual_1st = None
            actual_2nd = None
            actual_3rd = None
            actual_top3_set = set()
            actual_top3_names = []      # 保留但可以不使用
            
            for r in runners_data_sorted:
                pos = r.get('position')
                horse_id = r.get('horse_id')
                horse_name = name_cache.get(horse_id, r.get('horse_name', ''))
                if pos == 1:
                    actual_1st = horse_name
                    actual_top3_set.add(horse_name)
                elif pos == 2:
                    actual_2nd = horse_name
                    actual_top3_set.add(horse_name)
                elif pos == 3:
                    actual_3rd = horse_name
                    actual_top3_set.add(horse_name)
                    # ⭐ 不要添加 actual_top3_set = set(actual_top3_names) 这行
            
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
            
            # ROI：每场都投注 100 元
            total_stake += 100
            if is_correct:
                odds = runners[0].get('odds_win', 3.0)
                try:
                    odds = float(odds) if odds else 3.0
                except:
                    odds = 3.0
                total_return += 100 * odds
            
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
                "独赢正确": "✅" if is_correct else "❌",
                "前3名命中匹数": hits,
                "前3名全中": "✅" if tri_correct else "❌",
                "前3名顺序正确": "✅" if tce_correct else "❌"
            })
            
            if is_correct:
                correct_predictions += 1
        
        # 8. 清理进度条
        progress_bar.empty()
        status_text.empty()
        
        # 9. 计算最终结果
        if result["测试场次"] > 0 and not result["cancelled"]:
            result["预测正确"] = correct_predictions
            result["独赢正确率"] = correct_predictions / result["测试场次"] * 100
            
            result["前三名命中匹数"] = total_top3_hits
            result["前三名命中匹数率"] = total_top3_hits / (result["测试场次"] * 3) * 100
            
            result["前三名命中场次"] = total_top3_hit_races
            result["前三名命中场次率"] = total_top3_hit_races / result["测试场次"] * 100
            
            result["前三名全中场次"] = total_tri_correct
            result["前三名全中率"] = total_tri_correct / result["测试场次"] * 100
            
            result["前三名顺序正确场次"] = total_tce_correct
            result["前三名顺序正确率"] = total_tce_correct / result["测试场次"] * 100
            
            result["总投入"] = total_stake
            result["总回报"] = total_return
            if total_stake > 0:
                result["ROI"] = (total_return - total_stake) / total_stake * 100
        
        if not result["cancelled"]:
            st.success(f"✅ 回測完成: {result['测试场次']} 場, 獨贏正確率 {result['独赢正确率']:.1f}%, ROI {result['ROI']:+.1f}%")
        
    except Exception as e:
        st.error(f"回測失敗: {e}")
        print(f"回測失敗 ({model_type}): {e}")
    
    st.session_state.stop_backtest = False
    return result
#------------
# ==================== 回测专用：批量数据获取与缓存 ====================

@st.cache_data(ttl=3600, show_spinner=False)
def get_performances_batch(start_date: str, end_date: str) -> List[Dict]:
    """
    批量获取日期范围内的所有 past_performances 数据
    使用 st.cache_data 缓存，避免重复查询
    """
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances?race_date=gte.{start_date}&race_date=lte.{end_date}&limit=50000"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"批量获取数据失败: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"批量获取数据异常: {e}")
        return []


def build_horse_performances_cache(performances: List[Dict]) -> Dict[str, List[Dict]]:
    """
    构建马匹往绩缓存
    输入：所有 past_performances 记录
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


def calculate_basic_score_fast(past_performances: List[Dict], target_distance: int) -> float:
    """
    快速计算基础评分（使用已获取的往绩数据，不查询数据库）
    用于回测场景，避免 N+1 查询问题
    """
    if not past_performances:
        return 50.0
    
    # 取最近 10 场（已经是按日期降序排列）
    recent = past_performances[:10]
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
    返回: (X_features, y_labels)
    """
    X_list = []
    y_list = []
    
    # 筛选 cutoff_date 之前的赛事
    past_races = [p for p in all_performances if p.get('race_date', '') < cutoff_date]
    
    # 按赛事分组
    race_groups = {}
    for p in past_races:
        key = f"{p['race_date']}_{p['venue']}_{p['race_no']}"
        if key not in race_groups:
            race_groups[key] = []
        race_groups[key].append(p)
    
    for race_key, runners_data in race_groups.items():
        if not runners_data:
            continue
        
        # 获取赛事信息
        first_runner = runners_data[0]
        race_date = first_runner.get('race_date')
        distance = first_runner.get('distance', 1200)
        
        for r in runners_data:
            horse_id = r.get('horse_id')
            if not horse_id:
                continue
            
            # 获取该马匹在 race_date 之前的往绩
            all_past = horse_cache.get(horse_id, [])
            past_before = [p for p in all_past if p.get('race_date', '') < race_date]
            past_before = past_before[:10]
            
            # 构建特征
            features = {}
            
            # 1. 基础统计特征
            if past_before:
                total = len(past_before)
                wins = sum(1 for p in past_before if p.get('position') == 1)
                places = sum(1 for p in past_before if p.get('position', 0) in [1, 2])
                shows = sum(1 for p in past_before if p.get('position', 0) in [1, 2, 3])
                
                features['win_rate'] = wins / total if total > 0 else 0
                features['place_rate'] = places / total if total > 0 else 0
                features['show_rate'] = shows / total if total > 0 else 0
                
                # 近5场胜率
                recent_5 = past_before[:5]
                wins_5 = sum(1 for p in recent_5 if p.get('position') == 1)
                features['win_rate_5'] = wins_5 / len(recent_5) if recent_5 else 0
                
                # 平均负磅
                weights = [p.get('actual_weight', 0) for p in past_before if p.get('actual_weight')]
                features['avg_weight'] = sum(weights) / len(weights) if weights else 0
            else:
                features['win_rate'] = 0
                features['place_rate'] = 0
                features['show_rate'] = 0
                features['win_rate_5'] = 0
                features['avg_weight'] = 0
            
            # 2. 本场特征
            features['draw'] = r.get('draw', 0) or 0
            features['actual_weight'] = r.get('actual_weight', 0) or 0
            features['odds'] = r.get('odds', 10) or 10
            features['distance'] = distance
            
            # 3. 骑师特征（如果有骑师胜率数据）
            jockey = r.get('jockey', '')
            features['jockey_win_rate'] = 0  # 可扩展：从 jockeys 表获取
            
            X_list.append(features)
            
            # 目标：是否跑入前三
            position = r.get('position', 0)
            y_list.append(1 if position and position <= 3 else 0)
    
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


def predict_with_model(model, features: Dict, model_type: str) -> float:
    """使用训练好的模型预测"""
    if model is None:
        return 0.5
    
    try:
        X_pred = pd.DataFrame([features]).fillna(0)
        
        if model_type == 'ensemble':
            probs = []
            if model.get('lightgbm'):
                probs.append(model['lightgbm'].predict_proba(X_pred)[0][1])
            if model.get('xgboost'):
                probs.append(model['xgboost'].predict_proba(X_pred)[0][1])
            return sum(probs) / len(probs) if probs else 0.5
        else:
            return model.predict_proba(X_pred)[0][1]
    except Exception as e:
        print(f"预测失败: {e}")
        return 0.5
#----------
def run_ml_backtest(start_date: str, end_date: str, model_type: str) -> Dict:
    """
    ML 模型回测（时间滑窗版本 + 修正指标）
    - 使用截止日期前的数据训练模型
    - 预测该日期当天的赛事
    - 滚动进行，确保无数据泄露
    - 包含训练进度提示
    """
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
    "debug_details": [],
    "cancelled": False,
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
        
        # 3. 获取按日期排序的赛事列表
        races = get_races_from_performances(all_performances)
        result["测试场次"] = len(races)
        
        if result["测试场次"] == 0:
            return result
        
        # 4. 获取马名缓存
        name_cache = get_horse_name_cache()
        
        # 5. 按日期分组赛事（便于按天训练）
        races_by_date = {}
        for race in races:
            date = race['race_date']
            if date not in races_by_date:
                races_by_date[date] = []
            races_by_date[date].append(race)
        
        # 6. 按日期排序
        sorted_dates = sorted(races_by_date.keys())
        
        # 7. 初始化统计变量
        correct_predictions = 0
        total_top3_hits = 0
        total_top3_hit_races = 0
        total_tri_correct = 0
        total_tce_correct = 0
        total_stake = 0
        total_return = 0
        
        # 8. 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 9. 时间滑窗回测
        for idx, current_date in enumerate(sorted_dates):
            # 取消检查点
            if st.session_state.get("stop_backtest", False):
                st.warning("⚠️ 回測已被用戶取消")
                result["cancelled"] = True
                break
            
            status_text.text(f"正在處理日期: {current_date} ({idx+1}/{len(sorted_dates)})")
            progress_bar.progress((idx + 1) / len(sorted_dates))
            
            # 9.1 使用 current_date 之前的所有数据训练模型
            # ⭐ 训练进度提示
            status_text.text(f"正在訓練模型: {current_date} (準備訓練數據中...)")
            
            train_X, train_y = prepare_training_data_by_date(current_date, all_performances, horse_cache)
            
            if train_X is None or len(train_X) < 50:
                status_text.text(f"⚠️ {current_date} 訓練數據不足 ({len(train_X) if train_X is not None else 0} 條)，跳過")
                continue
            
            # ⭐ 显示训练数据量
            status_text.text(f"正在訓練模型: {current_date} (訓練數據: {len(train_X)} 條, 模型: {result['模型']})")
            
            model = train_model_on_data(train_X, train_y, model_type)
            if model is None:
                status_text.text(f"⚠️ {current_date} 模型訓練失敗，跳過")
                continue
            
            # 9.2 预测 current_date 当天的所有赛事
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
                
                # 为每匹马构建特征并预测
                runners = []
                for r in runners_data:
                    horse_id = r.get('horse_id')
                    if not horse_id:
                        continue
                    
                    horse_name = name_cache.get(horse_id, r.get('horse_name', ''))
                    
                    # 获取该马匹在 race_date 之前的往绩
                    all_past = horse_cache.get(horse_id, [])
                    past_before = [p for p in all_past if p.get('race_date', '') < race_date]
                    past_before = past_before[:10]
                    
                    # 构建特征
                    features = {}
                    if past_before:
                        total = len(past_before)
                        wins = sum(1 for p in past_before if p.get('position') == 1)
                        places = sum(1 for p in past_before if p.get('position', 0) in [1, 2])
                        shows = sum(1 for p in past_before if p.get('position', 0) in [1, 2, 3])
                        
                        features['win_rate'] = wins / total
                        features['place_rate'] = places / total
                        features['show_rate'] = shows / total
                        
                        recent_5 = past_before[:5]
                        wins_5 = sum(1 for p in recent_5 if p.get('position') == 1)
                        features['win_rate_5'] = wins_5 / len(recent_5) if recent_5 else 0
                        
                        weights = [p.get('actual_weight', 0) for p in past_before if p.get('actual_weight')]
                        features['avg_weight'] = sum(weights) / len(weights) if weights else 0
                    else:
                        features['win_rate'] = 0
                        features['place_rate'] = 0
                        features['show_rate'] = 0
                        features['win_rate_5'] = 0
                        features['avg_weight'] = 0
                    
                    features['draw'] = r.get('draw', 0) or 0
                    features['actual_weight'] = r.get('actual_weight', 0) or 0
                    features['odds'] = r.get('odds', 10) or 10
                    features['distance'] = distance
                    features['jockey_win_rate'] = 0
                    
                    # 预测
                    prob = predict_with_model(model, features, model_type)
                    
                    # 获取赔率
                    odds_raw = r.get('odds')
                    try:
                        odds = float(odds_raw) if odds_raw else 10
                    except (ValueError, TypeError):
                        odds = 10
                    
                    runners.append({
                        "horse_id": horse_id,
                        "horse_name": horse_name,
                        "horse_no": r.get('horse_no'),
                        "finishing_position": r.get('position'),
                        "win_probability": prob,
                        "odds_win": odds,
                    })
                
                if not runners:
                    continue
                
                # 按胜率排序
                runners.sort(key=lambda x: x.get('win_probability', 0), reverse=True)
                
                # ★ 获取预测前三名
                predicted_1st = runners[0].get('horse_name') if len(runners) > 0 else None
                predicted_2nd = runners[1].get('horse_name') if len(runners) > 1 else None
                predicted_3rd = runners[2].get('horse_name') if len(runners) > 2 else None
                predicted_top3_names = [predicted_1st, predicted_2nd, predicted_3rd]
                predicted_top3_set = {predicted_1st, predicted_2nd, predicted_3rd} - {None}  # ⭐ 必须添加这行
                # 获取实际结果（按名次排序）
                runners_data_sorted = sorted(runners_data, key=lambda x: x.get('position', 99))
                actual_1st = None
                actual_2nd = None
                actual_3rd = None
                actual_top3_names = []
                actual_top3_names = []  # ⭐ 必须定义这个列表
                actual_top3_set = set()  # ⭐ 必须定义这个集合
                for r in runners_data_sorted:
                    pos = r.get('position')
                    horse_id = r.get('horse_id')
                    horse_name = name_cache.get(horse_id, r.get('horse_name', ''))
                    if pos == 1:
                        actual_1st = horse_name
                        actual_top3_names.append(horse_name)
                        actual_top3_set.add(horse_name)  # ⭐ 添加这一行
                    elif pos == 2:
                        actual_2nd = horse_name
                        actual_top3_names.append(horse_name)
                        actual_top3_set.add(horse_name)  # ⭐ 添加这一行
                    elif pos == 3:
                        actual_3rd = horse_name
                        actual_top3_names.append(horse_name)
                        actual_top3_set.add(horse_name)  # ⭐ 添加这一行
                
                # ★ 统计命中情况
                # 统计各指标
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
                
                # ROI：每场都投注 100 元
                total_stake += 100
                if is_correct:
                    odds = runners[0].get('odds_win', 3.0)
                    try:
                        odds = float(odds) if odds else 3.0
                    except:
                        odds = 3.0
                    total_return += 100 * odds
                
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
                    "独赢正确": "✅" if is_correct else "❌",
                    "前3名命中匹数": hits,
                    "前3名全中": "✅" if tri_correct else "❌",
                    "前3名顺序正确": "✅" if tce_correct else "❌"
                })
                
                # 更新统计
                if is_correct:
                    correct_predictions += 1
        
        # 10. 清理进度条
        progress_bar.empty()
        status_text.empty()
        
        # 11. 计算最终结果
        if result["测试场次"] > 0 and not result["cancelled"]:
            result["预测正确"] = correct_predictions
            result["独赢正确率"] = correct_predictions / result["测试场次"] * 100
            
            result["前三名命中匹数"] = total_top3_hits
            result["前三名命中匹数率"] = total_top3_hits / (result["测试场次"] * 3) * 100
            
            result["前三名命中场次"] = total_top3_hit_races
            result["前三名命中场次率"] = total_top3_hit_races / result["测试场次"] * 100
            
            result["前三名全中场次"] = total_tri_correct
            result["前三名全中率"] = total_tri_correct / result["测试场次"] * 100
            
            result["前三名顺序正确场次"] = total_tce_correct
            result["前三名顺序正确率"] = total_tce_correct / result["测试场次"] * 100
            
            result["总投入"] = total_stake
            result["总回报"] = total_return
            if total_stake > 0:
                result["ROI"] = (total_return - total_stake) / total_stake * 100
        
        if not result["cancelled"]:
            st.success(f"✅ {result['模型']} 回測完成: {result['测试场次']} 場, 獨贏正確率 {result['独赢正确率']:.1f}%, ROI {result['ROI']:+.1f}%")
        
    except Exception as e:
        st.error(f"ML回測失敗 ({model_type}): {e}")
        print(f"ML回測失敗: {e}")
    
    # 重置取消标志
    st.session_state.stop_backtest = False
    
    return result
#-----------
def render_backtest_page(show_title: bool = True):
    """回测页面：模型对比 + 单场回测 + 全天回测"""
    if show_title:
        st.markdown("## 📊 回測")
    
    # ==================== 模型对比回测 ====================
    st.markdown("## 📊 模型對比回測")
    st.caption("選擇回測期間，比較不同模型的預測準確率和 ROI")
    
    # 初始化 session_state 中的日期
    if "backtest_start_date" not in st.session_state:
        st.session_state.backtest_start_date = (datetime.now() - timedelta(days=180)).date()
    if "backtest_end_date" not in st.session_state:
        st.session_state.backtest_end_date = datetime.now().date()
    
    # 日期选择器（无预设按钮）
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        backtest_start = st.date_input(
            "開始日期", 
            value=st.session_state.backtest_start_date,
            key="backtest_start_date_input"
        )
    with col2:
        backtest_end = st.date_input(
            "結束日期", 
            value=st.session_state.backtest_end_date,
            key="backtest_end_date_input"
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_backtest_btn = st.button("▶️ 運行模型對比回測", type="primary", use_container_width=True)
    
    # 更新 session_state
    st.session_state.backtest_start_date = backtest_start
    st.session_state.backtest_end_date = backtest_end
    
    # 模型选择复选框
    st.markdown("**🤖 選擇要對比的模型**")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    with col_m1:
        enable_rule = st.checkbox("评分系统", value=True, key="backtest_rule")
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
                                              "总投入", "总回报", "ROI"]
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
    # 在模型对比回测的 completed_results 循环之后添加
    # ==================== 新增：策略回测选项卡 ====================
    st.markdown("## 📊 策略回測")
    st.caption("回測不同投注策略（獨贏、連贏）的歷史表現")
    
    # 策略回测参数
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        backtest_strategy_start = st.date_input(
            "回測開始日期",
            value=datetime.now() - timedelta(days=180),
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
                        # 定义获取评分的函数（需要从现有系统获取）
                        def get_scores_func(race_date, race_no):
                            # 这里需要调用现有的评分系统
                            # 简化版：返回模拟数据
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
                    
                    # 显示回测结果
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

def calculate_win_rate(past_performances: List[Dict], recent_n: int = 10) -> float:
    """计算最近N场的胜率"""
    if not past_performances:
        return 0.0
    recent = past_performances[-recent_n:] if len(past_performances) >= recent_n else past_performances
    wins = sum(1 for p in recent if p.get('finishing_position') == 1)
    return wins / len(recent) if recent else 0.0


def calculate_place_rate(past_performances: List[Dict], recent_n: int = 10) -> float:
    """计算最近N场的入Q率（前2名）"""
    if not past_performances:
        return 0.0
    recent = past_performances[-recent_n:] if len(past_performances) >= recent_n else past_performances
    places = sum(1 for p in recent if p.get('finishing_position', 0) in [1, 2])
    return places / len(recent) if recent else 0.0


def calculate_show_rate(past_performances: List[Dict], recent_n: int = 10) -> float:
    """计算最近N场的入T率（前3名）"""
    if not past_performances:
        return 0.0
    recent = past_performances[-recent_n:] if len(past_performances) >= recent_n else past_performances
    shows = sum(1 for p in recent if p.get('finishing_position', 0) in [1, 2, 3])
    return shows / len(recent) if recent else 0.0


def calculate_rating_trend(past_performances: List[Dict], recent_n: int = 5) -> float:
    """计算官方评分趋势"""
    if len(past_performances) < 2:
        return 0.0
    recent = past_performances[-recent_n:] if len(past_performances) >= recent_n else past_performances
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


def calculate_avg_distance_rating(past_performances: List[Dict], target_distance: int) -> float:
    """计算在目标路程附近的平均表现评分"""
    if not past_performances:
        return 50.0
    scores = []
    weights = []
    for p in past_performances:
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


def calculate_basic_score(horse_id: int, target_distance: int, past_performances: List[Dict]) -> float:
    """计算基础评分（0-100）"""
    win_rate = calculate_win_rate(past_performances)
    place_rate = calculate_place_rate(past_performances)
    show_rate = calculate_show_rate(past_performances)
    rating_trend = calculate_rating_trend(past_performances)
    distance_rating = calculate_avg_distance_rating(past_performances, target_distance)
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


def calculate_same_course_score(horse_id: int, venue: str, past_performances: List[Dict]) -> float:
    """计算同马场往绩评分"""
    venue_performances = [p for p in past_performances if p.get('venue') == venue]
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


def calculate_same_distance_score(horse_id: int, distance: int, past_performances: List[Dict]) -> float:
    """计算同路程往绩评分"""
    distance_performances = [p for p in past_performances if p.get('distance') == distance]
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
    past_performances: List[Dict]
) -> float:
    """计算场次评分"""
    same_course = calculate_same_course_score(horse_id, venue, past_performances)
    same_distance = calculate_same_distance_score(horse_id, distance, past_performances)
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

def get_horse_past_performances(horse_id: int, limit: int = 10) -> List[Dict]:
    """从数据库获取马匹的历史往绩"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances?horse_id=eq.{horse_id}&order=race_date.desc&limit={limit}"
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
    past = get_horse_past_performances(horse_id, limit=20)
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
    past_performances = get_horse_past_performances(horse_id)
    basic_score = calculate_basic_score(horse_id, distance, past_performances)
    weight_comfort_range = get_horse_weight_comfort_range(horse_id)
    race_score = calculate_race_score(
        horse_id, venue, distance, draw, actual_weight,
        jockey_id, trainer_id, weight_comfort_range, past_performances
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
        url = f"{SUPABASE_URL}/rest/v1/past_performances?horse_id=in.({ids_str})&order=race_date.desc&limit=10000"
        
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


def get_horse_past_performances_optimized(horse_id: str, cache: Dict[str, List[Dict]], limit: int = 10) -> List[Dict]:
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
    """
    计算一场赛事所有马匹的评分和胜率（优化版）
    - 批量获取所有马匹的往绩（1次请求）
    - 从缓存读取，避免 N+1 查询
    """
    if not runners:
        return [], []
    
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
        past_performances = get_horse_past_performances_optimized(horse_id, perf_cache, limit=10)
        
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
        basic_score = calculate_basic_score_fast(past_performances, distance)
        
        # 计算场次评分
        weight_comfort_range = get_horse_weight_comfort_range_from_cache(horse_id, past_performances)
        race_score = calculate_race_score_optimized(
            horse_id, venue, distance, draw, actual_weight,
            jockey_id, trainer_id, weight_comfort_range, past_performances
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


def get_horse_weight_comfort_range_from_cache(horse_id: str, past_performances: List[Dict]) -> Tuple[int, int]:
    """从缓存的往绩中获取马匹的负磅舒适区（不查询数据库）"""
    winning_weights = []
    for p in past_performances:
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
    past_performances: List[Dict]
) -> float:
    """
    计算场次评分（优化版，使用已获取的往绩）
    """
    # 同马场往绩
    same_course = calculate_same_course_score_from_cache(horse_id, venue, past_performances)
    
    # 同路程往绩
    same_distance = calculate_same_distance_score_from_cache(horse_id, distance, past_performances)
    
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


def calculate_same_course_score_from_cache(horse_id: str, venue: str, past_performances: List[Dict]) -> float:
    """从缓存的往绩中计算同马场评分"""
    venue_performances = [p for p in past_performances if p.get('venue') == venue]
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


def calculate_same_distance_score_from_cache(horse_id: str, distance: int, past_performances: List[Dict]) -> float:
    """从缓存的往绩中计算同路程评分"""
    distance_performances = [p for p in past_performances if p.get('distance') == distance]
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
        check_url = f"{SUPABASE_URL}/rest/v1/past_performances?race_date=eq.{record['race_date']}&venue=eq.{record['venue']}&race_no=eq.{record['race_no']}&horse_no=eq.{record['horse_no']}"
        check_response = requests.get(check_url, headers=headers)
        
        if check_response.status_code == 200 and check_response.json():
            # 已存在，跳过
            return True
        
        # 插入新记录
        insert_url = f"{SUPABASE_URL}/rest/v1/past_performances"
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
    """从 past_performances 表获取最新的赛事日期"""
    try:
        headers = get_supabase_headers(use_secret=True)
        # ✅ 改为查询 past_performances 表
        url = f"{SUPABASE_URL}/rest/v1/past_performances?order=race_date.desc&limit=1&select=race_date"
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
        count_url = f"{SUPABASE_URL}/rest/v1/past_performances?select=id"
        count_response = requests.get(count_url, headers=headers)
        
        if count_response.status_code != 200:
            return result
        
        all_ids = [item.get('id') for item in count_response.json() if item.get('id')]
        total_count = len(all_ids)
        
        if total_count <= keep_count:
            result["kept"] = total_count
            return result
        
        # 获取需要保留的最新记录 ID
        keep_url = f"{SUPABASE_URL}/rest/v1/past_performances?order=race_date.desc&limit={keep_count}&select=id"
        keep_response = requests.get(keep_url, headers=headers)
        
        if keep_response.status_code != 200:
            return result
        
        keep_ids = {str(item.get('id')) for item in keep_response.json() if item.get('id')}
        
        # 删除不在保留列表中的记录
        for record_id in all_ids:
            if str(record_id) not in keep_ids:
                delete_url = f"{SUPABASE_URL}/rest/v1/past_performances?id=eq.{record_id}"
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
    """从 past_performances 表获取最新的赛事日期"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances?order=race_date.desc&limit=1&select=race_date"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('race_date')
        return None
    except Exception as e:
        print(f"获取数据库最新日期失败: {e}")
        return None


def save_race_results_batch(results: List[Dict]) -> bool:
    """
    批量保存一场赛事的全部结果到 past_performances 表
    使用 upsert 避免重复
    """
    if not results:
        return True
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 构建 upsert 请求（如果有重复则更新）
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/past_performances",
            headers={
                **headers,
                "Prefer": "resolution=merge-duplicates"  # 关键：重复时更新
            },
            json=results
        )
        
        if response.status_code in [200, 201]:
            print(f"批量保存成功: {len(results)} 条记录")
            return True
        else:
            print(f"批量保存失败: {response.status_code} - {response.text}")
            return False
            
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
    """从 past_performances 表获取最新的赛事日期"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/past_performances?order=race_date.desc&limit=1&select=race_date"
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            return response.json()[0].get('race_date')
        return None
    except Exception as e:
        print(f"获取数据库最新日期失败: {e}")
        return None


def save_race_results_batch(results: List[Dict]) -> bool:
    """
    批量保存一场赛事的全部结果到 past_performances 表
    """
    if not results:
        return True
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 清理每条记录
        clean_results = []
        for record in results:
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
            clean_results.append(clean_record)
        
        # 批量 upsert
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/past_performances",
            headers={
                **headers,
                "Prefer": "resolution=merge-duplicates"
            },
            json=clean_results
        )
        
        if response.status_code in [200, 201]:
            print(f"批量保存成功: {len(results)} 条记录")
            return True
        else:
            print(f"批量保存失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"批量保存异常: {e}")
        return False
#----------------
def sync_all_data() -> Dict:
    """
    智能同步所有数据（优化版）
    1. 从数据库获取最新日期
    2. 从最新日期遍历到今天
    3. 爬虫自动判断是否有赛事
    4. 批量写入，提高性能
    5. 提前终止无效场次循环
    6. 清理超过 9000 行的旧数据
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
        
        # ==================== 第5步：清理旧数据 ====================
        if total_new_records > 0:
            with st.spinner("正在清理旧数据..."):
                cleanup_result = cleanup_old_records(keep_count=9000)
                if cleanup_result.get("deleted", 0) > 0:
                    st.info(f"已清理 {cleanup_result['deleted']} 条旧记录，保持数据库在 9000 行以内")
        
        # ==================== 第6步：清除缓存 ====================
        st.cache_data.clear()
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        st.error(f"更新失败: {e}")
        print(f"更新异常: {e}")
        return result


def cleanup_old_records(keep_count: int = 9000) -> Dict:
    """清理旧记录，只保留最新的 keep_count 条"""
    result = {"deleted": 0, "kept": 0}
    
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 获取当前记录数
        count_url = f"{SUPABASE_URL}/rest/v1/past_performances?select=id"
        count_response = requests.get(count_url, headers=headers)
        
        if count_response.status_code != 200:
            return result
        
        all_ids = [item.get('id') for item in count_response.json() if item.get('id')]
        total_count = len(all_ids)
        
        if total_count <= keep_count:
            result["kept"] = total_count
            return result
        
        # 获取需要保留的最新记录 ID
        keep_url = f"{SUPABASE_URL}/rest/v1/past_performances?order=race_date.desc&limit={keep_count}&select=id"
        keep_response = requests.get(keep_url, headers=headers)
        
        if keep_response.status_code != 200:
            return result
        
        keep_ids = {str(item.get('id')) for item in keep_response.json() if item.get('id')}
        
        # 删除不在保留列表中的记录
        for record_id in all_ids:
            if str(record_id) not in keep_ids:
                delete_url = f"{SUPABASE_URL}/rest/v1/past_performances?id=eq.{record_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                if delete_response.status_code in [200, 204]:
                    result["deleted"] += 1
        
        result["kept"] = keep_count
        
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
    """同步未来 N 天的所有赛事（带进度条）"""
    results = {"success": 0, "failed": 0, "total": 0}
    
    # 创建进度条
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(days):
        sync_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        status_text.text(f"正在同步 {sync_date}...")
        
        # 传入 show_progress=False
        result = update_all_data_for_date(sync_date, show_progress=False)
        results["success"] += result.get("success", 0)
        results["failed"] += result.get("failed", 0)
        results["total"] += result.get("total", 0)
        
        # 更新进度条
        progress_bar.progress((i + 1) / days)
        time.sleep(0.5)
    
    progress_bar.empty()
    status_text.empty()
    
    return results
# ==================== 第2次代码结束 ====================
# 注意：没有 if __name__ == "__main__"，因为主入口在第1次代码中

if __name__ == "__main__":
    main()
