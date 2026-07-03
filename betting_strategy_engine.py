"""
香港赛马AI投注策略引擎
功能：
- 基于AI评分计算胜率、入Q率、入T率
- 计算各彩池的期望值 (EV)
- 生成 Top 3 投注建议（独赢、连赢、位置、单T）
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


def format_horse_display(name: str, horse_no=None) -> str:
    """统一显示：马名(马号)"""
    name = (name or "").strip()
    if horse_no is not None and str(horse_no).strip() not in ("", "0", "None"):
        return f"{name}({horse_no})" if name else f"({horse_no})"
    return name or "-"


def pick_horse_name(
    record: Dict,
    lang: str = "zh",
    name_lookup: Optional[Dict[str, Dict[str, str]]] = None,
) -> str:
    """按语言选择马名（英文模式优先英文名）。"""
    prefer_en = lang == "en"
    name_en = (
        record.get("horse_name_en")
        or record.get("name_en")
        or ""
    )
    if isinstance(name_en, str):
        name_en = name_en.strip()
    else:
        name_en = str(name_en or "").strip()

    name_zh = (
        record.get("horse_name_zh")
        or record.get("horse_name")
        or record.get("name_zh")
        or ""
    )
    if isinstance(name_zh, str):
        name_zh = name_zh.strip()
    else:
        name_zh = str(name_zh or "").strip()

    horse_id = record.get("horse_id")
    if name_lookup and horse_id:
        info = name_lookup.get(str(horse_id), {})
        if not name_en:
            name_en = (info.get("name_en") or "").strip()
        if not name_zh:
            name_zh = (info.get("name_zh") or "").strip()

    if prefer_en and name_en:
        return name_en
    return name_zh or name_en or "-"


@dataclass
class HorseProbability:
    """马匹概率数据"""
    horse_no: int
    horse_name: str
    win_prob: float      # 胜率 (跑第一的概率)
    place_prob: float    # 入Q率 (跑入前二的概率)
    show_prob: float     # 入T率 (跑入前三的概率)


@dataclass
class BettingRecommendation:
    """投注建议"""
    type: str            # 'WIN', 'PLA', 'QIN', 'TRI', 'TCE'
    description: str     # 描述文字
    content: str         # 具体内容 (如 '8号', '8号+5号')
    odds: float          # 赔率
    ev: float            # 期望值
    roi: float           # 预期ROI (%)
    risk_level: str      # '低', '中', '高'
    reason: str          # 推荐理由


class BettingStrategyEngine:
    """AI投注策略引擎"""
    
    def __init__(self):
        self.weights = {
            "win_prob": 0.50,   # 胜率权重
            "place_prob": 0.30, # 入Q率权重
            "show_prob": 0.20   # 入T率权重
        }
    
    def scores_to_probabilities(self, scores: List[float], temperature: float = 0.8) -> List[float]:
        """
        将评分转换为概率 (Softmax)
        参数:
            scores: 综合评分列表
            temperature: 温度参数，值越小概率分布越陡峭
        返回:
            概率列表，总和为1
        """
        if not scores:
            return []
        
        max_score = max(scores)
        exp_scores = [np.exp((s - max_score) / temperature) for s in scores]
        sum_exp = sum(exp_scores)
        if sum_exp == 0:
            return [1.0 / len(scores)] * len(scores)
        return [e / sum_exp for e in exp_scores]
    
    def calculate_ev(self, probability: float, odds: float) -> float:
        """
        计算期望值 (Expected Value)
        EV = (概率 × 赔率) - 1
        返回 > 0 表示正期望值
        """
        if odds <= 0 or probability <= 0:
            return -1
        return (probability * odds) - 1
    
    def calculate_roi(self, ev: float) -> float:
        """计算预期ROI (%)"""
        return ev * 100
    
    def get_horse_probabilities(
        self,
        scores: List[float],
        names: List[str],
        horse_nos: Optional[List] = None,
    ) -> List[HorseProbability]:
        """
        从评分获取马匹各项概率
        参数:
            scores: 各马匹综合评分
            names: 各马匹名称
        返回:
            HorseProbability 列表
        """
        # 1. 胜率 (跑第一)
        win_probs = self.scores_to_probabilities(scores)
        
        # 2. 入Q率 (跑入前二) - 用排名第二的Softmax概率加权
        place_probs = []
        for i in range(len(scores)):
            # 估算: 跑入前二的概率 ≈ 胜率 + 跑第二的概率
            # 简化算法: 该马胜率 × 2 (因为前两名概率较高)
            place_prob = min(win_probs[i] * 2.5, 0.85)
            place_probs.append(place_prob)
        
        # 3. 入T率 (跑入前三)
        show_probs = []
        for i in range(len(scores)):
            # 估算: 跑入前三的概率 ≈ 胜率 × 4
            show_prob = min(win_probs[i] * 4, 0.95)
            show_probs.append(show_prob)
        
        # 归一化确保合理性
        total_place = sum(place_probs)
        if total_place > 1:
            place_probs = [p / total_place for p in place_probs]
        
        total_show = sum(show_probs)
        if total_show > 1:
            show_probs = [p / total_show for p in show_probs]
        
        results = []
        for i, name in enumerate(names):
            hno = horse_nos[i] if horse_nos and i < len(horse_nos) else (i + 1)
            display_name = format_horse_display(name, hno)
            results.append(HorseProbability(
                horse_no=hno,
                horse_name=display_name,
                win_prob=round(win_probs[i] * 100, 1),
                place_prob=round(place_probs[i] * 100, 1),
                show_prob=round(show_probs[i] * 100, 1)
            ))
        
        return results
    
    def recommend_win(self, probs: List[HorseProbability], odds_win: List[float]) -> List[BettingRecommendation]:
        """
        推荐独赢 (WIN)
        按期望值排序，返回 Top 3
        """
        recommendations = []
        
        for prob, odds in zip(probs, odds_win):
            if odds is None or odds <= 0:
                continue
            
            # 胜率概率 (% 转小数)
            win_prob = prob.win_prob / 100
            ev = self.calculate_ev(win_prob, odds)
            
            if ev > 0.10:  # 只推荐正期望值且 > 10%
                roi = self.calculate_roi(ev)
                risk = "低" if win_prob > 0.3 else "中" if win_prob > 0.15 else "高"
                
                recommendations.append(BettingRecommendation(
                    type="WIN",
                    description=f"獨贏 - {prob.horse_name}",
                    content=f"{prob.horse_name}",
                    odds=odds,
                    ev=ev,
                    roi=roi,
                    risk_level=risk,
                    reason=f"AI勝率{prob.win_prob:.0f}%，賠率{odds}倍，期望值{ev:+.2f}"
                ))
        
        # 按期望值降序排序
        recommendations.sort(key=lambda x: x.ev, reverse=True)
        return recommendations[:3]
    
    def recommend_place(self, probs: List[HorseProbability], odds_place: List[float]) -> List[BettingRecommendation]:
        """
        推荐位置 (PLACE)
        跑入前三的概率最高
        """
        recommendations = []
        
        for prob, odds in zip(probs, odds_place):
            if odds is None or odds <= 0:
                continue
            
            show_prob = prob.show_prob / 100
            ev = self.calculate_ev(show_prob, odds)
            
            if ev > 0.05:  # 位置彩池门槛较低
                roi = self.calculate_roi(ev)
                risk = "低"
                
                recommendations.append(BettingRecommendation(
                    type="PLA",
                    description=f"位置 - {prob.horse_name}",
                    content=f"{prob.horse_name}",
                    odds=odds,
                    ev=ev,
                    roi=roi,
                    risk_level=risk,
                    reason=f"入三甲概率{prob.show_prob:.0f}%，賠率{odds}倍"
                ))
        
        recommendations.sort(key=lambda x: x.ev, reverse=True)
        return recommendations[:2]
    
    def recommend_qin(self, probs: List[HorseProbability], odds_qin: Dict[str, float]) -> List[BettingRecommendation]:
        """
        推荐连赢 (QIN)
        组合概率 = 马A胜率 × 马B胜率 × 2
        """
        recommendations = []
        n = len(probs)
        
        for i in range(n):
            for j in range(i + 1, n):
                hno_i = probs[i].horse_no
                hno_j = probs[j].horse_no
                combo_key = f"{hno_i},{hno_j}"
                odds = odds_qin.get(combo_key)
                if odds is None or odds <= 0:
                    combo_key_alt = f"{hno_j},{hno_i}"
                    odds = odds_qin.get(combo_key_alt)
                if odds is None or odds <= 0:
                    continue
                
                # 组合概率 (两马包揽前二)
                combo_prob = (probs[i].win_prob / 100) * (probs[j].win_prob / 100) * 2
                ev = self.calculate_ev(combo_prob, odds)
                
                if ev > 0.10:
                    roi = self.calculate_roi(ev)
                    risk = "中"
                    
                    recommendations.append(BettingRecommendation(
                        type="QIN",
                        description=f"連贏 - {probs[i].horse_name} + {probs[j].horse_name}",
                        content=f"{probs[i].horse_name} + {probs[j].horse_name}",
                        odds=odds,
                        ev=ev,
                        roi=roi,
                        risk_level=risk,
                        reason=f"組合概率{combo_prob*100:.1f}%，賠率{odds}倍"
                    ))
        
        recommendations.sort(key=lambda x: x.ev, reverse=True)
        return recommendations[:3]
    
    def recommend_tri(self, probs: List[HorseProbability], odds_tri: Dict[str, float]) -> List[BettingRecommendation]:
        """
        推荐单T (TRI)
        前三名组合 (顺序不限)
        """
        recommendations = []
        n = len(probs)
        
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    nums = [probs[i].horse_no, probs[j].horse_no, probs[k].horse_no]
                    combo_key = ",".join(str(x) for x in nums)
                    odds = odds_tri.get(combo_key)
                    if odds is None or odds <= 0:
                        continue
                    
                    # 组合概率估算
                    combo_prob = (probs[i].win_prob / 100) * (probs[j].win_prob / 100) * (probs[k].win_prob / 100) * 6
                    ev = self.calculate_ev(combo_prob, odds)
                    
                    if ev > 0.15:
                        roi = self.calculate_roi(ev)
                        risk = "高"
                        
                        recommendations.append(BettingRecommendation(
                            type="TRI",
                            description=f"單T - {probs[i].horse_name} + {probs[j].horse_name} + {probs[k].horse_name}",
                            content=f"{probs[i].horse_name} + {probs[j].horse_name} + {probs[k].horse_name}",
                            odds=odds,
                            ev=ev,
                            roi=roi,
                            risk_level=risk,
                            reason=f"組合概率{combo_prob*100:.2f}%，賠率{odds}倍"
                        ))
        
        recommendations.sort(key=lambda x: x.ev, reverse=True)
        return recommendations[:2]
    
    def generate_all_recommendations(
        self,
        scores: List[float],
        horse_names: List[str],
        odds_win: List[float],
        odds_place: List[float],
        odds_qin: Dict[str, float],
        odds_tri: Dict[str, float],
        horse_nos: Optional[List] = None,
    ) -> Dict[str, List[BettingRecommendation]]:
        """
        生成所有彩池的投注建议
        返回: {
            'win': [...],
            'place': [...],
            'qin': [...],
            'tri': [...]
        }
        """
        # 1. 计算概率
        probs = self.get_horse_probabilities(scores, horse_names, horse_nos=horse_nos)
        
        # 2. 生成各彩池建议
        win_recs = self.recommend_win(probs, odds_win)
        place_recs = self.recommend_place(probs, odds_place)
        qin_recs = self.recommend_qin(probs, odds_qin)
        tri_recs = self.recommend_tri(probs, odds_tri)
        
        return {
            'win': win_recs,
            'place': place_recs,
            'qin': qin_recs,
            'tri': tri_recs
        }


def get_odds_qin_from_db(race_date: str, race_no: int) -> Dict[str, float]:
    """
    从 odds_history 获取连赢赔率
    返回: {'1,2': 15.5, '1,3': 22.0, ...}
    """
    try:
        from supabase import create_client
        import streamlit as st
        
        supabase_url = st.secrets.get("SUPABASE_STOCK_URL", "")
        supabase_key = st.secrets.get("SUPABASE_STOCK_SECRET_KEY", "")
        
        if not supabase_url or not supabase_key:
            return {}
        
        supabase = create_client(supabase_url, supabase_key)
        
        # 查询 QIN 赔率
        response = supabase.table('odds_history')\
            .select('combination, odds_value')\
            .eq('race_date', race_date)\
            .eq('race_no', race_no)\
            .eq('odds_type', 'QIN')\
            .execute()
        
        odds_qin = {}
        if response.data:
            for item in response.data:
                combo = item.get('combination')
                odds = item.get('odds_value')
                if combo and odds:
                    odds_qin[combo] = float(odds)
        
        return odds_qin
        
    except Exception as e:
        print(f"获取连赢赔率失败: {e}")
        return {}


def get_odds_tri_from_db(race_date: str, race_no: int) -> Dict[str, float]:
    """
    从 odds_history 获取单T赔率
    返回: {'1,2,3': 150.0, ...}
    """
    try:
        from supabase import create_client
        import streamlit as st
        
        supabase_url = st.secrets.get("SUPABASE_STOCK_URL", "")
        supabase_key = st.secrets.get("SUPABASE_STOCK_SECRET_KEY", "")
        
        if not supabase_url or not supabase_key:
            return {}
        
        supabase = create_client(supabase_url, supabase_key)
        
        response = supabase.table('odds_history')\
            .select('combination, odds_value')\
            .eq('race_date', race_date)\
            .eq('race_no', race_no)\
            .eq('odds_type', 'TRI')\
            .execute()
        
        odds_tri = {}
        if response.data:
            for item in response.data:
                combo = item.get('combination')
                odds = item.get('odds_value')
                if combo and odds:
                    odds_tri[combo] = float(odds)
        
        return odds_tri
        
    except Exception as e:
        print(f"获取单T赔率失败: {e}")
        return {}
