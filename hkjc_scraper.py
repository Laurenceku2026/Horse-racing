"""
香港赛马会数据爬虫（降级方案）
当 Node.js API 不可用时使用
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase 配置
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_upcoming_races():
    """获取未来赛马日"""
    url = "https://racing.hkjc.com/racing/info/meeting/raceMeeting.asp"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    meetings = []
    table = soup.find('table', class_='table_bd')
    if table:
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                meetings.append({
                    'date': cols[0].text.strip(),
                    'venue': cols[1].text.strip(),
                    'race_count': int(cols[3].text.strip()) if cols[3].text.strip().isdigit() else 0
                })
    return meetings

def get_race_results(date, venue, race_no):
    """获取赛果"""
    url = f"https://racing.hkjc.com/racing/Info/Meeting/Results/english/Local/{date}/{venue}/{race_no}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    results = []
    table = soup.find('table', class_='table_bd f_fs13')
    if table:
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 10:
                results.append({
                    'position': cols[0].text.strip(),
                    'horse_no': cols[1].text.strip(),
                    'horse_name': cols[2].text.strip(),
                    'jockey': cols[3].text.strip(),
                    'actual_weight': cols[4].text.strip(),
                    'draw': cols[5].text.strip(),
                    'odds': cols[6].text.strip(),
                    'finishing_time': cols[9].text.strip()
                })
    return results
#------------
def save_to_supabase(race_data, results):
    """保存到 Supabase（含马匹、骑师表）"""
    # 1. 保存赛事主表
    supabase.schema('racing').table('races').upsert({
        'race_date': race_data['date'],
        'venue': race_data['venue'],
        'race_no': race_data['race_no'],
        'race_status': 'RESULT'
    }).execute()
    
    # 2. 保存结果（同时保存马匹、骑师）
    for result in results:
        # 2.1 保存马匹（如果不存在）
        if result.get('horse_name'):
            supabase.schema('racing').table('horses').upsert({
                'name_en': result['horse_name']
            }, on_conflict='name_en').execute()
        
        # 2.2 保存骑师（如果不存在）
        if result.get('jockey'):
            supabase.schema('racing').table('jockeys').upsert({
                'name_en': result['jockey']
            }, on_conflict='name_en').execute()
        
        # 2.3 保存出赛记录
        supabase.schema('racing').table('race_runners').upsert({
            'race_date': race_data['date'],
            'venue': race_data['venue'],
            'race_no': race_data['race_no'],
            'horse_name': result['horse_name'],
            'finishing_position': result['position'],
            'draw': result['draw'],
            'actual_weight': result['actual_weight'],
            'odds_win': result['odds'],
            'jockey_name': result.get('jockey')
        }).execute()

if __name__ == '__main__':
    meetings = get_upcoming_races()
    print(f"找到 {len(meetings)} 个赛马日")
    for m in meetings:
        print(f"  {m['date']} - {m['venue']} - {m['race_count']}场")
