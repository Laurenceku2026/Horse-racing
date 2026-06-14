"""
香港赛马AI分析系统 - 评分引擎模块
文件名: scoring_engine.py
功能: 包含所有评分计算函数，可被主程序导入
版本: v3.0
"""

import numpy as np
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from supabase import create_client

# ==================== 评分权重常量 ====================

# 一级因子权重
LEVEL1_WEIGHTS = {
    "basic": 0.35,      # 基础往绩
    "race": 0.25,       # 场次因素
    "odds": 0.25,       # 赔率因素
    "status": 0.15      # 状态/事件
}

# 基础往绩二级因子权重（占基础往绩的百分比）
BASIC_WEIGHTS = {
    "recent_3_win": 0.34,     # 近3场胜率
    "recent_10_win": 0.23,    # 近10场胜率
    "recent_10_place": 0.17,  # 近10场入Q率
    "same_distance": 0.14,    # 同程胜率
    "trend": 0.12             # 名次趋势
}

# 场次因素二级因子权重（占场次因素的百分比）
RACE_WEIGHTS = {
    "draw": 0.32,        # 档位优势
    "weight_change": 0.24,  # 负磅变化
    "jockey": 0.20,      # 骑师配合
    "same_venue": 0.16,  # 同场地胜率
    "trainer": 0.08      # 练马师状态
}

# 赔率因素二级因子权重（占赔率因素的百分比）
ODDS_WEIGHTS = {
    "win_odds": 0.48,    # 独赢赔率
    "odds_trend": 0.32,  # 赔率变动趋势
    "ev": 0.20           # 预期价值
}

# 状态/事件二级因子权重（占状态/事件的百分比）
STATUS_WEIGHTS = {
    "age": 0.33,         # 马龄因子
    "weight_change": 0.27,  # 体重变化
    "closing": 0.20,     # 冲刺能力
    "incident": 0.20     # 事件报告
}

# 档位分数（内档有利，沙田1000米直路除外）
DRAW_SCORE_INNER = {draw: int(100 - (draw - 1) * (80 / 13)) for draw in range(1, 15)}
DRAW_SCORE_OUTER = {draw: int(20 + (draw - 1) * (80 / 13)) for draw in range(1, 15)}

# 冲刺能力分数
CLOSING_SCORES = {
    "Strong Closer": 100,
    "Closer": 80,
    "Even": 60,
    "Faded": 40,
    "Quitter": 20
}

# 事件报告关键词影响分数（规则匹配，替代DeepSeek）
INCIDENT_IMPACT = {
    # 严重不利
    "流鼻血": -30,
    "心脏": -30,
    "不良于行": -25,
    # 中等不利
    "走外叠": -20,
    "受阻": -15,
    "勒避": -15,
    "失地": -12,
    "出闸笨拙": -10,
    "抢口": -10,
    # 轻微不利
    "碰撞": -5,
    "紧迫": -5,
    # 有利
    "望空": 5,
    "顺利": 5,
    "佳势": 8
}

# 骑师等级分数（基于赛季表现，可后续从数据库动态获取）
JOCKEY_SCORES = {
    "潘頓": 100,
    "布文": 95,
    "田泰安": 85,
    "艾兆禮": 80,
    "潘明輝": 75,
    "何澤堯": 75,
    "巴度": 70,
    "希威森": 70,
    "梁家俊": 65,
    "霍宏聲": 65,
    "班德禮": 60,
    "艾道拿": 60,
    "蔡明紹": 55,
    "周俊樂": 55,
    "金誠剛": 50,
    "楊明綸": 50,
    "鍾易禮": 45,
    "巫顯東": 45,
    "黃智弘": 40,
    "麥文堅": 40,
    "奧爾民": 40,
    "紀仁安": 40
}

# 练马师等级分数
TRAINER_SCORES = {
    "蔡約翰": 100,
    "大衛希斯": 95,
    "姚本輝": 90,
    "告東尼": 90,
    "羅富全": 85,
    "呂健威": 85,
    "沈集成": 80,
    "方嘉柏": 80,
    "伍鵬志": 80,
    "韋達": 75,
    "蘇偉賢": 70,
    "文家良": 70,
    "賀賢": 65,
    "鄭俊偉": 65,
    "葉楚航": 60,
    "徐雨石": 60,
    "黎昭昇": 60,
    "巫偉傑": 55,
    "廖康銘": 55,
    "游達榮": 55,
    "丁冠豪": 50,
    "桂福特": 50,
    "其他": 50
}


# ==================== 马龄计算 ====================

def calculate_horse_age(horse_id: str, race_date: str) -> float:
    """
    计算马匹在比赛时的实时年龄
    
    Args:
        horse_id: 马匹ID，格式 HK_YYYY_XXX
        race_date: 比赛日期，格式 YYYY-MM-DD
    
    Returns:
        实时年龄（岁）
    """
    if not horse_id or not isinstance(horse_id, str):
        return 5.0  # 默认年龄
    
    # 从horse_id提取年份（抵达香港的年份）
    match = re.search(r'HK_(\d{4})_', horse_id)
    if not match:
        return 5.0
    
    arrival_year = int(match.group(1))
    # 抵达香港时通常3岁
    birth_year = arrival_year - 3
    
    race_dt = datetime.strptime(race_date, '%Y-%m-%d')
    
    # 根据南/北半球判断增龄日期
    # 南半球马（澳洲、新西兰等）8月1日增龄，北半球马1月1日增龄
    # 简化处理：统一用1月1日
    age_cutoff = datetime(birth_year + 1, 1, 1)
    
    if race_dt >= age_cutoff:
        age = race_dt.year - birth_year
    else:
        age = race_dt.year - birth_year - 1
    
    return max(3, min(11, age))  # 限制3-11岁


def get_age_factor(age: float) -> float:
    """
    根据年龄返回评分系数
    4-6岁是巅峰期，系数>1
    """
    if 4 <= age <= 5:
        return 1.10  # 巅峰期
    elif age == 6:
        return 1.05  # 仍处巅峰
    elif age == 3:
        return 1.00  # 潜力
    elif age == 7:
        return 0.95  # 下滑
    elif age == 8:
        return 0.85  # 明显下滑
    elif age >= 9:
        return 0.75  # 老将
    else:
        return 1.00


# ==================== 基础往绩评分 ====================

def calculate_recent_win_rate(performances: List[Dict], n: int = 3) -> float:
    """计算最近N场胜率"""
    if not performances:
        return 0
    recent = performances[:n] if len(performances) >= n else performances
    wins = sum(1 for p in recent if p.get('position') == 1)
    return (wins / len(recent)) * 100 if recent else 0


def calculate_recent_place_rate(performances: List[Dict], n: int = 10) -> float:
    """计算最近N场入Q率（前2名）"""
    if not performances:
        return 0
    recent = performances[:n] if len(performances) >= n else performances
    places = sum(1 for p in recent if p.get('position', 0) in [1, 2])
    return (places / len(recent)) * 100 if recent else 0


def calculate_same_distance_win_rate(performances: List[Dict], target_distance: int) -> float:
    """计算同路程胜率"""
    if not performances:
        return 0
    same_dist = [p for p in performances if p.get('distance') == target_distance]
    if not same_dist:
        return 0
    wins = sum(1 for p in same_dist if p.get('position') == 1)
    return (wins / len(same_dist)) * 100


def calculate_trend_score(performances: List[Dict]) -> float:
    """计算名次趋势分数"""
    if len(performances) < 3:
        return 50
    
    recent_3 = performances[:3]
    positions = [p.get('position', 0) for p in recent_3 if p.get('position')]
    
    if len(positions) < 3:
        return 50
    
    # 检查是否持续进步
    if positions[0] > positions[1] > positions[2]:
        return 100
    # 检查是否持续退步
    elif positions[0] < positions[1] < positions[2]:
        return 30
    # 检查是否稳定
    elif abs(positions[0] - positions[2]) <= 2:
        return 70
    else:
        return 50


def calculate_basic_score(performances: List[Dict], target_distance: int) -> float:
    """
    计算基础往绩评分（0-100）
    """
    recent_3_win = calculate_recent_win_rate(performances, 3)
    recent_10_win = calculate_recent_win_rate(performances, 10)
    recent_10_place = calculate_recent_place_rate(performances, 10)
    same_dist_win = calculate_same_distance_win_rate(performances, target_distance)
    trend_score = calculate_trend_score(performances)
    
    # 加权计算
    score = (
        recent_3_win * BASIC_WEIGHTS["recent_3_win"] +
        recent_10_win * BASIC_WEIGHTS["recent_10_win"] +
        recent_10_place * BASIC_WEIGHTS["recent_10_place"] +
        same_dist_win * BASIC_WEIGHTS["same_distance"] +
        trend_score * BASIC_WEIGHTS["trend"]
    )
    
    return round(score, 2)


# ==================== 场次因素评分 ====================

def calculate_draw_score(draw: int, venue: str, distance: int) -> float:
    """
    计算档位优势分数
    沙田1000米直路赛外档有利，其他路程内档有利
    """
    if draw is None or draw < 1 or draw > 14:
        return 50
    
    if venue == "ST" and distance == 1000:
        score = DRAW_SCORE_OUTER.get(draw, 50)
    else:
        score = DRAW_SCORE_INNER.get(draw, 50)
    
    return score


def calculate_jockey_score(jockey_name: str) -> float:
    """计算骑师评分"""
    if not jockey_name:
        return 50
    return JOCKEY_SCORES.get(jockey_name, 50)


def calculate_trainer_score(trainer_name: str) -> float:
    """计算练马师评分"""
    if not trainer_name:
        return 50
    return TRAINER_SCORES.get(trainer_name, 50)


def calculate_same_venue_win_rate(performances: List[Dict], venue: str) -> float:
    """计算同场地胜率"""
    if not performances:
        return 0
    same_venue = [p for p in performances if p.get('venue') == venue]
    if not same_venue:
        return 0
    wins = sum(1 for p in same_venue if p.get('position') == 1)
    return (wins / len(same_venue)) * 100

#--------------
def calculate_race_score(
    performances: List[Dict],
    venue: str,
    distance: int,
    draw: int,
    jockey: str,
    trainer: str
) -> float:
    """
    计算场次因素评分（0-100）
    """
    draw_score = calculate_draw_score(draw, venue, distance)
    jockey_score = calculate_jockey_score(jockey)
    trainer_score = calculate_trainer_score(trainer)
    same_venue_rate = calculate_same_venue_win_rate(performances, venue)
    
    score = (
        draw_score * RACE_WEIGHTS["draw"] +
        jockey_score * RACE_WEIGHTS["jockey"] +
        trainer_score * RACE_WEIGHTS["trainer"] +
        same_venue_rate * RACE_WEIGHTS["same_venue"]
    )
    
    return round(score, 2)


# ==================== 赔率因素评分 ====================

def calculate_odds_score(odds: float) -> float:
    """
    计算赔率评分
    赔率越低分数越高：1.5倍→100分，99倍→0分
    """
    if odds is None or odds <= 0:
        return 50
    
    odds = min(odds, 99)  # 限制最大99倍
    score = 100 * (1 - (odds - 1) / 98)
    return max(0, min(100, score))


# ==================== 状态/事件评分 ====================

def calculate_weight_change_score(body_weight: int, past_weights: List[int]) -> float:
    """
    计算体重变化评分
    与最近一次出赛体重比较
    """
    if not body_weight or not past_weights:
        return 70
    
    latest_weight = past_weights[0] if past_weights else None
    if not latest_weight:
        return 70
    
    change = abs(body_weight - latest_weight)
    
    if change <= 10:
        return 100
    elif change <= 20:
        return 80
    elif change <= 30:
        return 55
    elif change <= 40:
        return 35
    else:
        return 20


def calculate_closing_score(closing_profile: str) -> float:
    """计算冲刺能力评分"""
    if not closing_profile:
        return 60
    return CLOSING_SCORES.get(closing_profile, 60)


def analyze_incident(incident_text: str) -> int:
    """
    分析事件报告，返回影响分数
    规则匹配，无需API调用
    """
    if not incident_text or incident_text == '无特别报告。':
        return 0
    
    total = 0
    for keyword, impact in INCIDENT_IMPACT.items():
        if keyword in incident_text:
            total += impact
    
    return max(-20, min(20, total))


def calculate_status_score(
    horse_id: str,
    race_date: str,
    body_weight: int,
    past_weights: List[int],
    closing_profile: str,
    incident: str
) -> float:
    """
    计算状态/事件评分（0-100）
    """
    # 马龄因子
    age = calculate_horse_age(horse_id, race_date)
    age_factor = get_age_factor(age)
    age_score = age_factor * 100
    
    # 体重变化
    weight_score = calculate_weight_change_score(body_weight, past_weights)
    
    # 冲刺能力
    closing_score = calculate_closing_score(closing_profile)
    
    # 事件影响（转换为0-100分制）
    incident_impact = analyze_incident(incident)
    incident_score = 50 + incident_impact  # 基准50分，影响±20
    
    score = (
        age_score * STATUS_WEIGHTS["age"] +
        weight_score * STATUS_WEIGHTS["weight_change"] +
        closing_score * STATUS_WEIGHTS["closing"] +
        incident_score * STATUS_WEIGHTS["incident"]
    )
    
    return round(score, 2)


# ==================== 综合评分 ====================

def calculate_overall_score(
    basic_score: float,
    race_score: float,
    odds_score: float,
    status_score: float
) -> float:
    """
    计算综合评分（0-100）
    """
    raw_score = (
        basic_score * LEVEL1_WEIGHTS["basic"] +
        race_score * LEVEL1_WEIGHTS["race"] +
        odds_score * LEVEL1_WEIGHTS["odds"] +
        status_score * LEVEL1_WEIGHTS["status"]
    )
    
    return round(raw_score, 2)


# ==================== 胜率转换 ====================

def softmax_probabilities(scores: List[float], temperature: float = 0.8) -> List[float]:
    """
    将评分转换为胜率概率
    """
    if not scores:
        return []
    
    # 减去最大值防止溢出
    max_score = max(scores)
    exp_scores = [np.exp((s - max_score) / temperature) for s in scores]
    total = sum(exp_scores)
    
    if total == 0:
        return [1.0 / len(scores)] * len(scores)
    
    return [e / total for e in exp_scores]


# ==================== 批量获取马匹往绩 ====================

def get_horse_performances_batch(supabase, horse_ids: List[str], limit: int = 10) -> Dict[str, List[Dict]]:
    """
    批量获取多匹马的历史往绩
    """
    if not horse_ids:
        return {}
    
    try:
        # 构建查询
        response = supabase.table('past_performances_v2')\
            .select('*')\
            .in_('horse_id', horse_ids)\
            .order('race_date', desc=True)\
            .execute()
        
        data = response.data if response.data else []
        
        # 按horse_id分组
        cache = {}
        for record in data:
            hid = record.get('horse_id')
            if not hid:
                continue
            if hid not in cache:
                cache[hid] = []
            cache[hid].append(record)
        
        return cache
        
    except Exception as e:
        print(f"批量获取马匹往绩失败: {e}")
        return {}


# ==================== 单马评分计算 ====================

def calculate_horse_full_score(
    supabase,
    horse_id: str,
    race_date: str,
    venue: str,
    race_no: int,
    distance: int,
    draw: int,
    jockey: str,
    trainer: str,
    body_weight: int,
    closing_profile: str,
    incident: str,
    odds_win: float
) -> Dict:
    """
    计算单匹马的完整评分
    """
    # 获取历史往绩
    perf_cache = get_horse_performances_batch(supabase, [horse_id], limit=10)
    performances = perf_cache.get(horse_id, [])
    
    # 提取历史体重列表
    past_weights = [p.get('body_weight') for p in performances if p.get('body_weight')]
    
    # 计算各维度评分
    basic_score = calculate_basic_score(performances, distance)
    race_score = calculate_race_score(performances, venue, distance, draw, jockey, trainer)
    odds_score = calculate_odds_score(odds_win)
    status_score = calculate_status_score(horse_id, race_date, body_weight, past_weights, closing_profile, incident)
    
    # 综合评分
    overall_score = calculate_overall_score(basic_score, race_score, odds_score, status_score)
    
    return {
        "horse_id": horse_id,
        "basic_score": basic_score,
        "race_score": race_score,
        "odds_score": odds_score,
        "status_score": status_score,
        "overall_score": overall_score
    }


# ==================== 单场赛事评分计算 ====================

def calculate_race_scores(
    supabase,
    race_date: str,
    venue: str,
    race_no: int,
    runners: List[Dict]
) -> Tuple[List[Dict], List[float]]:
    """
    计算一场赛事所有马匹的评分和胜率
    
    Args:
        supabase: Supabase客户端
        race_date: 赛事日期
        venue: 场地
        race_no: 场次
        runners: 出赛马匹列表，每匹包含 horse_id, horse_no, draw, jockey, trainer, 
                 body_weight, closing_profile, incident, odds_win
    
    Returns:
        (scores_list, probabilities_list)
    """
    if not runners:
        return [], []
    
    # 收集所有horse_id
    horse_ids = [r.get('horse_id') for r in runners if r.get('horse_id')]
    
    # 批量获取所有马匹的往绩
    perf_cache = get_horse_performances_batch(supabase, horse_ids, limit=10)
    
    scores = []
    basic_scores = []
    race_scores = []
    odds_scores = []
    status_scores = []
    
    for runner in runners:
        horse_id = runner.get('horse_id')
        if not horse_id:
            # 没有horse_id的马匹，使用默认评分
            basic_scores.append(50)
            race_scores.append(50)
            odds_scores.append(50)
            status_scores.append(50)
            scores.append({
                "horse_no": runner.get('horse_no'),
                "horse_id": None,
                "overall_score": 50,
                "basic_score": 50,
                "race_score": 50,
                "odds_score": 50,
                "status_score": 50
            })
            continue
        
        # 获取该马匹的往绩
        performances = perf_cache.get(horse_id, [])
        
        # 提取历史体重列表
        past_weights = [p.get('body_weight') for p in performances if p.get('body_weight')]
        
        # 获取赛事参数
        distance = runner.get('distance', 1200)
        draw = runner.get('draw')
        jockey = runner.get('jockey')
        trainer = runner.get('trainer')
        body_weight = runner.get('body_weight')
        closing_profile = runner.get('closing_profile', 'Even')
        incident = runner.get('incident', '')
        odds_win = runner.get('odds_win')
        
        # 计算各维度评分
        basic_score = calculate_basic_score(performances, distance)
        race_score = calculate_race_score(performances, venue, distance, draw, jockey, trainer)
        odds_score = calculate_odds_score(odds_win)
        status_score = calculate_status_score(horse_id, race_date, body_weight, past_weights, closing_profile, incident)
        
        # 综合评分
        overall_score = calculate_overall_score(basic_score, race_score, odds_score, status_score)
        
        basic_scores.append(basic_score)
        race_scores.append(race_score)
        odds_scores.append(odds_score)
        status_scores.append(status_score)
        
        scores.append({
            "horse_no": runner.get('horse_no'),
            "horse_id": horse_id,
            "overall_score": overall_score,
            "basic_score": basic_score,
            "race_score": race_score,
            "odds_score": odds_score,
            "status_score": status_score
        })
    
    # 计算胜率概率
    # 计算胜率概率
    probabilities = softmax_probabilities(
        [s["overall_score"] for s in scores], 
        temperature=0.8
    )
    
    # 将概率赋值给每个 score
    for i, prob in enumerate(probabilities):
        scores[i]["win_probability"] = round(prob * 100, 2)  # 转换为百分比
    
    return scores, probabilities


# ==================== 模块导出 ====================

__all__ = [
    # 权重常量
    'LEVEL1_WEIGHTS',
    'BASIC_WEIGHTS', 
    'RACE_WEIGHTS',
    'ODDS_WEIGHTS',
    'STATUS_WEIGHTS',
    # 核心函数
    'calculate_horse_age',
    'get_age_factor',
    'calculate_basic_score',
    'calculate_race_score',
    'calculate_odds_score',
    'calculate_status_score',
    'calculate_overall_score',
    'softmax_probabilities',
    'calculate_race_scores',
    'analyze_incident',
    # 批量函数
    'get_horse_performances_batch',
    'calculate_horse_full_score'
]
