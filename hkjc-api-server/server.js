const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const { HorseRacingAPI } = require('@gikndue/hkjc-api');
const cron = require('node-cron');  // 需要先安装: npm install node-cron

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

// ==================== 辅助函数 ====================

// 检查是否已存在赔率快照
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

// 保存赔率快照
async function saveOddsSnapshot(race, horseNo, oddsType, oddsValue, minutesToStart) {
    try {
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

// 获取未来24小时需要采集赔率的赛事
async function getRacesNeedingOdds() {
    try {
        const meetings = await horseAPI.getActiveMeetings();
        const now = new Date();
        const racesToSync = [];
        
        for (const meeting of meetings) {
            const meetingDate = new Date(meeting.date);
            if ((meetingDate - now) > 24 * 60 * 60 * 1000) continue;
            
            for (const race of meeting.races || []) {
                const postTime = new Date(race.postTime);
                const minutesToStart = (postTime - now) / 1000 / 60;
                
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

// 判断是否应该采集该时间点的赔率
function shouldCollectOdds(minutesBeforeRace) {
    if (minutesBeforeRace > 90) return false;
    if (minutesBeforeRace < 0) return false;
    
    const keyMinutes = [
        90, 80, 70, 60, 50, 45, 40, 35, 30, 27, 24, 21,
        18, 15, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0
    ];
    
    return keyMinutes.includes(minutesBeforeRace);
}

// 采集单场赛事赔率
async function collectOddsForRace(race) {
    console.log(`[采集] ${race.date} ${race.venue} 第${race.raceNo}场 (${race.minutesToStart}分钟后开跑)`);
    
    if (!shouldCollectOdds(race.minutesToStart)) {
        console.log(`[跳过] 非关键时间点: ${race.minutesToStart}分钟`);
        return null;
    }
    
    try {
        const oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(
            race.date, race.venue, race.raceNo, 
            ['WIN', 'PLA', 'QIN', 'FCT', 'TCE', 'TRI']
        );
        
        if (!oddsData) {
            console.log(`[采集] 无赔率数据`);
            return null;
        }
        
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(
            race.date, race.venue, race.raceNo
        );
        
        const runners = raceDetails?.runners || [];
        let savedCount = 0;
        
        for (const runner of runners) {
            const horseNo = parseInt(runner.no);
            
            const winOdds = oddsData.WIN?.find(o => o.horseNo === horseNo);
            if (winOdds) {
                await saveOddsSnapshot(race, horseNo, 'WIN', winOdds.odds, race.minutesToStart);
                savedCount++;
            }
            
            const placeOdds = oddsData.PLA?.find(o => o.horseNo === horseNo);
            if (placeOdds) {
                await saveOddsSnapshot(race, horseNo, 'PLA', placeOdds.odds, race.minutesToStart);
                savedCount++;
            }
        }
        
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
        return { success: true, runners: runners.length, saved: savedCount };
        
    } catch (error) {
        console.error(`[采集] 失败: ${error.message}`);
        return { success: false, error: error.message };
    }
}

// ==================== 核心：单场赛事同步到 Supabase（可复用）====================
async function syncSingleRaceToSupabase(date, venue, raceNo) {
    console.log(`[同步] ${date} ${venue} 第${raceNo}场`);
    
    try {
        // 1. 从 HKJC API 获取赛事信息
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(date, venue, parseInt(raceNo));
        
        if (!raceDetails) {
            console.log(`[同步] ${date} ${venue} 第${raceNo}场 - 未找到赛事数据`);
            return false;
        }
        
        console.log(`[API返回] 距离=${raceDetails.distance}, 马匹数=${raceDetails.runners?.length}`);
        
        // 2. 获取赔率
        let oddsData = null;
        try {
            oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(date, venue, parseInt(raceNo), ['WIN', 'PLA', 'QIN']);
            if (oddsData && oddsData.WIN) {
                console.log(`[赔率] 获取成功，WIN赔率数量: ${oddsData.WIN.length}`);
            }
        } catch (oddsErr) {
            console.error(`[赔率] 获取失败: ${oddsErr.message}`);
        }
        
        // 3. 保存 races 主表
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
        }
        
        // 4. 遍历 runners 保存到 race_runners_clean
        const runners = raceDetails.runners || [];
        
        for (const runner of runners) {
            const horseId = runner.horse?.id || runner.id || runner.horseId || '';
            const horseName = runner.name_en || runner.horseName || 'Unknown';
            const horseNo = parseInt(runner.no) || 0;
            const draw = parseInt(runner.barrierDrawNumber) || 0;
            const actualWeight = parseInt(runner.handicapWeight) || 0;
            const rating = parseInt(runner.internationalRating) || 0;
            
            let jockeyName = '';
            if (runner.jockey) {
                jockeyName = runner.jockey.name_en || '';
            }
            
            const horseNameZh = runner.name_ch || '';
            
            let winOdds = null;
            if (oddsData && oddsData.WIN) {
                const horseOdds = oddsData.WIN.find(o => o.horseNo === horseNo);
                if (horseOdds) {
                    winOdds = horseOdds.odds;
                }
            }
            
            // 保存到 horses 表
            if (horseId) {
                await supabase
                    .from('horses')
                    .upsert({
                        hkjc_id: horseId,
                        name_en: horseName,
                        name_zh: horseNameZh
                    }, { onConflict: 'hkjc_id' });
            }
            
            // 保存到 race_runners_clean
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
            }
        }
        
        console.log(`[同步完成] ${date} ${venue} 第${raceNo}场, ${runners.length} 匹马`);
        return true;
        
    } catch (error) {
        console.error(`同步失败 ${date} ${venue} R${raceNo}:`, error);
        return false;
    }
}

// ==================== 定时任务：每天凌晨3点自动同步未来14天赛事 ====================
cron.schedule('0 3 * * *', async () => {
    console.log('[' + new Date().toISOString() + '] 定时任务触发：开始同步未来14天赛程...');
    const startTime = Date.now();

    try {
        const activeMeetings = await horseAPI.getActiveMeetings();
        const now = new Date();
        const futureMeetings = activeMeetings.filter(meeting => new Date(meeting.date) >= now);

        let totalSyncedRaces = 0;
        let totalFailedRaces = 0;

        for (const meeting of futureMeetings) {
            const races = meeting.races || [];
            for (const race of races) {
                const success = await syncSingleRaceToSupabase(meeting.date, meeting.venueCode, race.no);
                if (success) {
                    totalSyncedRaces++;
                } else {
                    totalFailedRaces++;
                }
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }

        const duration = Date.now() - startTime;
        console.log(`[定时任务] 执行完成，耗时 ${duration}ms。同步结果: 成功 ${totalSyncedRaces} 场，失败 ${totalFailedRaces} 场。`);

    } catch (error) {
        console.error('[定时任务] 执行失败:', error);
    }
}, {
    scheduled: true,
    timezone: "Asia/Shanghai"
});

// ==================== API 路由 ====================

// 健康检查
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// 获取赛马日列表
app.get('/api/meetings', async (req, res) => {
    try {
        const activeMeetings = await horseAPI.getActiveMeetings();
        res.json({ success: true, data: activeMeetings });
    } catch (error) {
        console.error('获取赛马日失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 手动触发单场同步（保留，用于调试或手动更新）
app.post('/api/sync/race', async (req, res) => {
    const { date, venue, raceNo } = req.body;
    console.log(`[手动同步] ${date} ${venue} 第${raceNo}场`);
    
    const success = await syncSingleRaceToSupabase(date, venue, raceNo);
    
    if (success) {
        res.json({ success: true, message: `同步成功: ${date} ${venue} 第${raceNo}场` });
    } else {
        res.status(500).json({ success: false, error: '同步失败，请查看服务器日志。' });
    }
});

// 手动触发赔率采集
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

// 自动赔率采集（供定时任务调用）
app.post('/api/collect/auto', async (req, res) => {
    console.log('[API] 自动赔率采集');
    const races = await getRacesNeedingOdds();
    const targetRaces = races.filter(r => r.minutesToStart <= 180 && r.minutesToStart >= 30);
    
    const results = [];
    for (const race of targetRaces) {
        const result = await collectOddsForRace(race);
        results.push(result);
        await new Promise(r => setTimeout(r, 500));
    }
    
    res.json({ collected: results.length, details: results });
});

// 更新最终赔率
app.post('/api/odds/final', async (req, res) => {
    console.log('[API] 更新最终赔率');
    const races = await getRacesNeedingOdds();
    const targetRaces = races.filter(r => r.minutesToStart <= 10 && r.minutesToStart >= 0);
    
    for (const race of targetRaces) {
        await updateFinalOdds(race);
    }
    
    res.json({ updated: targetRaces.length });
});

// 数据库清理
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

// 启动服务器
app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
});

// 更新最终赔率的辅助函数
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
