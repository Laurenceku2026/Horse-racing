const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const { HorseRacingAPI } = require('@gikndue/hkjc-api');

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(cors());
app.use(express.json());

// Supabase 客户端
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

// HKJC API 客户端
const horseAPI = new HorseRacingAPI();

// ==================== 赔率采集核心函数 ====================

// 获取未来24小时需要采集赔率的赛事
async function getRacesNeedingOdds() {
    try {
        const meetings = await horseAPI.getActiveMeetings();
        const now = new Date();
        const racesToSync = [];
        
        for (const meeting of meetings) {
            // 只处理未来24小时内的赛事
            const meetingDate = new Date(meeting.date);
            if ((meetingDate - now) > 24 * 60 * 60 * 1000) continue;
            
            for (const race of meeting.races || []) {
                const postTime = new Date(race.postTime);
                const minutesToStart = (postTime - now) / 1000 / 60;
                
                // 采集窗口：开跑前 3 小时到开跑
                if (minutesToStart <= 180 && minutesToStart >= 0) {
                    racesToSync.push({
                        date: meeting.date,
                        venue: meeting.venueCode,
                        raceNo: race.no,
                        postTime: postTime,
                        minutesToStart: Math.round(minutesToStart)
                    });
                }
            }
        }
        
        return racesToSync;
    } catch (error) {
        console.error('获取赛事失败:', error);
        return [];
    }
}

// 保存赔率快照到历史表
// 保存赔率快照到历史表（带去重）
async function saveOddsSnapshot(race, horseNo, oddsType, oddsValue, minutesToStart) {
    try {
        // 检查是否已存在
        const exists = await hasOddsSnapshot(race, horseNo, oddsType, minutesToStart);
        if (exists) {
            console.log(`[跳过] 已存在: ${race.date} ${race.venue} R${race.raceNo} 马${horseNo} ${oddsType} @ ${minutesToStart}分钟`);
            return;
        }
        
        const { error } = await supabase
            .from('odds_history')
            .insert({
                race_date: race.date,
                venue: race.venue,
                race_no: race.raceNo,
                horse_no: horseNo,
                odds_type: oddsType,
                odds_value: oddsValue,
                recorded_at: new Date().toISOString(),
                minutes_before_race: minutesToStart
            });
        
        if (error) {
            console.error(`保存赔率历史失败: ${error.message}`);
        } else {
            console.log(`[保存] ${race.date} ${race.venue} R${race.raceNo} 马${horseNo} ${oddsType} = ${oddsValue} @ ${minutesToStart}分钟`);
        }
    } catch (error) {
        console.error(`保存赔率历史异常: ${error.message}`);
    }
}

// 采集单场赛事的所有赔率
async function collectOddsForRace(race) {
    console.log(`[采集] ${race.date} ${race.venue} 第${race.raceNo}场 (${race.minutesToStart}分钟后开跑)`);
    
    // 智能采集：只采集关键时间点
    if (!shouldCollectOdds(race.minutesToStart)) {
        console.log(`[跳过] 非关键时间点: ${race.minutesToStart}分钟`);
        return null;
    }
    
    try {
        // 获取所有赔率类型（WIN, PLA, QIN, FCT, TCE, TRI）
        const oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(
            race.date, race.venue, race.raceNo, 
            ['WIN', 'PLA', 'QIN', 'FCT', 'TCE', 'TRI']
        );
        
        if (!oddsData) {
            console.log(`[采集] 无赔率数据`);
            return null;
        }
        
        // 获取该场赛事的马匹列表
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(
            race.date, race.venue, race.raceNo
        );
        
        const runners = raceDetails?.runners || [];
        let savedCount = 0;
        
        // 遍历每匹马，保存赔率快照
        for (const runner of runners) {
            const horseNo = parseInt(runner.no);
            
            // 独赢赔率
            const winOdds = oddsData.WIN?.find(o => o.horseNo === horseNo);
            if (winOdds) {
                await saveOddsSnapshot(race, horseNo, 'WIN', winOdds.odds, race.minutesToStart);
                savedCount++;
            }
            
            // 位置赔率
            const placeOdds = oddsData.PLA?.find(o => o.horseNo === horseNo);
            if (placeOdds) {
                await saveOddsSnapshot(race, horseNo, 'PLA', placeOdds.odds, race.minutesToStart);
                savedCount++;
            }
        }
        
        // 保存连赢赔率（组合赔率）
        if (oddsData.QIN) {
            for (const qin of oddsData.QIN) {
                await supabase.from('odds_history').insert({
                    race_date: race.date,
                    venue: race.venue,
                    race_no: race.raceNo,
                    horse_no: 0,
                    odds_type: 'QIN',
                    odds_value: qin.odds,
                    recorded_at: new Date().toISOString(),
                    minutes_before_race: race.minutesToStart,
                    horse_id: `${qin.horseNo1}+${qin.horseNo2}`
                });
                savedCount++;
            }
        }
        
        console.log(`[采集] 完成，保存了 ${savedCount} 条记录`);
        
        // 每采集 10 次触发一次清理
        if (Math.random() < 0.1) {
            await triggerDatabaseCleanup();
        }
        
        return { success: true, runners: runners.length, saved: savedCount };
        
    } catch (error) {
        console.error(`[采集] 失败: ${error.message}`);
        return { success: false, error: error.message };
    }
}

// 更新最终赔率到 race_runners_clean 表
async function updateFinalOdds(race) {
    try {
        const oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(
            race.date, race.venue, race.raceNo, 
            ['WIN', 'PLA', 'QIN']
        );
        
        if (!oddsData) return;
        
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(
            race.date, race.venue, race.raceNo
        );
        
        const runners = raceDetails?.runners || [];
        let updatedCount = 0;
        
        for (const runner of runners) {
            const horseNo = parseInt(runner.no);
            const winOdds = oddsData.WIN?.find(o => o.horseNo === horseNo);
            
            if (winOdds) {
                const { error } = await supabase
                    .from('race_runners_clean')
                    .upsert({
                        race_date: race.date,
                        race_no: race.raceNo,
                        venue: race.venue,
                        horse_no: horseNo,
                        horse_name: runner.name_en || '',
                        odds_win: winOdds.odds
                    }, { onConflict: 'race_date,venue,race_no,horse_no' });
                
                if (!error) updatedCount++;
            }
        }
        
        console.log(`[最终赔率] 更新完成 ${race.date} ${race.venue} 第${race.raceNo}场, 更新 ${updatedCount} 匹马`);
    } catch (error) {
        console.error(`[最终赔率] 更新失败: ${error.message}`);
    }
}
// ==================== 数据清理函数 ====================

// 调用 Supabase 清理函数
async function triggerDatabaseCleanup() {
    try {
        const { data, error } = await supabase.rpc('manual_cleanup');
        if (error) {
            console.error('清理失败:', error);
        } else {
            console.log('清理完成:', data);
        }
    } catch (err) {
        console.error('清理异常:', err);
    }
}

// ==================== 智能赔率采集判断 ====================

// 判断是否应该采集该时间点的赔率
function shouldCollectOdds(minutesBeforeRace) {
    // 只采集开跑前 90 分钟内的数据
    if (minutesBeforeRace > 90) return false;
    if (minutesBeforeRace < 0) return false;
    
    // 关键时间点定义
    const keyMinutes = [
        // 赔率公布期
        90, 80, 70, 60,
        // 稳定期
        50, 45, 40, 35,
        // 活跃期
        30, 27, 24, 21,
        // 冲刺期
        18, 15, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1,
        // 最终值
        0
    ];
    
    return keyMinutes.includes(minutesBeforeRace);
}

// 检查该时间点是否已经采集过（避免重复）
async function hasOddsSnapshot(race, horseNo, oddsType, minutesBeforeRace) {
    try {
        const { data, error } = await supabase
            .from('odds_history')
            .select('id')
            .eq('race_date', race.date)
            .eq('venue', race.venue)
            .eq('race_no', race.raceNo)
            .eq('horse_no', horseNo)
            .eq('odds_type', oddsType)
            .eq('minutes_before_race', minutesBeforeRace)
            .limit(1);
        
        if (error) return false;
        return data && data.length > 0;
    } catch (err) {
        return false;
    }
}
// ==================== 赔率采集 API 端点 ====================

// 端点1：手动触发采集（用于测试）
app.post('/api/collect/odds', async (req, res) => {
    console.log('[API] 手动触发赔率采集');
    const races = await getRacesNeedingOdds();
    const results = [];
    
    for (const race of races) {
        const result = await collectOddsForRace(race);
        results.push(result);
        await new Promise(r => setTimeout(r, 1000));
    }
    
    res.json({ collected: results.length, details: results });
});

// 端点2：智能自动采集（供定时任务调用）
app.post('/api/collect/auto', async (req, res) => {
    console.log('[API] 自动赔率采集');
    const races = await getRacesNeedingOdds();
    
    // 只采集开跑前30-180分钟内的赛事
    const targetRaces = races.filter(r => r.minutesToStart <= 180 && r.minutesToStart >= 30);
    
    const results = [];
    for (const race of targetRaces) {
        const result = await collectOddsForRace(race);
        results.push(result);
        await new Promise(r => setTimeout(r, 500));
    }
    
    // 更新调度配置
    await supabase
        .from('odds_schedule_config')
        .update({ 
            last_run: new Date().toISOString(),
            next_run: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
            updated_at: new Date().toISOString()
        })
        .eq('id', 1);
    
    res.json({ 
        collected: results.length, 
        next_run: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
        details: results 
    });
});

// 端点3：更新最终赔率（开跑前5分钟调用）
app.post('/api/odds/final', async (req, res) => {
    console.log('[API] 更新最终赔率');
    const races = await getRacesNeedingOdds();
    const targetRaces = races.filter(r => r.minutesToStart <= 10 && r.minutesToStart >= 0);
    
    for (const race of targetRaces) {
        await updateFinalOdds(race);
    }
    
    res.json({ updated: targetRaces.length });
});
// ========================================
// 手动触发清理端点
app.post('/api/cleanup', async (req, res) => {
    console.log('[API] 手动触发数据库清理');
    try {
        const result = await supabase.rpc('manual_cleanup');
        res.json({ success: true, result: result });
    } catch (error) {
        console.error('清理失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});
// ==================== 健康检查 ====================
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ==================== 获取赛马日列表 ====================
app.get('/api/meetings', async (req, res) => {
    try {
        const activeMeetings = await horseAPI.getActiveMeetings();
        res.json({ success: true, data: activeMeetings });
    } catch (error) {
        console.error('获取赛马日失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// ==================== 同步单场赛事到 Supabase ====================
app.post('/api/sync/race', async (req, res) => {
    const { date, venue, raceNo } = req.body;
    
    console.log(`[开始同步] ${date} ${venue} 第${raceNo}场`);
    
    try {
        // 1. 从 HKJC API 获取赛事信息
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(date, venue, parseInt(raceNo));
        
        if (!raceDetails) {
            return res.json({ success: false, error: '未找到赛事数据' });
        }
        
        console.log(`[API返回] 距离=${raceDetails.distance}, 马匹数=${raceDetails.runners?.length}`);
        
        // 2. 获取赔率
        let oddsData = null;
        try {
            oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(date, venue, parseInt(raceNo), ['WIN', 'PLA', 'QIN']);
            if (oddsData && oddsData.WIN) {
                console.log(`[赔率] 获取成功，WIN赔率数量: ${oddsData.WIN.length}`);
            } else {
                console.log(`[赔率] 无数据`);
            }
        } catch (oddsErr) {
            console.error(`[赔率] 获取失败: ${oddsErr.message}`);
        }
        
        // ========== 3. 保存 races 主表 ==========
        const { error: raceError } = await supabase
            .from('races')
            .upsert({
                race_date: date,
                venue: venue,
                race_no: parseInt(raceNo),
                distance: raceDetails.distance || 0,
                surface: raceDetails.surface || '草地',
                going: raceDetails.going || '好地',
                race_class: raceDetails.raceClass || '',
                total_runners: raceDetails.runners?.length || 0,
                race_status: 'RUNNERS',
                updated_at: new Date().toISOString()
            }, { onConflict: 'race_date,venue,race_no' });
        
        if (raceError) {
            console.error('保存赛事失败:', raceError);
        } else {
            console.log('保存赛事成功');
        }
        
        // ========== 4. 遍历 runners ==========
        const runners = raceDetails.runners || [];
        
        for (const runner of runners) {
            // 获取马匹信息
            const horseId = runner.id || runner.horseId || '';
            const horseName = runner.name_en || runner.horseName || 'Unknown';
            const horseNo = parseInt(runner.no) || 0;
            const draw = parseInt(runner.barrierDrawNumber) || 0;
            const actualWeight = parseInt(runner.handicapWeight) || 0;
            const rating = parseInt(runner.internationalRating) || 0;
            
            // 骑师信息
            let jockeyName = '';
            if (runner.jockey) {
                jockeyName = runner.jockey.name_en || '';
            }
            
            // 中文名
            const horseNameZh = runner.name_ch || '';
            
            // 获取赔率
            let winOdds = null;
            if (oddsData && oddsData.WIN) {
                const horseOdds = oddsData.WIN.find(o => o.horseNo === horseNo);
                if (horseOdds) {
                    winOdds = horseOdds.odds;
                }
            }
            
            // 保存马匹到 horses 表
            if (horseId) {
                await supabase
                    .from('horses')
                    .upsert({
                        hkjc_id: horseId,
                        name_en: horseName,
                        name_zh: horseNameZh
                    }, { onConflict: 'hkjc_id' });
            }
            
            // 保存骑师
            if (jockeyName) {
                await supabase
                    .from('jockeys')
                    .upsert({
                        name_en: jockeyName,
                        name_zh: runner.jockey?.name_ch || ''
                    }, { onConflict: 'name_en' });
            }
            
            // 保存出赛记录（包含 horse_id）
            // 保存出赛记录（使用新表名，带 onConflict）
            const { error: runnerError } = await supabase
                .from('race_runners_clean')
                .upsert({
                    race_date: date,
                    race_no: parseInt(raceNo),
                    venue: venue,
                    horse_id: horseId,
                    horse_name: horseName,
                    horse_name_zh: horseNameZh,
                    horse_no: horseNo,
                    draw: draw,
                    actual_weight: actualWeight,
                    rating: rating,
                    jockey_name: jockeyName,
                    odds_win: winOdds
                }, { onConflict: 'race_date,venue,race_no,horse_no' });
            
            if (runnerError) {
                console.error(`保存出赛记录失败 ${horseName}:`, runnerError);
            } else {
                console.log(`保存马匹: ${horseName}, horse_id: ${horseId}, 档位: ${draw}, 骑师: ${jockeyName}`);
            }
        }
        
        console.log(`[同步完成] ${date} ${venue} 第${raceNo}场, ${runners.length} 匹马`);
        res.json({ 
            success: true, 
            message: `同步成功: ${date} ${venue} 第${raceNo}场`,
            data: { runners: runners.length }
        });
        
    } catch (error) {
        console.error('同步失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 启动服务器
app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
});
