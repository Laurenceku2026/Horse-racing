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
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from supabase import create_client, Client

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
    tab1, tab2, tab3 = st.tabs(["📊 数据编辑器", "📈 回测", "👥 用户管理"])
    
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


def get_table_data(table_name: str, limit: int = 500) -> List[Dict]:
    """获取表数据"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/{table_name}?order=race_date.desc&limit={limit}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"获取表数据失败: {e}")
        return []


def save_table_data(table_name: str, data: List[Dict]) -> bool:
    """全量覆盖保存表数据"""
    try:
        headers = get_supabase_headers(use_secret=True)
        # 先清空表
        supabase_request("DELETE", table_name, params="", access_token=None)
        # 批量插入
        for record in data:
            response = supabase_request("POST", table_name, data=record, access_token=None)
            if response.status_code not in [200, 201]:
                print(f"插入失败: {response.text}")
                return False
        return True
    except Exception as e:
        print(f"保存失败: {e}")
        return False


def incremental_sync_table(table_name: str, new_data: List[Dict]) -> Dict:
    """增量同步表数据"""
    result = {"inserted": 0, "updated": 0, "deleted": 0}
    
    try:
        # 获取现有数据
        existing = get_table_data(table_name, limit=10000)
        existing_ids = {str(r.get('id')) for r in existing if r.get('id')}
        new_ids = {str(r.get('id')) for r in new_data if r.get('id')}
        
        # 需要删除的
        to_delete = existing_ids - new_ids
        # 需要新增的
        to_insert = new_ids - existing_ids
        
        headers = get_supabase_headers(use_secret=True)
        
        # 删除
        for record_id in to_delete:
            supabase_request("DELETE", table_name, params=f"id=eq.{record_id}", access_token=None)
            result["deleted"] += 1
        
        # 插入新记录
        for record in new_data:
            if str(record.get('id')) in to_insert or not record.get('id'):
                supabase_request("POST", table_name, data=record, access_token=None)
                result["inserted"] += 1
            else:
                # 更新现有记录
                record_id = record.get('id')
                if record_id:
                    supabase_request("PATCH", table_name, data=record, params=f"id=eq.{record_id}", access_token=None)
                    result["updated"] += 1
        
        return result
    except Exception as e:
        print(f"增量同步失败: {e}")
        return result


def render_user_management():
    """用户管理界面"""
    st.markdown("### 👥 用户管理")
    
    users = get_all_users()
    
    if not users:
        st.info("暂无用户数据")
        return
    
    # 显示用户列表
    display_users = []
    for u in users:
        display_users.append({
            "邮箱": u.get('email', '未知'),
            "订阅等级": "专业版" if u.get('subscription_tier') == 'pro' else "免费版",
            "剩余次数": u.get('free_trials_remaining', 30),
            "注册时间": u.get('created_at', '')[:10] if u.get('created_at') else '-'
        })
    
    df_users = pd.DataFrame(display_users)
    st.dataframe(df_users, use_container_width=True, hide_index=True)
    st.caption(f"共 {len(users)} 位用户")
#----------------------------
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
    """获取所有马匹的基础评分（基于指定最近场次）
    
    Args:
        limit: 返回马匹数量
        recent_games: 使用最近多少场比赛计算（0 表示全部）
    """
    try:
        headers = get_supabase_headers(use_secret=True)
        
        # 获取所有成绩记录
        url = f"{SUPABASE_URL}/rest/v1/past_performances?select=horse_name,position,body_weight,race_date&limit=50000"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            st.error(f"查询失败: {response.status_code}")
            return pd.DataFrame()
        
        data = response.json()
        
        if not data:
            return pd.DataFrame()
        
        # 按马名分组
        from collections import defaultdict
        horse_records = defaultdict(list)
        
        for p in data:
            horse_name = p.get("horse_name")
            if not horse_name:
                continue
            horse_records[horse_name].append({
                "position": p.get("position"),
                "body_weight": p.get("body_weight"),
                "race_date": p.get("race_date")
            })
        
        results = []
        for horse_name, records in horse_records.items():
            # 按日期排序（最新的在前）
            records.sort(key=lambda x: x.get("race_date", ""), reverse=True)
            
            # 取最近 N 场
            if recent_games == 0:
                selected = records
            else:
                selected = records[:recent_games]
            
            total = len(selected)
            if total < 3:  # 少于3场不显示
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
        races_url = f"{SUPABASE_URL}/rest/v1/races"
        races_response = requests.get(races_url, headers=headers)
        race_count = len(races_response.json()) if races_response.status_code == 200 else 0
        
        # 成绩记录数量
        perf_url = f"{SUPABASE_URL}/rest/v1/past_performances"
        perf_response = requests.get(perf_url, headers=headers)
        perf_count = len(perf_response.json()) if perf_response.status_code == 200 else 0
        
        # 最新和最旧赛事日期
        races_data = races_response.json() if races_response.status_code == 200 else []
        if races_data:
            dates = [r.get('race_date') for r in races_data if r.get('race_date')]
            latest_date = max(dates) if dates else 'N/A'
            oldest_date = min(dates) if dates else 'N/A'
        else:
            latest_date = 'N/A'
            oldest_date = 'N/A'
        
        # 第一行：4个指标
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🐎 馬匹總數", horse_count)
        with col2:
            st.metric("🏆 賽事總數", race_count)
        with col3:
            st.metric("📊 成績記錄總數", perf_count)
        with col4:
            st.metric("📅 數據日期範圍", f"{oldest_date} ~ {latest_date}" if latest_date != 'N/A' else "暂无数据")
        
        # 第二行：骑师和练马师
        jockeys_url = f"{SUPABASE_URL}/rest/v1/jockeys"
        jockeys_response = requests.get(jockeys_url, headers=headers)
        jockey_count = len(jockeys_response.json()) if jockeys_response.status_code == 200 else 0
        
        trainers_url = f"{SUPABASE_URL}/rest/v1/trainers"
        trainers_response = requests.get(trainers_url, headers=headers)
        trainer_count = len(trainers_response.json()) if trainers_response.status_code == 200 else 0
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🤠 騎師總數", jockey_count)
        with col2:
            st.metric("🏋️ 練馬師總數", trainer_count)
            
    except Exception as e:
        st.warning(f"獲取數據統計失敗: {e}")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🐎 馬匹總數", "0")
        with col2:
            st.metric("🏆 賽事總數", "0")
        with col3:
            st.metric("📊 成績記錄總數", "0")
        with col4:
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
    render_smart_betting(show_title=False)
    
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
        url = f"{SUPABASE_URL}/rest/v1/races?race_date=gte.{today}&race_date=lte.{next_two_weeks}&order=race_date.asc,race_no.asc"
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
    """获取赛事出赛马匹详情（含评分）"""
    try:
        headers = get_supabase_headers(use_secret=True)
        # 使用 race_date, venue, race_no 查询
        url = f"{SUPABASE_URL}/rest/v1/race_runners?race_date=eq.{race_date}&venue=eq.{venue}&race_no=eq.{race_no}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            runners = response.json()
            # 注意：runners 中已经有 horse_name 和 jockey_name，不需要再补充
            return runners
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
    sorted_runners = sorted(runners, key=lambda x: x.get('win_probability', 0), reverse=True)
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
                runners_url = f"{SUPABASE_URL}/rest/v1/race_runners?race_id=eq.{race.get('race_id')}"
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
    """智能投注页面：单场分析 + 全天优化"""
    if show_title:
        st.markdown("## 🎯 智能投注")
        
    # ==================== 用户设置区域 ====================
    with st.expander("⚙️ 投注設置", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # 获取用户默认预算
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
            
            # 风险系数映射
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
    
    # ==================== 选择赛日 ====================
    st.markdown("### 📅 選擇賽日")

    # ... 后续代码
    upcoming_races = get_upcoming_races()
    
    if not upcoming_races:
        st.info("📌 未來7天暫無賽事，請點擊「更新數據」同步最新賽程")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 更新賽程", use_container_width=True):
                if consume_free_trial(st.session_state.user_id):
                    with st.spinner("正在更新賽程..."):
                        today = datetime.now().strftime("%Y-%m-%d")
                        result = update_all_data_for_date(today)
                        if result["total"] > 0:
                            st.success(f"更新完成！成功 {result['success']} 場")
                            st.rerun()
                        else:
                            st.info("今日暫無賽事")
                else:
                    st.warning("免費次數已用完")
        return
    
    # 按日期分组显示
    dates = sorted(set([r.get('race_date') for r in upcoming_races]))
    date_options = [f"{d} ({['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][datetime.strptime(d, '%Y-%m-%d').weekday()]})" for d in dates]
    
    selected_date_str = st.selectbox("選擇賽日", date_options, key="selected_race_date")
    selected_date = selected_date_str.split(" ")[0]
    
    # 获取该日期的所有赛事
    races = get_races_by_date(selected_date)
    
    if not races:
        st.warning("該日期暫無賽事數據")
        return
    
    st.markdown(f"**📋 共 {len(races)} 場賽事**")
    st.markdown("---")
    
    # ==================== 单场分析 ====================
    st.markdown("### 📊 單場分析")
    
    # 选择场次
    race_options = [f"第{r.get('race_no')}場 - {r.get('distance')}米 ({r.get('venue', 'ST')}) - {r.get('race_class', '')}" for r in races]
    selected_race_idx = st.selectbox("選擇場次", range(len(race_options)), format_func=lambda x: race_options[x], key="selected_race")
    
    selected_race = races[selected_race_idx]
    race_id = selected_race.get('race_id')
    
    # 获取出赛马匹
    runners = get_race_runners_with_details(
        selected_race.get('race_date'),
        selected_race.get('venue'),
        selected_race.get('race_no')
    )
    
    if not runners:
        st.warning("暫無出賽馬匹數據")
        return
    
    # 获取用户权重
    user_weights = {
        "basic": 0.30,
        "race": 0.40,
        "odds": 0.30,
        "temperature": 0.8,
        "odds_mix_ratio": 0.6
    }
    #-----------
    # 根据选择的模型计算胜率
    if model_choice == "评分系统":
        with st.spinner("正在計算馬匹勝率（評分系統）..."):
            scores, probabilities = calculate_all_horses_scores(race_id, runners, user_weights)
        
        # 更新runner数据
        for i, runner in enumerate(runners):
            if i < len(scores):
                runner['basic_score'] = scores[i].get('basic_score', 0)
                runner['race_score'] = scores[i].get('race_score', 0)
                runner['odds_score'] = scores[i].get('odds_score', 0)
                runner['overall_score'] = scores[i].get('combined_score', 0)
                runner['win_probability'] = scores[i].get('win_probability', 0) / 100
    else:
        # 使用 ML 模型预测
        model_type = 'lightgbm' if model_choice == "LightGBM" else 'xgboost' if model_choice == "XGBoost" else 'ensemble'
        with st.spinner(f"正在計算馬匹勝率（{model_choice}）..."):
            ml_probs = get_model_predictions(race_id, runners, model_type)
        
        # 更新runner数据
        for i, runner in enumerate(runners):
            if i < len(ml_probs):
                runner['win_probability'] = ml_probs[i]
                # ML 模型没有详细的子评分，设置默认值
                runner['basic_score'] = 50
                runner['race_score'] = 50
                runner['odds_score'] = 50
                runner['overall_score'] = ml_probs[i] * 100
            else:
                runner['win_probability'] = 0.1
    
    # 按胜率排序
    sorted_runners = sorted(runners, key=lambda x: x.get('win_probability', 0), reverse=True)
    
    # 显示分析结果
    st.markdown(f"#### 🏇 第{selected_race.get('race_no')}場 分析結果")
    
    # 表格显示
    race_data = []
    for runner in sorted_runners:
        horse_name = runner.get('horse_name_zh', runner.get('horse_name_en', ''))
        draw = runner.get('draw', '-')
        weight = runner.get('actual_weight', '-')
        odds_win = runner.get('odds_win')
        
        # 安全处理赔率
        try:
            odds_display = f"{float(odds_win):.1f}" if odds_win and float(odds_win) > 0 else "-"
        except (ValueError, TypeError):
            odds_display = "-"
        
        prob = runner.get('win_probability', 0) * 100
        score = runner.get('overall_score', 0)
        
        # 等级
        if score >= 85:
            level = "S"
        elif score >= 70:
            level = "A"
        elif score >= 55:
            level = "B"
        elif score >= 40:
            level = "C"
        else:
            level = "D"
        
        race_data.append({
            "馬名": horse_name,
            "檔位": draw,
            "負磅": weight,
            "賠率": odds_display,
            "綜合評分": f"{score:.0f}",
            "等級": level,
            "勝率": f"{prob:.1f}%"
        })
    
    st.dataframe(pd.DataFrame(race_data), use_container_width=True, hide_index=True)
    
    # 投注建议
    st.markdown("#### 💡 投注建議")
    
    top3 = get_top_horses_by_probability(runners, limit=3)
    
    if top3:
        col1, col2, col3 = st.columns(3)
        
        for i, horse in enumerate(top3):
            prob = horse.get('win_probability', 0) * 100
            odds_raw = horse.get('odds_win')
            
            # 安全转换赔率
            try:
                odds = float(odds_raw) if odds_raw else 0
            except (ValueError, TypeError):
                odds = 0
            
            score = horse.get('overall_score', 0)
            horse_name = horse.get('horse_name_zh', horse.get('horse_name_en', ''))
            
            kelly_fraction = calculate_kelly_fraction(prob / 100, odds) if odds > 0 else 0
            suggested_stake = bankroll * kelly_fraction * risk_multiplier
            
            with [col1, col2, col3][i]:
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 0.8rem; border-radius: 0.5rem; margin-bottom: 0.5rem;">
                    <strong>🥇 {horse_name}</strong><br>
                    勝率: {prob:.1f}% | 賠率: {odds:.1f}<br>
                    評分: {score:.0f}<br>
                    建議注額: <strong>HK${suggested_stake:.0f}</strong>
                </div>
                """, unsafe_allow_html=True)
        
        # 连赢建议
        if len(top3) >= 2:
            st.markdown("---")
            st.markdown("**🔗 連贏建議 (QIN)**")
            
            for i in range(min(2, len(top3))):
                for j in range(i+1, min(3, len(top3))):
                    horse1 = top3[i]
                    horse2 = top3[j]
                    prob1 = horse1.get('win_probability', 0)
                    prob2 = horse2.get('win_probability', 0)
                    joint_prob = prob1 * prob2 * 2  # 近似联合概率
                    
                    # 安全获取赔率
                    odds1_raw = horse1.get('odds_win')
                    odds2_raw = horse2.get('odds_win')
                    
                    # 安全转换赔率
                    try:
                        odds1 = float(odds1_raw) if odds1_raw else 0
                    except (ValueError, TypeError):
                        odds1 = 0
                    
                    try:
                        odds2 = float(odds2_raw) if odds2_raw else 0
                    except (ValueError, TypeError):
                        odds2 = 0
                    
                    # 连赢赔率估算（简化：取两匹马赔率乘积的一半）
                    qin_odds = (odds1 * odds2) / 2 if odds1 > 0 and odds2 > 0 else 0
                    
                    if qin_odds > 0 and joint_prob * qin_odds > 1:
                        suggested_qin = bankroll * 0.05 * risk_multiplier
                        st.markdown(f"**{horse1.get('horse_name_zh', '')} + {horse2.get('horse_name_zh', '')}** | 建議注額: HK${suggested_qin:.0f}")
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
        url = f"{SUPABASE_URL}/rest/v1/races?race_status=eq.RESULT&order=race_date.desc,race_no.asc&limit={limit}"
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
def render_backtest_page(show_title: bool = True):
    """回测页面：模型对比 + 单场回测 + 全天回测"""
    if show_title:
        st.markdown("## 📊 回測")
    
    # ==================== 新增：模型对比回测 ====================
    st.markdown("### 🤖 模型對比回測")
    st.caption("選擇回測期間，比較不同模型的預測準確率和 ROI")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        backtest_start = st.date_input(
            "開始日期", 
            value=datetime.now() - timedelta(days=90),
            key="backtest_start_date"
        )
    with col2:
        backtest_end = st.date_input(
            "結束日期", 
            value=datetime.now(),
            key="backtest_end_date"
        )
    with col3:
        run_backtest_btn = st.button("▶️ 運行模型對比回測", type="primary", use_container_width=True)
    
    if run_backtest_btn:
        if not consume_free_trial(st.session_state.user_id):
            st.warning("免費次數已用完，請升級到專業版")
        else:
            with st.spinner("正在運行模型對比回測..."):
                results = run_models_backtest(
                    start_date=backtest_start.strftime("%Y-%m-%d"),
                    end_date=backtest_end.strftime("%Y-%m-%d")
                )
                
                if results:
                    st.markdown("#### 📈 模型對比結果")
                    
                    # 显示对比表格
                    compare_df = pd.DataFrame(results)
                    st.dataframe(
                        compare_df.style.format({
                            '准确率': '{:.1f}%',
                            'ROI': '{:+.1f}%',
                            '总回报': '${:.0f}'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # 绘制对比图表
                    fig = go.Figure()
                    for model in results:
                        fig.add_trace(go.Bar(
                            name=model['模型'],
                            x=['准确率', 'ROI'],
                            y=[model['准确率'], model['ROI']],
                            text=[f"{model['准确率']:.1f}%", f"{model['ROI']:+.1f}%"],
                            textposition='auto'
                        ))
                    fig.update_layout(title="模型性能对比", barmode='group', height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("回测数据不足，请确保有足够的历史数据")
    
    st.markdown("---")
    
    # ==================== 原有的单场回测代码保持不变 ====================
    # 获取用户权重
    user_weights = {
        "basic": 0.30,
        "race": 0.40,
        "odds": 0.30,
        "temperature": 0.8,
        "odds_mix_ratio": 0.6
    }
    
    # 单场回测
    st.markdown("### 🏇 單場回測")
    st.caption("選擇一場已完成賽事，AI預測 vs 實際結果")
    
    # 获取历史赛事
    historical_races = get_historical_races(limit=50)
    
    if not historical_races:
        st.info("暫無歷史賽事數據，請確保數據庫中有已完成賽事")
    else:
        # 选择赛事
        race_options = []
        for r in historical_races:
            race_date = r.get('race_date', '')
            race_no = r.get('race_no', 0)
            venue = r.get('venue', '')
            distance = r.get('distance', 0)
            race_options.append(f"{race_date} 第{race_no}場 - {venue} {distance}米")
        
        selected_idx = st.selectbox("選擇賽事", range(len(race_options)), format_func=lambda x: race_options[x], key="backtest_race_select")
        selected_race = historical_races[selected_idx]
        
        col1, col2 = st.columns(2)
        with col1:
            run_single_btn = st.button("▶️ 運行單場回測", use_container_width=True, type="primary")
        with col2:
            if st.button("🔄 刷新歷史數據", use_container_width=True):
                st.rerun()
        
        if run_single_btn:
            if not consume_free_trial(st.session_state.user_id):
                st.warning("免費次數已用完，請升級到專業版")
            else:
                with st.spinner("正在運行回測..."):
                    result = run_backtest_on_race(
                        selected_race.get('race_id'),
                        selected_race.get('race_date'),
                        user_weights
                    )
                    
                    if result.get("success"):
                        st.markdown("---")
                        st.markdown("#### 📈 回測結果")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if result.get("is_correct"):
                                st.success("✅ 預測正確")
                            else:
                                st.error("❌ 預測錯誤")
                        with col2:
                            st.metric("總出賽馬匹", result.get("total_runners", 0))
                        with col3:
                            st.metric("預測冠軍得分", f"{result.get('predicted_winner_score', 0):.0f}")
                        
                        st.info(f"🏆 實際冠軍: {result.get('actual_winner_name', '未知')}")
                        
                        # 前三名命中
                        st.metric("前三名命中數", f"{result.get('top3_hits', 0)}/3")
                    else:
                        st.error(f"回測失敗: {result.get('error', '未知錯誤')}")
    
    st.markdown("---")
    
    # ==================== 原有的全天回测代码保持不变 ====================
    st.markdown("### 📅 全天回測")
    st.caption("選擇一個賽日，測試AI對全天賽事的預測準確率")
    
    # 获取有多个赛事的日期
    if historical_races:
        # 按日期分组
        dates_with_races = {}
        for r in historical_races:
            date = r.get('race_date', '')
            if date not in dates_with_races:
                dates_with_races[date] = 0
            dates_with_races[date] += 1
        
        # 筛选有3场以上赛事的日期
        valid_dates = [d for d, count in dates_with_races.items() if count >= 3]
        
        if valid_dates:
            date_options = [f"{d} ({dates_with_races[d]}場)" for d in valid_dates]
            selected_date_idx = st.selectbox("選擇賽日", range(len(date_options)), format_func=lambda x: date_options[x], key="backtest_date_select")
            selected_date = valid_dates[selected_date_idx]
            
            col1, col2 = st.columns(2)
            with col1:
                run_full_btn = st.button("▶️ 運行全天回測", use_container_width=True, type="primary")
            with col2:
                st.caption(f"該賽日共 {dates_with_races[selected_date]} 場賽事")
            
            if run_full_btn:
                if not consume_free_trial(st.session_state.user_id):
                    st.warning("免費次數已用完，請升級到專業版")
                else:
                    with st.spinner("正在運行全天回測..."):
                        full_result = run_full_day_backtest(selected_date, user_weights)
                        
                        if full_result.get("success"):
                            st.markdown("---")
                            st.markdown(f"#### 📈 全天回測結果 - {selected_date}")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("總場次", full_result.get("total_races", 0))
                            with col2:
                                st.metric("預測正確", f"{full_result.get('correct_predictions', 0)}場")
                            with col3:
                                accuracy = full_result.get("accuracy", 0)
                                st.metric("勝出預測準確率", f"{accuracy:.1f}%")
                            with col4:
                                top3_acc = full_result.get("top3_accuracy", 0)
                                st.metric("前三名命中率", f"{top3_acc:.1f}%")
                            
                            # 显示每场明细
                            if full_result.get("results"):
                                st.markdown("#### 📋 場次明細")
                                results_df = pd.DataFrame(full_result["results"])
                                results_df.columns = ["場次", "預測正確", "前三名命中", "總馬匹"]
                                st.dataframe(results_df, use_container_width=True, hide_index=True)
                        else:
                            st.error(f"回測失敗: {full_result.get('error', '未知錯誤')}")
        else:
            st.info("暫無足夠的歷史賽事數據（需要至少一個賽日有3場以上賽事）")
    
    st.markdown("---")
    
    # ==================== 回测说明 ====================
    with st.expander("📖 回測說明", expanded=False):
        st.markdown("""
        ### 回測邏輯
        
        **時間旅行原則**：回測時只使用該賽事**之前**的歷史數據，不使用未來數據。
        
        **預測方法**：
        - 基於馬匹在該日期之前的往績計算基礎評分
        - 基於排位時的檔位、負磅、騎師、練馬師計算場次評分
        - 基於賽前賠率進行校准
        - 綜合評分最高的馬匹為AI預測冠軍
        
        **評估指標**：
        - **勝出預測準確率**：AI預測冠軍 = 實際冠軍的比例
        - **前三名命中率**：AI預測前三名中包含實際前三名的比例
        
        **注意事項**：
        - 回測結果僅供參考，不代表未來表現
        - 歷史數據越充足，回測結果越可信
        """)
    
    st.markdown("---")
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
#-----------------
def calculate_all_horses_scores(
    race_id: int,
    runners: List[Dict],
    user_weights: Dict
) -> Tuple[List[Dict], List[float]]:
    """计算一场赛事所有马匹的评分和胜率"""
    if not runners:
        return [], []
    
    scores = []
    basic_scores = []
    race_scores = []
    odds_scores = []
    
    for runner in runners:
        # 获取赔率，处理 None 情况
        odds_win = runner.get("odds_win")
        if odds_win is None or odds_win == '':
            odds_win = 10.0  # 默认赔率
        
        result = calculate_horse_score(
            horse_id=runner.get("horse_id"),
            race_id=race_id,
            venue=runner.get("venue", "ST"),
            distance=runner.get("distance", 1200),
            draw=runner.get("draw"),
            actual_weight=runner.get("actual_weight"),
            jockey_id=runner.get("jockey_id"),
            trainer_id=runner.get("trainer_id"),
            odds_win=odds_win,
            user_weights=user_weights
        )
        scores.append(result)
        basic_scores.append(result["basic_score"])
        race_scores.append(result["race_score"])
        odds_scores.append(result["odds_score"])
    
    probabilities = calculate_win_probabilities(
        basic_scores, race_scores, odds_scores,
        user_weights, user_weights.get("odds_mix_ratio", 0.6)
    )
    
    for i, prob in enumerate(probabilities):
        scores[i]["win_probability"] = round(prob * 100, 2)
    
    return scores, probabilities


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


def get_latest_race_date_from_db() -> Optional[str]:
    """从数据库获取最新的赛事日期"""
    try:
        headers = get_supabase_headers(use_secret=True)
        url = f"{SUPABASE_URL}/rest/v1/races?order=race_date.desc&limit=1"
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


def sync_all_data() -> Dict:
    """
    智能同步所有数据（增量更新）
    1. 检查 Supabase 中最新的赛事日期
    2. 只抓取缺失的日期数据
    3. 保持总数据量不超过 9000 行
    """
    result = {"success": False, "new_races": 0, "new_records": 0, "error": None}
    
    if not SCRAPER_AVAILABLE:
        result["error"] = "爬虫模块不可用，请确保 hkjc_advanced_scraper_v2.py 在项目根目录"
        return result
    
    try:
        # 1. 获取当前数据库中最新的赛事日期
        latest_date_str = get_latest_race_date_from_db()
        
        # 2. 确定需要同步的起始日期
        if latest_date_str:
            latest_date = datetime.strptime(latest_date_str, '%Y-%m-%d')
            start_date = latest_date + timedelta(days=1)
            # 如果最新日期是今天或未来，不需要同步
            if start_date > datetime.now():
                result["success"] = True
                result["new_races"] = 0
                result["new_records"] = 0
                return result
        else:
            # 没有数据，从 2025-01-01 开始
            start_date = datetime(2025, 1, 1)
        
        end_date = datetime.now()
        
        # 3. 遍历日期范围，抓取缺失的数据
        total_new_races = 0
        total_new_records = 0
        
        current = start_date
        venues = ['ST', 'HV']
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 计算总天数
        total_days = (end_date - start_date).days + 1
        days_processed = 0
        
        while current <= end_date:
            days_processed += 1
            progress_bar.progress(days_processed / total_days)
            
            if current.weekday() in [5, 6]:  # 周六或周日
                date_str = current.strftime("%Y/%m/%d")
                status_text.text(f"正在同步 {current.strftime('%Y-%m-%d')}...")
                
                for venue in venues:
                    for race_no in range(1, 13):
                        try:
                            race_info, results = parse_race_result(date_str, venue, race_no)
                            
                            if results:
                                # 保存每条记录
                                for record in results:
                                    # 添加赛事信息
                                    record['race_class'] = race_info.get('race_class', '')
                                    record['distance'] = race_info.get('distance', 0)
                                    record['going'] = race_info.get('going', '')
                                    record['sectional_times'] = json.dumps(race_info.get('sectional_times', []))
                                    
                                    success = save_race_result_to_db(record)
                                    if success:
                                        total_new_records += 1
                                
                                total_new_races += 1
                        except Exception as e:
                            print(f"同步失败 {date_str} {venue} 第{race_no}场: {e}")
                            continue
                    
                    time.sleep(1)  # 避免请求过快
            
            current += timedelta(days=1)
        
        progress_bar.empty()
        status_text.empty()
        
        result["success"] = True
        result["new_races"] = total_new_races
        result["new_records"] = total_new_records
        
        # 4. 清理超过 9000 行的旧数据
        if total_new_records > 0:
            cleanup_result = cleanup_old_records(keep_count=9000)
            if cleanup_result.get("deleted", 0) > 0:
                st.info(f"已清理 {cleanup_result['deleted']} 条旧记录，保持数据库在 9000 行以内")
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
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
