# test_score.py
import requests
from datetime import datetime
from typing import List, Dict

# --- 请在这里配置您的Supabase信息 ---
SUPABASE_URL = "https://wglfpwlqesjrxonfaaeb.supabase.co"
SUPABASE_KEY = "你的 Supabase anon key 或 service_role key" # 请替换成你的 key
# -----------------------------------

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def get_runners(race_date, venue, race_no):
    url = f"{SUPABASE_URL}/rest/v1/race_runners_clean"
    params = {
        "race_date": f"eq.{race_date}",
        "venue": f"eq.{venue}",
        "race_no": f"eq.{race_no}",
        "select": "horse_id,horse_no,horse_name"
    }
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()

def get_history(horse_ids):
    if not horse_ids:
        return {}
    ids_str = ','.join([f"'{hid}'" for hid in horse_ids])
    url = f"{SUPABASE_URL}/rest/v1/past_performances_v2?horse_id=in.({ids_str})&order=race_date.desc&limit=5000"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    
    history = {}
    for row in response.json():
        hid = row.get('horse_id')
        if hid not in history:
            history[hid] = []
        history[hid].append(row)
    return history

# 简单的评分函数
def simple_score(history, target_distance=1200):
    if not history:
        return 0
    total, wins = 0, 0
    for p in history[:10]:  # 只看最近10场
        total += 1
        if p.get('position') == 1:
            wins += 1
    return (wins / total * 100) if total > 0 else 0

def main():
    print("1. 正在获取参赛马匹...")
    runners = get_runners('2026-06-13', 'ST', 1)
    if not runners:
        print("   错误：无法获取参赛马匹！")
        return
    print(f"   成功，找到 {len(runners)} 匹马。")

    horse_ids = [r['horse_id'] for r in runners if r.get('horse_id')]
    print(f"\n2. 正在获取 {len(horse_ids)} 匹马的历史成绩...")
    history = get_history(horse_ids)
    print(f"   成功获取 {len(history)} 匹马的成绩。")

    print("\n3. 开始计算评分：")
    for runner in runners:
        hid = runner.get('horse_id')
        score = simple_score(history.get(hid, []))
        print(f"   马号 {runner.get('horse_no')} ({runner.get('horse_name')}): 评分 = {score:.1f}")

if __name__ == "__main__":
    main()
