"""
香港赛马会高级数据抓取工具 v2（Excel文本修复版）
包含：分段时间、沿途走位、竞赛事件报告、班次、路程、场地状况
修复：lbw_raw 在 Excel 中显示为文本（添加 ="..." 格式）
用法: python hkjc_advanced_scraper_v2.py --start 2025-01-01 --end 2026-06-06 --output hkjc_full_year.csv --delay 1.5
"""

import requests
from bs4 import BeautifulSoup
import re
import csv
import time
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json


def parse_race_result(race_date: str, venue: str, race_no: int):
    """解析单场赛果（包含所有专业数据）"""
    url = f"https://racing.hkjc.com/zh-hk/local/information/localresults?racedate={race_date}&Racecourse={venue}&RaceNo={race_no}"
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"    请求失败: {e}")
        return None, []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1. 提取赛事基本信息（班次、路程、场地）
    race_info = extract_race_info(soup, race_date, venue, race_no)
    
    # 2. 提取分段时间
    race_info['sectional_times'] = extract_sectional_times(soup)
    
    # 3. 提取马匹成绩
    results = extract_race_results(soup, race_date, venue, race_no)
    
    # 4. 提取竞赛事件报告（按马号匹配）
    incidents = extract_incidents(soup)
    
    # 调试：打印事件报告数量
    if incidents:
        print(f"    抓到 {len(incidents)} 条事件报告", end=' ')
    else:
        print(f"    未抓到事件报告", end=' ')
    
    # 5. 为每条记录添加赛事信息
    for result in results:
        horse_no = result['horse_no']
        incident_text = incidents.get(horse_no, '')
        # 如果事件文本过长，可以截断
        if len(incident_text) > 500:
            incident_text = incident_text[:500]
        result['incident'] = incident_text
        result['race_class'] = race_info.get('race_class', '')
        result['distance'] = race_info.get('distance', 0)
        result['going'] = race_info.get('going', '')
        result['sectional_times'] = json.dumps(race_info.get('sectional_times', []))
    
    return race_info, results


def extract_race_info(soup, race_date, venue, race_no) -> Dict:
    """提取赛事基本信息：班次、路程、场地状况"""
    info = {
        'race_date': race_date,
        'venue': venue,
        'race_no': race_no,
        'race_class': '',
        'distance': 0,
        'going': ''
    }
    
    # 方法1：从 class='big' 的 td 中提取（包含班次和路程）
    class_distance_elem = soup.find('td', class_='big', colspan='2')
    if class_distance_elem:
        text = class_distance_elem.get_text(strip=True)
        
        # 提取班次（第X班）
        class_match = re.search(r'第(.*?)班', text)
        if class_match:
            info['race_class'] = class_match.group(1).strip()
        
        # 提取路程（XXX米）
        distance_match = re.search(r'(\d+)米', text)
        if distance_match:
            info['distance'] = int(distance_match.group(1))
    
    # 如果方法1没找到，尝试方法2：从页面其他地方找
    if not info['race_class'] or info['distance'] == 0:
        all_text = soup.get_text()
        class_match = re.search(r'第([一二三四五])班', all_text)
        if class_match:
            info['race_class'] = class_match.group(1)
        distance_match = re.search(r'(\d+)米', all_text)
        if distance_match:
            info['distance'] = int(distance_match.group(1))
    
    # 提取场地状况（例如："好地"、"好至快地"）
    going_elem = soup.find('td', string=re.compile(r'場地狀況'))
    if going_elem:
        going_text = going_elem.find_next_sibling('td')
        if going_text:
            going_raw = going_text.get_text(strip=True)
            going_match = re.search(r'([好黏快慢乾濕]+地?)', going_raw)
            if going_match:
                info['going'] = going_match.group(1)
            else:
                info['going'] = going_raw.split()[0] if going_raw else ''
    
    return info


def extract_sectional_times(soup) -> List[float]:
    """提取分段时间"""
    sectionals = []
    sectional_elem = soup.find('td', string=re.compile(r'分段時間'))
    if sectional_elem:
        sectional_text = sectional_elem.find_next_sibling('td')
        if sectional_text:
            numbers = re.findall(r'(\d+\.\d+)', sectional_text.get_text())
            sectionals = [float(n) for n in numbers]
    return sectionals


def clean_lbw(raw: str) -> str:
    """
    清理头马距离字段，确保在 Excel 中显示为文本
    返回清洗后的字符串
    """
    if not raw or raw == '---':
        return '---'
    
    # 移除多余空格
    raw = raw.strip()
    
    # 如果已经是标准格式，直接返回
    # 标准格式：数字、1/2、1-1/4、2-1/2、3-3/4 等
    if re.match(r'^[\d\-/]+$', raw):
        return raw
    
    # 如果包含中文（如"短馬頭位"），保留原样
    if re.search(r'[\u4e00-\u9fff]', raw):
        return raw
    
    return raw


def extract_race_results(soup, race_date, venue, race_no) -> List[Dict]:
    """提取马匹成绩"""
    table = soup.find('table', class_='table_bd')
    if not table:
        return []
    
    results = []
    rows = table.find_all('tr')[1:]
    
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 12:
            continue
        
        position_str = cols[0].get_text(strip=True)
        if not position_str.isdigit():
            continue
        
        horse_no = cols[1].get_text(strip=True)
        
        horse_name_raw = cols[2].get_text(strip=True)
        horse_name = re.sub(r'\s*\([^)]+\)', '', horse_name_raw).strip()
        horse_id_match = re.search(r'\(([^)]+)\)', horse_name_raw)
        horse_id = horse_id_match.group(1) if horse_id_match else ''
        
        jockey = cols[3].get_text(strip=True)
        trainer = cols[4].get_text(strip=True)
        
        actual_weight_str = cols[5].get_text(strip=True)
        actual_weight = int(actual_weight_str) if actual_weight_str.isdigit() else None
        
        body_weight_str = cols[6].get_text(strip=True)
        body_weight = int(body_weight_str) if body_weight_str.isdigit() else None
        
        draw_str = cols[7].get_text(strip=True)
        draw = int(draw_str) if draw_str.isdigit() else None
        
        # 清洗头马距离
        lbw_raw = cols[8].get_text(strip=True)
        lbw_raw = clean_lbw(lbw_raw)
        
        running_position = cols[9].get_text(strip=True) if len(cols) > 9 else ''
        
        finish_time_raw = cols[10].get_text(strip=True)
        finish_seconds = convert_time_to_seconds(finish_time_raw)
        
        odds_str = cols[11].get_text(strip=True)
        odds = float(odds_str) if odds_str.replace('.', '').isdigit() else None
        
        closing_profile = calculate_closing_profile(running_position)
        
        results.append({
            'race_date': race_date,
            'venue': venue,
            'race_no': race_no,
            'position': int(position_str),
            'horse_no': horse_no,
            'horse_name': horse_name,
            'horse_id': horse_id,
            'jockey': jockey,
            'trainer': trainer,
            'actual_weight': actual_weight,
            'body_weight': body_weight,
            'draw': draw,
            'lbw_raw': lbw_raw,
            'running_position': running_position,
            'finish_time': finish_time_raw,
            'finish_seconds': finish_seconds,
            'odds': odds,
            'closing_profile': closing_profile
        })
    
    return results


def extract_incidents(soup) -> Dict[str, str]:
    """提取竞赛事件报告"""
    incidents = {}
    
    for table in soup.find_all('table', class_='f_tac table_bd'):
        header = table.find('thead')
        if header and '競賽事件' in header.get_text():
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    horse_no = cols[1].get_text(strip=True)
                    incident = cols[3].get_text(strip=True)
                    if horse_no and incident and horse_no.isdigit():
                        incident = incident.replace('\n', ' ').replace('\r', ' ').strip()
                        incident = re.sub(r'\s+', ' ', incident)
                        incidents[horse_no] = incident
            break
    
    return incidents


def convert_time_to_seconds(time_str: str) -> Optional[float]:
    """转换完成时间为秒数"""
    if not time_str:
        return None
    if ':' in time_str:
        parts = time_str.split(':')
        minutes = float(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    try:
        return float(time_str)
    except ValueError:
        return None


def calculate_closing_profile(running_position: str) -> str:
    """计算冲刺 profile"""
    if not running_position:
        return "Even"
    
    parts = running_position.split()
    if len(parts) < 2:
        return "Even"
    
    try:
        pos_before = int(parts[-2]) if parts[-2].isdigit() else 0
        pos_end = int(parts[-1]) if parts[-1].isdigit() else 0
        position_change = pos_end - pos_before
    except (ValueError, IndexError):
        return "Even"
    
    if position_change <= -4:
        return "Strong Closer"
    elif position_change <= -2:
        return "Closer"
    elif position_change <= 1:
        return "Even"
    elif position_change <= 3:
        return "Faded"
    else:
        return "Quitter"


def save_to_csv(results: List[Dict], filename: str):
    """保存结果为 CSV 文件（lbw_raw 强制为文本格式）"""
    if not results:
        print("没有数据可保存")
        return
    
    fieldnames = [
        'race_date', 'venue', 'race_no', 'position', 'horse_no',
        'horse_name', 'horse_id', 'jockey', 'trainer', 'actual_weight',
        'body_weight', 'draw', 'lbw_raw', 'running_position',
        'finish_time', 'finish_seconds', 'odds', 'closing_profile',
        'incident', 'race_class', 'distance', 'going', 'sectional_times'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL)
        writer.writeheader()
        
        for row in results:
            # 复制一行，避免修改原数据
            out_row = row.copy()
            
            # 关键修复：给 lbw_raw 添加 ="..." 格式，强制 Excel 识别为文本
            # 这样 "2-1/4" 就不会被 Excel 自动转换成日期
            lbw_value = out_row.get('lbw_raw', '')
            if lbw_value and lbw_value != '---':
                # 使用 ="value" 格式强制文本
                out_row['lbw_raw'] = f'="{lbw_value}"'
            
            writer.writerow(out_row)
    
    print(f"已保存 {len(results)} 条记录到 {filename}")


def is_race_day(date: datetime) -> bool:
    """判断是否为赛马日（周六或周日）"""
    return date.weekday() in [5, 6]


def scrape_date_range(start_date: datetime, end_date: datetime, output_file: str, delay: float = 1.0):
    """抓取日期范围内的所有赛果"""
    current = start_date
    all_results = []
    total_races = 0
    total_records = 0
    
    venues = ['ST', 'HV']
    
    while current <= end_date:
        if is_race_day(current):
            date_str = current.strftime("%Y/%m/%d")
            print(f"\n📅 {current.strftime('%Y-%m-%d')}")
            
            for venue in venues:
                for race_no in range(1, 13):
                    print(f"  🏇 {venue} 第{race_no}场...", end=' ', flush=True)
                    
                    race_info, results = parse_race_result(date_str, venue, race_no)
                    
                    if results:
                        all_results.extend(results)
                        total_races += 1
                        total_records += len(results)
                        print(f"✅ {len(results)} 条记录")
                    else:
                        if race_no == 1:
                            print(f"⏭️ 无赛事")
                            break
                        print(f"⏭️ 无数据")
                    
                    time.sleep(delay)
        
        current += timedelta(days=1)
    
    if all_results:
        save_to_csv(all_results, output_file)
        print(f"\n📊 统计: {total_races} 场比赛, {total_records} 条记录")
    else:
        print("\n⚠️ 没有抓取到任何数据")
    
    return all_results


def main():
    parser = argparse.ArgumentParser(description='HKJC 高级数据抓取工具 v2（Excel文本修复版）')
    parser.add_argument('--start', type=str, default='2025-01-01', 
                        help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2026-06-06', 
                        help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, default='hkjc_full_year.csv',
                        help='输出 CSV 文件名')
    parser.add_argument('--delay', type=float, default=1.5,
                        help='请求间隔秒数')
    
    args = parser.parse_args()
    
    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d')
    
    print("=" * 60)
    print("🏇 HKJC 高级数据抓取工具 v2（Excel文本修复版）")
    print("=" * 60)
    print(f"📅 日期范围: {args.start} 至 {args.end}")
    print(f"⏱️  请求间隔: {args.delay} 秒")
    print(f"📁 输出文件: {args.output}")
    print("=" * 60)
    
    scrape_date_range(start_date, end_date, args.output, args.delay)
    
    print("\n✅ 抓取完成！")


if __name__ == "__main__":
    main()
