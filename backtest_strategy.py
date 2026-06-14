"""
策略回测系统
功能：
- 基于历史数据和赔率快照回测投注策略
- 计算各彩池的ROI、胜率、夏普比率等指标
- 支持自定义回测参数（彩池类型、期望值门槛等）
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class BacktestResult:
    """单场回测结果"""
    race_date: str
    race_no: int
    recommendation_type: str      # WIN, QIN, TRI
    recommendation_content: str   # 具体内容
    odds: float                    # 使用的赔率
    ev_calculated: float           # 计算的期望值
    actual_hit: bool               # 是否命中
    actual_return: float           # 实际回报（投注10元）
    profit: float                  # 盈亏


@dataclass
class BacktestSummary:
    """回测汇总"""
    total_bets: int                # 总投注次数
    hit_count: int                 # 命中次数
    win_rate: float                # 胜率 (%)
    total_stake: float             # 总投入
    total_return: float            # 总回报
    roi: float                     # 投资回报率 (%)
    avg_odds: float                # 平均赔率
    avg_ev: float                  # 平均期望值
    sharpe_ratio: float            # 夏普比率
    max_drawdown: float            # 最大回撤 (%)
    details: List[BacktestResult] = field(default_factory=list)


class StrategyBacktester:
    """策略回测器"""
    
    def __init__(self):
        self.daily_returns = []  # 用于计算夏普比率
    
    def calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.025) -> float:
        """
        计算夏普比率
        参数:
            returns: 每日收益率列表 (%)
            risk_free_rate: 无风险利率 (年化)
        """
        if len(returns) < 2:
            return 0
        
        returns_array = np.array(returns)
        daily_rf = (1 + risk_free_rate) ** (1/365) - 1
        excess_returns = returns_array - daily_rf
        
        if np.std(excess_returns) == 0:
            return 0
        
        sharpe = (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(252)
        return round(sharpe, 2)
    
    def calculate_max_drawdown(self, values: List[float]) -> float:
        """计算最大回撤"""
        if len(values) < 2:
            return 0
        
        peak = values[0]
        max_dd = 0
        
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        return round(max_dd, 2)
    
    def backtest_win_strategy(
        self,
        race_dates: List[str],
        get_scores_func,      # 获取评分的函数
        get_odds_func,        # 获取赔率的函数
        get_result_func,      # 获取实际结果的函数
        min_ev_threshold: float = 0.10,
        stake_per_bet: float = 100
    ) -> BacktestSummary:
        """
        回测独赢策略
        
        策略: 当期望值 > 阈值时，投注期望值最高的马匹
        """
        results = []
        daily_profits = []
        
        for race_date in race_dates:
            # 1. 获取该日期的所有场次
            races = get_races_on_date(race_date)
            
            for race in races:
                race_no = race['race_no']
                
                # 2. 获取当时的AI评分（使用比赛日期前的数据）
                scores = get_scores_func(race_date, race_no)
                if not scores:
                    continue
                
                # 3. 获取赔率
                odds = get_odds_func(race_date, race_no, 'WIN')
                if not odds:
                    continue
                
                # 4. 计算概率和期望值
                engine = self._get_engine()
                probs = engine.scores_to_probabilities(scores)
                
                best_ev = -1
                best_horse = None
                best_odds = None
                
                for i, (prob, odd) in enumerate(zip(probs, odds)):
                    if odd and odd > 0:
                        ev = engine.calculate_ev(prob, odd)
                        if ev > best_ev and ev > min_ev_threshold:
                            best_ev = ev
                            best_horse = i + 1
                            best_odds = odd
                
                # 5. 模拟投注
                if best_horse and best_odds:
                    # 获取实际结果
                    actual_winner = get_result_func(race_date, race_no)
                    actual_hit = (actual_winner == best_horse)
                    
                    if actual_hit:
                        actual_return = stake_per_bet * best_odds
                        profit = actual_return - stake_per_bet
                    else:
                        actual_return = 0
                        profit = -stake_per_bet
                    
                    results.append(BacktestResult(
                        race_date=race_date,
                        race_no=race_no,
                        recommendation_type='WIN',
                        recommendation_content=f"{best_horse}號",
                        odds=best_odds,
                        ev_calculated=best_ev,
                        actual_hit=actual_hit,
                        actual_return=actual_return,
                        profit=profit
                    ))
                    
                    daily_profits.append(profit)
        
        # 计算汇总指标
        return self._calculate_summary(results, daily_profits, stake_per_bet)
    
    def backtest_qin_strategy(
        self,
        race_dates: List[str],
        get_scores_func,
        get_odds_func,
        get_result_func,
        min_ev_threshold: float = 0.10,
        stake_per_bet: float = 100
    ) -> BacktestSummary:
        """
        回测连赢策略
        
        策略: 当组合期望值 > 阈值时，投注期望值最高的连赢组合
        """
        results = []
        daily_profits = []
        
        for race_date in race_dates:
            races = get_races_on_date(race_date)
            
            for race in races:
                race_no = race['race_no']
                
                # 获取评分和赔率
                scores = get_scores_func(race_date, race_no)
                if not scores:
                    continue
                
                odds_qin = get_odds_func(race_date, race_no, 'QIN')
                if not odds_qin:
                    continue
                
                # 计算概率
                engine = self._get_engine()
                probs = engine.scores_to_probabilities(scores)
                
                best_ev = -1
                best_combo = None
                best_odds = None
                
                # 遍历所有连赢组合
                n = len(probs)
                for i in range(n):
                    for j in range(i + 1, n):
                        combo_key = f"{i+1},{j+1}"
                        odds = odds_qin.get(combo_key)
                        if not odds or odds <= 0:
                            continue
                        
                        # 组合概率
                        combo_prob = probs[i] * probs[j] * 2
                        ev = engine.calculate_ev(combo_prob, odds)
                        
                        if ev > best_ev and ev > min_ev_threshold:
                            best_ev = ev
                            best_combo = combo_key
                            best_odds = odds
                
                # 模拟投注
                if best_combo and best_odds:
                    actual_top2 = get_result_func(race_date, race_no, 'TOP2')
                    actual_hit = (actual_top2 == best_combo or actual_top2 == f"{best_combo.split(',')[1]},{best_combo.split(',')[0]}")
                    
                    if actual_hit:
                        actual_return = stake_per_bet * best_odds
                        profit = actual_return - stake_per_bet
                    else:
                        actual_return = 0
                        profit = -stake_per_bet
                    
                    results.append(BacktestResult(
                        race_date=race_date,
                        race_no=race_no,
                        recommendation_type='QIN',
                        recommendation_content=best_combo,
                        odds=best_odds,
                        ev_calculated=best_ev,
                        actual_hit=actual_hit,
                        actual_return=actual_return,
                        profit=profit
                    ))
                    
                    daily_profits.append(profit)
        
        return self._calculate_summary(results, daily_profits, stake_per_bet)
    
    def _get_engine(self):
        """获取策略引擎实例（避免循环导入）"""
        from betting_strategy_engine import BettingStrategyEngine
        return BettingStrategyEngine()
    
    def _calculate_summary(
        self, 
        results: List[BacktestResult], 
        profits: List[float],
        stake_per_bet: float
    ) -> BacktestSummary:
        """计算回测汇总指标"""
        if not results:
            return BacktestSummary(
                total_bets=0,
                hit_count=0,
                win_rate=0,
                total_stake=0,
                total_return=0,
                roi=0,
                avg_odds=0,
                avg_ev=0,
                sharpe_ratio=0,
                max_drawdown=0,
                details=[]
            )
        
        total_bets = len(results)
        hit_count = sum(1 for r in results if r.actual_hit)
        win_rate = hit_count / total_bets * 100
        
        total_stake = total_bets * stake_per_bet
        total_return = sum(r.actual_return for r in results)
        roi = (total_return - total_stake) / total_stake * 100
        
        avg_odds = np.mean([r.odds for r in results]) if results else 0
        avg_ev = np.mean([r.ev_calculated for r in results]) if results else 0
        
        # 计算累计盈亏曲线
        cumulative = np.cumsum(profits)
        sharpe_ratio = self.calculate_sharpe_ratio(profits)
        max_drawdown = self.calculate_max_drawdown(cumulative)
        
        return BacktestSummary(
            total_bets=total_bets,
            hit_count=hit_count,
            win_rate=round(win_rate, 2),
            total_stake=round(total_stake, 2),
            total_return=round(total_return, 2),
            roi=round(roi, 2),
            avg_odds=round(avg_odds, 2),
            avg_ev=round(avg_ev, 4),
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            details=results
        )


def get_races_on_date(race_date: str) -> List[Dict]:
    """获取指定日期的所有赛事"""
    try:
        from supabase import create_client
        import streamlit as st
        
        supabase_url = st.secrets.get("SUPABASE_STOCK_URL", "")
        supabase_key = st.secrets.get("SUPABASE_STOCK_SECRET_KEY", "")
        
        if not supabase_url or not supabase_key:
            return []
        
        supabase = create_client(supabase_url, supabase_key)
        response = supabase.table('races')\
            .select('race_no, distance')\
            .eq('race_date', race_date)\
            .order('race_no')\
            .execute()
        
        return response.data if response.data else []
        
    except Exception as e:
        print(f"获取赛事失败: {e}")
        return []


def get_historical_scores(race_date: str, race_no: int) -> List[float]:
    """获取历史评分（使用该日期之前的数据）"""
    # 这里需要调用现有的评分系统
    # 简化版：返回模拟数据
    # 实际应用中需要调用 calculate_all_horses_scores
    return [75, 68, 62, 58, 55, 52, 48, 45, 42, 40, 38, 35, 32, 30]

#-------------
def get_historical_odds(race_date: str, race_no: int, odds_type: str):
    """获取历史赔率"""
    try:
        from supabase import create_client
        import streamlit as st
        
        supabase_url = st.secrets.get("SUPABASE_STOCK_URL", "")
        supabase_key = st.secrets.get("SUPABASE_STOCK_SECRET_KEY", "")
        
        if not supabase_url or not supabase_key:
            return {}
        
        supabase = create_client(supabase_url, supabase_key)
        
        if odds_type == 'WIN':
            response = supabase.table('odds_history')\
                .select('horse_no, odds_value')\
                .eq('race_date', race_date)\
                .eq('race_no', race_no)\
                .eq('odds_type', 'WIN')\
                .order('recorded_at', desc=True)\
                .execute()
            
            if response.data:
                odds_dict = {}
                for item in response.data:
                    horse_no = item.get('horse_no')
                    odds = item.get('odds_value')
                    if horse_no and odds:
                        odds_dict[horse_no] = float(odds)
                return odds_dict
            return {}
        
        elif odds_type == 'QIN':
            # 修复：从 combo_odds_v2 表获取连赢赔率
            response = supabase.table('combo_odds_v2')\
                .select('combination, odds_value')\
                .eq('race_date', race_date)\
                .eq('race_no', race_no)\
                .eq('odds_type', 'QIN')\
                .execute()
            
            odds_dict = {}
            if response.data:
                for item in response.data:
                    combo = item.get('combination')
                    odds = item.get('odds_value')
                    if combo and odds:
                        odds_dict[combo] = float(odds)
            return odds_dict
        
        return {}
        
    except Exception as e:
        print(f"获取赔率失败: {e}")
        return {}


def get_historical_result(race_date: str, race_no: int, result_type: str = 'WIN'):
    """获取实际赛果"""
    try:
        from supabase import create_client
        import streamlit as st
        
        supabase_url = st.secrets.get("SUPABASE_STOCK_URL", "")
        supabase_key = st.secrets.get("SUPABASE_STOCK_SECRET_KEY", "")
        
        if not supabase_url or not supabase_key:
            return None
        
        supabase = create_client(supabase_url, supabase_key)
        
        # 从 past_performances 获取结果
        response = supabase.table('past_performances')\
            .select('horse_no, position')\
            .eq('race_date', race_date)\
            .eq('race_no', race_no)\
            .order('position')\
            .execute()
        
        if response.data:
            if result_type == 'WIN':
                # 返回第一名马号
                for r in response.data:
                    if r.get('position') == 1:
                        return r.get('horse_no')
            elif result_type == 'TOP2':
                # 返回前两名组合
                top2 = []
                for r in response.data:
                    if r.get('position') in [1, 2]:
                        top2.append(str(r.get('horse_no')))
                if len(top2) == 2:
                    return f"{top2[0]},{top2[1]}"
        
        return None
        
    except Exception as e:
        print(f"获取赛果失败: {e}")
        return None
