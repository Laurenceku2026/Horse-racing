"""
过关投注推荐器
功能：
- 支持用户选择2-6场赛事
- AI为每场推荐高分马匹
- 计算过关赔率和期望值
- 推荐最优过关组合（2x1, 3x4, 4x11等）
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from itertools import combinations

from betting_strategy_engine import format_horse_display


@dataclass
class RaceSelection:
    """单场选择"""
    race_date: str
    race_no: int
    venue: str
    selected_horse_no: int
    horse_name: str
    win_prob: float      # 胜率概率 (%)
    odds: float          # 独赢赔率


@dataclass
class ParlayRecommendation:
    """过关推荐"""
    parlay_type: str        # '2x1', '3x4', '4x11' 等
    num_legs: int           # 关数
    num_bets: int           # 注数
    selections: List[RaceSelection]  # 每关的选择
    total_odds: float       # 总赔率（单注）
    combined_prob: float    # 联合概率 (%)
    ev: float               # 期望值
    roi: float              # 预期ROI (%)
    total_stake: float      # 总投注额
    expected_return: float  # 预期回报
    risk_level: str         # 风险等级


class ParlayRecommender:
    """过关投注推荐器"""
    
    def __init__(self):
        # 过关方式配置
        self.parlay_configs = {
            '2x1': {'num_legs': 2, 'num_bets': 1, 'description': '2串1 (1注)'},
            '2x3': {'num_legs': 2, 'num_bets': 3, 'description': '2串3 (3注) - 包含2场单关'},
            '3x1': {'num_legs': 3, 'num_bets': 1, 'description': '3串1 (1注)'},
            '3x4': {'num_legs': 3, 'num_bets': 4, 'description': '3串4 (4注) - 包含3个2串1 + 1个3串1'},
            '3x7': {'num_legs': 3, 'num_bets': 7, 'description': '3串7 (7注) - 包含3个单关 + 3个2串1 + 1个3串1'},
            '4x1': {'num_legs': 4, 'num_bets': 1, 'description': '4串1 (1注)'},
            '4x11': {'num_legs': 4, 'num_bets': 11, 'description': '4串11 (11注) - 包含6个2串1 + 4个3串1 + 1个4串1'},
            '5x1': {'num_legs': 5, 'num_bets': 1, 'description': '5串1 (1注)'},
            '5x26': {'num_legs': 5, 'num_bets': 26, 'description': '5串26 (26注) - 包含各种组合'},
            '6x1': {'num_legs': 6, 'num_bets': 1, 'description': '6串1 (1注)'},
            '6x42': {'num_legs': 6, 'num_bets': 42, 'description': '6串42 (42注) - 包含各种组合'},
        }
        
        # 默认每注金额
        self.default_stake_per_bet = 10
    
    def calculate_parlay_odds(self, odds_list: List[float]) -> float:
        """计算过关总赔率（各关赔率相乘）"""
        result = 1.0
        for odd in odds_list:
            if odd > 0:
                result *= odd
        return round(result, 2)
    
    def calculate_parlay_prob(self, prob_list: List[float]) -> float:
        """计算过关联合概率（各关概率相乘）"""
        result = 1.0
        for prob in prob_list:
            if prob > 0:
                result *= (prob / 100)  # 输入是百分比
        return round(result * 100, 2)  # 输出百分比
    
    def calculate_ev(self, total_odds: float, combined_prob: float) -> float:
        """计算过关期望值"""
        prob_decimal = combined_prob / 100
        return (prob_decimal * total_odds) - 1
    
    def calculate_roi(self, ev: float) -> float:
        """计算预期ROI (%)"""
        return ev * 100
    
    def get_top_horses_for_race(
        self,
        scores: List[float],
        horse_names: List[str],
        odds: List[float],
        top_n: int = 3,
        horse_nos: Optional[List] = None,
    ) -> List[Dict]:
        """
        获取一场比赛的前N名推荐马匹
        
        参数:
            scores: 各马匹评分
            horse_names: 各马匹名称
            odds: 各马匹独赢赔率
            top_n: 返回前N匹
        
        返回:
            按评分排序的马匹列表
        """
        horses = []
        for i, (score, name, odd) in enumerate(zip(scores, horse_names, odds)):
            if odd and odd > 0:
                hno = horse_nos[i] if horse_nos and i < len(horse_nos) else (i + 1)
                horses.append({
                    'horse_no': hno,
                    'horse_name': name,
                    'score': score,
                    'odds': odd,
                    'win_prob': min(score * 0.8, 85)  # 简化：评分转换为胜率
                })
        
        # 按评分排序
        horses.sort(key=lambda x: x['score'], reverse=True)
        return horses[:top_n]
    
    def recommend_for_single_race(
        self,
        race_date: str,
        race_no: int,
        venue: str,
        scores: List[float],
        horse_names: List[str],
        odds: List[float],
        top_n: int = 2,
        horse_nos: Optional[List] = None,
    ) -> List[RaceSelection]:
        """
        为单场比赛推荐可选马匹
        
        返回: 前 top_n 匹马的 RaceSelection 列表
        """
        top_horses = self.get_top_horses_for_race(scores, horse_names, odds, top_n, horse_nos)
        
        selections = []
        for horse in top_horses:
            selections.append(RaceSelection(
                race_date=race_date,
                race_no=race_no,
                venue=venue,
                selected_horse_no=horse['horse_no'],
                horse_name=horse['horse_name'],
                win_prob=horse['win_prob'],
                odds=horse['odds']
            ))
        
        return selections
    
    def recommend_parlay(
        self,
        race_selections: List[List[RaceSelection]],  # 每场有多个可选马匹
        num_legs: int = 3,
        parlay_type: str = '3x4'
    ) -> List[ParlayRecommendation]:
        """
        推荐过关组合
        
        参数:
            race_selections: 每场比赛的可选马匹列表
            num_legs: 选择几场比赛过关
            parlay_type: 过关方式
        
        返回:
            按期望值排序的推荐列表
        """
        if len(race_selections) < num_legs:
            return []
        
        config = self.parlay_configs.get(parlay_type)
        if not config:
            return []
        
        recommendations = []
        
        # 生成所有可能的组合
        # 从可选场次中选择 num_legs 场
        for combo_indices in combinations(range(len(race_selections)), num_legs):
            # 获取每场的首选马（评分最高的）
            selections_for_parlay = []
            odds_list = []
            prob_list = []
            
            for idx in combo_indices:
                if race_selections[idx]:
                    best_horse = race_selections[idx][0]  # 取该场首选
                    selections_for_parlay.append(best_horse)
                    odds_list.append(best_horse.odds)
                    prob_list.append(best_horse.win_prob)
                else:
                    break
            
            if len(selections_for_parlay) == num_legs:
                total_odds = self.calculate_parlay_odds(odds_list)
                combined_prob = self.calculate_parlay_prob(prob_list)
                ev = self.calculate_ev(total_odds, combined_prob)
                roi = self.calculate_roi(ev)
                total_stake = config['num_bets'] * self.default_stake_per_bet
                expected_return = total_stake * (1 + roi / 100) if roi > 0 else total_stake * total_odds / config['num_bets']
                
                # 风险等级判断
                if combined_prob > 30:
                    risk_level = '低'
                elif combined_prob > 15:
                    risk_level = '中'
                else:
                    risk_level = '高'
                
                recommendations.append(ParlayRecommendation(
                    parlay_type=parlay_type,
                    num_legs=num_legs,
                    num_bets=config['num_bets'],
                    selections=selections_for_parlay,
                    total_odds=total_odds,
                    combined_prob=combined_prob,
                    ev=round(ev, 4),
                    roi=round(roi, 2),
                    total_stake=total_stake,
                    expected_return=round(expected_return, 2),
                    risk_level=risk_level
                ))
        
        # 按期望值排序
        recommendations.sort(key=lambda x: x.ev, reverse=True)
        return recommendations[:5]  # 返回前5个推荐
    
    def get_parlay_recommendations_for_schedule(
        self,
        races_data: List[Dict],  # 每场比赛的数据 {scores, horse_names, odds, race_date, race_no, venue}
        max_legs: int = 3,
        top_parlay_types: List[str] = None
    ) -> Dict:
        """
        为整个赛程生成过关推荐
        
        参数:
            races_data: 所有比赛的数据列表
            max_legs: 最大过关关数 (2-6)
            top_parlay_types: 要推荐的过关方式列表
        
        返回:
            各过关方式的推荐
        """
        if top_parlay_types is None:
            top_parlay_types = ['2x1', '3x4', '4x11']
        
        # 为每场比赛生成可选马匹
        all_selections = []
        for race in races_data:
            selections = self.recommend_for_single_race(
                race_date=race['race_date'],
                race_no=race['race_no'],
                venue=race['venue'],
                scores=race['scores'],
                horse_names=race['horse_names'],
                odds=race['odds'],
                top_n=2,
                horse_nos=race.get('horse_nos'),
            )
            all_selections.append(selections)
        
        results = {}
        
        for parlay_type in top_parlay_types:
            config = self.parlay_configs.get(parlay_type)
            if config and config['num_legs'] <= max_legs:
                recommendations = self.recommend_parlay(
                    race_selections=all_selections,
                    num_legs=config['num_legs'],
                    parlay_type=parlay_type
                )
                if recommendations:
                    results[parlay_type] = recommendations
        
        return results


def format_parlay_display(rec: ParlayRecommendation) -> str:
    """格式化过关推荐显示"""
    legs_text = []
    for sel in rec.selections:
        legs_text.append(
            f"第{sel.race_no}場 {format_horse_display(sel.horse_name, sel.selected_horse_no)}"
        )

    return f"{' → '.join(legs_text)}"
